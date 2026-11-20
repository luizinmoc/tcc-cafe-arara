#!/usr/bin/env python3
"""
inference_engine.py — Motor de Inferência Deep Learning YOLOv8 com Calibração HSV.

Executa a detecção de frutos em escala nativa 1:1 utilizando janelamento deslizante denso,
NMS global e classificação refinada de maturação para a variedade Café Arara.
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image
from ultralytics import YOLO

from src.color_classifier import ColorClassifier, DEFAULT_COLOR_RANGES
from src.utils import CLASS_NAMES, CLASS_COLORS_BGR

logger = logging.getLogger("inference_engine")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEIGHTS_PATH = PROJECT_ROOT / "weights" / "best.pt"

# Cache do modelo em memória
_CACHED_MODEL: YOLO | None = None
_CACHED_MTIME: float = 0.0


def get_model() -> YOLO:
    """Retorna o modelo YOLO carregado em cache, recarregando se os pesos mudaram."""
    global _CACHED_MODEL, _CACHED_MTIME

    if not WEIGHTS_PATH.exists():
        raise FileNotFoundError(f"Pesos do modelo não encontrados em: {WEIGHTS_PATH}")

    current_mtime = WEIGHTS_PATH.stat().st_mtime
    if _CACHED_MODEL is None or current_mtime != _CACHED_MTIME:
        logger.info("Carregando pesos do YOLOv8: %s", WEIGHTS_PATH)
        _CACHED_MODEL = YOLO(str(WEIGHTS_PATH))
        _CACHED_MTIME = current_mtime

    return _CACHED_MODEL


def segment_tray_and_slats(
    image_bgr: NDArray[np.uint8],
) -> tuple[tuple[int, int, int, int], list[tuple[int, int]]]:
    """Segmenta automaticamente os limites do leito de café (ROI) e detecta ripas divisórias de madeira.

    Elimina:
    - O chão de asfalto/concreto acima e abaixo da bandeja
    - As vigas laterais de madeira e a fita métrica/trena
    - As ripas horizontais de madeira que dividem os compartimentos
    """
    h_img, w_img = image_bgr.shape[:2]
    target_w = 540
    target_h = int(h_img * target_w / w_img)
    small = cv2.resize(image_bgr, (target_w, target_h))
    hs, ws = small.shape[:2]

    hsv_s = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    gray_s = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    # 1. Delimitar leito de café por saturação e brilho característicos dos frutos Arara
    coffee_pixels = ((hsv_s[:, :, 1] > 35) & (hsv_s[:, :, 2] > 35)).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    dense = cv2.morphologyEx(coffee_pixels, cv2.MORPH_CLOSE, kernel)

    row_density = np.mean(dense > 0, axis=1)
    col_density = np.mean(dense > 0, axis=0)

    y_active = np.where(row_density > 0.30)[0]
    x_active = np.where(col_density > 0.30)[0]

    y_min = int((y_active[0] / hs) * h_img) if len(y_active) > 0 else int(0.18 * h_img)
    y_max = int((y_active[-1] / hs) * h_img) if len(y_active) > 0 else int(0.98 * h_img)
    x_min = int((x_active[0] / ws) * w_img) if len(x_active) > 0 else int(0.05 * w_img)
    x_max = int((x_active[-1] / ws) * w_img) if len(x_active) > 0 else int(0.95 * w_img)

    # Margens de segurança para garantir exclusão do chão e vigas externas
    y_min = max(y_min + int(0.015 * h_img), int(0.18 * h_img))
    y_max = min(y_max, int(0.985 * h_img))
    x_min = max(x_min + int(0.015 * w_img), int(0.05 * w_img))
    x_max = min(x_max - int(0.015 * w_img), int(0.95 * w_img))

    # 2. Detectar ripas horizontais divisórias internas de madeira
    sobel_x = cv2.Sobel(gray_s, cv2.CV_64F, 1, 0, ksize=3)
    c1, c2 = int(0.20 * ws), int(0.80 * ws)
    row_sx_var = np.var(sobel_x[:, c1:c2], axis=1)

    y1_s = int(y_min / h_img * hs)
    y2_s = int(y_max / h_img * hs)
    active_vars = row_sx_var[y1_s:y2_s]
    med_var = float(np.median(active_vars)) if len(active_vars) > 0 else 50000.0

    slat_ranges: list[tuple[int, int]] = []
    in_slat = False
    slat_start = 0

    for ys in range(y1_s + 15, y2_s - 15):
        if row_sx_var[ys] < 0.38 * med_var:
            if not in_slat:
                in_slat = True
                slat_start = ys
        else:
            if in_slat:
                in_slat = False
                if (ys - slat_start) >= 8:
                    y_slat_min = int(slat_start / hs * h_img) - int(0.006 * h_img)
                    y_slat_max = int(ys / hs * h_img) + int(0.006 * h_img)
                    slat_ranges.append((y_slat_min, y_slat_max))

    if in_slat and (y2_s - 15 - slat_start) >= 8:
        y_slat_min = int(slat_start / hs * h_img) - int(0.006 * h_img)
        y_slat_max = int((y2_s - 15) / hs * h_img) + int(0.006 * h_img)
        slat_ranges.append((y_slat_min, y_slat_max))

    return (x_min, y_min, x_max, y_max), slat_ranges


def compute_grid_coordinates(min_v: int, max_v: int, sz: int, st: int) -> list[int]:
    """Gera coordenadas de janelas garantindo cobertura 100% até a última borda."""
    coords = []
    c = min_v
    while c + sz <= max_v:
        coords.append(c)
        c += st
    last_c = max_v - sz
    if last_c not in coords and last_c >= min_v:
        coords.append(last_c)
    return sorted(list(set(coords)))


def run_inference(
    image_bgr: NDArray[np.uint8],
    confidence: float = 0.04,
    iou_threshold: float = 0.65,
    tile_size: int = 640,
    stride: int = 360,
    draw_style: str = "boxes",  # Modo Bounding Boxes
    box_thickness: int = 2,
) -> dict[str, Any]:
    """Executa a inferência completa sobre a imagem, refinando maturação e gerando anotações."""
    model = get_model()
    h_img, w_img = image_bgr.shape[:2]

    # Delimitar ROI automática da bandeja e detectar ripas de madeira
    (x_min, y_min, x_max, y_max), slat_ranges = segment_tray_and_slats(image_bgr)
    logger.info(
        "ROI leito de cafe: X=[%d, %d], Y=[%d, %d] | Ripas divisórias detectadas: %s",
        x_min,
        x_max,
        y_min,
        y_max,
        slat_ranges,
    )

    tops = compute_grid_coordinates(y_min, y_max, tile_size, stride)
    lefts = compute_grid_coordinates(x_min, x_max, tile_size, stride)

    tiles: list[NDArray[np.uint8]] = []
    offsets: list[tuple[int, int]] = []

    for top in tops:
        for left in lefts:
            patch = image_bgr[top : top + tile_size, left : left + tile_size]
            if patch.shape[0] == tile_size and patch.shape[1] == tile_size:
                tiles.append(patch)
                offsets.append((left, top))

    all_raw_boxes: list[list[float]] = []
    all_scores: list[float] = []
    all_classes: list[int] = []

    # Inferência em lotes (batch inference)
    batch_size = 8
    for i in range(0, len(tiles), batch_size):
        b_tiles = tiles[i : i + batch_size]
        b_offsets = offsets[i : i + batch_size]

        results = model.predict(
            source=b_tiles,
            imgsz=tile_size,
            conf=confidence,
            max_det=2000,
            verbose=False,
        )

        for res, (off_x, off_y) in zip(results, b_offsets):
            boxes = res.boxes
            if boxes is None or len(boxes) == 0:
                continue

            for b in boxes:
                bx1, by1, bx2, by2 = b.xyxy[0].cpu().numpy().tolist()
                score = float(b.conf.item())
                cid = int(b.cls.item())

                all_raw_boxes.append([bx1 + off_x, by1 + off_y, bx2 + off_x, by2 + off_y])
                all_scores.append(score)
                all_classes.append(cid)

    # NMS Global
    detections: list[dict[str, Any]] = []
    counts = {"verde": 0, "amarelo": 0, "cereja": 0, "passado": 0, "seco": 0}

    if all_raw_boxes:
        boxes_xywh = []
        for x1, y1, x2, y2 in all_raw_boxes:
            boxes_xywh.append([int(x1), int(y1), int(x2 - x1), int(y2 - y1)])

        indices = cv2.dnn.NMSBoxes(
            bboxes=boxes_xywh,
            scores=all_scores,
            score_threshold=confidence,
            nms_threshold=iou_threshold,
        )

        if len(indices) > 0:
            classifier = ColorClassifier(color_ranges=DEFAULT_COLOR_RANGES)

            for idx in indices.flatten():
                gx1, gy1, gx2, gy2 = all_raw_boxes[idx]
                bw = gx2 - gx1
                bh = gy2 - gy1
                cy = (gy1 + gy2) / 2
                cx = (gx1 + gx2) / 2

                # Filtro 1: Descartar caixas nas ripas de madeira divisórias
                in_slat = False
                for s_min, s_max in slat_ranges:
                    if s_min <= cy <= s_max:
                        in_slat = True
                        break
                if in_slat:
                    continue

                # Filtro 2: Descartar formatos anômalos (não elipsoides/esféricos)
                aspect_ratio = bw / max(1.0, bh)
                if aspect_ratio < 0.45 or aspect_ratio > 2.2:
                    continue

                # Filtro 3: Refinamento espectral HSV e rejeição de madeira / chão / trena
                y1_c, y2_c = max(0, int(gy1)), min(h_img, int(gy2))
                x1_c, x2_c = max(0, int(gx1)), min(w_img, int(gx2))
                crop_grain = image_bgr[y1_c:y2_c, x1_c:x2_c]

                if crop_grain.size == 0:
                    continue

                hsv_grain = cv2.cvtColor(crop_grain, cv2.COLOR_BGR2HSV)
                med_h = float(np.median(hsv_grain[:, :, 0]))
                med_s = float(np.median(hsv_grain[:, :, 1]))
                med_v = float(np.median(hsv_grain[:, :, 2]))

                # Rejeição de chão de asfalto e madeira acinzentada
                if med_s < 28.0 and med_v > 40.0:
                    continue

                matched_cid: int | None = None
                for cr in classifier.color_ranges:
                    if (
                        cr.h_min <= med_h <= cr.h_max
                        and cr.s_min <= med_s <= cr.s_max
                        and cr.v_min <= med_v <= cr.v_max
                    ):
                        matched_cid = cr.class_id
                        break

                if matched_cid is not None:
                    cid = matched_cid
                else:
                    # Se não bate com nenhuma faixa de maturação e tem saturação baixa com baixa confiança, descartar
                    if all_scores[idx] < 0.12 and med_s < 35.0:
                        continue
                    cid = all_classes[idx]

                cname = CLASS_NAMES.get(cid, "desconhecido")
                if cname in counts:
                    counts[cname] += 1

                detections.append({
                    "class_id": cid,
                    "class_name": cname,
                    "confidence": round(all_scores[idx], 3),
                    "bbox": [int(gx1), int(gy1), int(gx2), int(gy2)],
                    "center": [int(cx), int(cy)],
                })

    total_graos = len(detections)
    ratios = {
        k: round((v / total_graos * 100), 1) if total_graos > 0 else 0.0
        for k, v in counts.items()
    }

    # Recomendação agronômica
    pct_ideal = ratios.get("cereja", 0.0) + ratios.get("amarelo", 0.0)
    if pct_ideal >= 75.0:
        recomendacao = "Excelente ponto de colheita! Alta concentração de frutos maduros e cerejas."
        status_colheita = "Ponto Ideal de Colheita ★"
        badge_cor = "#10b981"
    elif pct_ideal >= 50.0:
        recomendacao = "Maturação moderada. Colheita seletiva recomendada nos próximos dias."
        status_colheita = "Maturação Moderada"
        badge_cor = "#f59e0b"
    elif ratios.get("verde", 0.0) > 40.0:
        recomendacao = "Lote predominantemente imaturo. Recomenda-se aguardar evolução fisiológica."
        status_colheita = "Aguardar Maturação"
        badge_cor = "#3b82f6"
    else:
        recomendacao = "Presença significativa de frutos passados/secos. Necessária catação prévia."
        status_colheita = "Catação Necessária"
        badge_cor = "#ef4444"

    # Renderizar imagem anotada com Bounding Boxes
    annotated_bgr = image_bgr.copy()
    for d in detections:
        cid = d["class_id"]
        color = CLASS_COLORS_BGR.get(cid, (255, 255, 255))
        x1, y1, x2, y2 = d["bbox"]
        cv2.rectangle(annotated_bgr, (x1, y1), (x2, y2), color, max(1, int(box_thickness)))

    # Converter imagem para Base64 JPEG otimizado
    # Se a imagem for 4K muito grande, redimensionar versão web para transmissão rápida
    max_web_dim = 1600
    h_ann, w_ann = annotated_bgr.shape[:2]
    if max(h_ann, w_ann) > max_web_dim:
        scale = max_web_dim / max(h_ann, w_ann)
        web_bgr = cv2.resize(annotated_bgr, (int(w_ann * scale), int(h_ann * scale)), interpolation=cv2.INTER_AREA)
    else:
        web_bgr = annotated_bgr

    _, buffer = cv2.imencode(".jpg", web_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64_image = base64.b64encode(buffer).decode("utf-8")

    return {
        "total_graos": total_graos,
        "counts": counts,
        "ratios": ratios,
        "detections_sample": detections[:50],  # amostra para tabela
        "recomendacao": recomendacao,
        "status_colheita": status_colheita,
        "badge_cor": badge_cor,
        "annotated_image_b64": f"data:image/jpeg;base64,{b64_image}",
        "dimensoes": {"largura": w_img, "altura": h_img},
    }
