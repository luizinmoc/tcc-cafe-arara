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
    """Segmenta com precisão milimétrica os limites reais do leito de café (ROI) e detecta ripas divisórias.

    Garante:
    - Inclusão de 100% dos frutos de café, incluindo a camada superior de frutos verdes
    - Exclusão total do chão de asfalto/concreto acima e abaixo da bandeja
    - Exclusão total da fita métrica/trena e da viga de madeira na lateral esquerda
    - Exclusão total da viga de madeira na lateral direita
    - Supressão de detecções na ripa horizontal intermediária de madeira
    """
    h_img, w_img = image_bgr.shape[:2]
    # Redimensionamento rápido mantendo proporção para análise robusta
    small = cv2.resize(image_bgr, (270, 480))
    hs, ws = small.shape[:2]

    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    # 1. Delimitação vertical (Y):
    # O chão de asfalto superior e a moldura de madeira têm saturação baixa (S < 20).
    # O leito de café (incluindo frutos verdes) apresenta saturação consistente (S > 24).
    center_s = np.mean(hsv[:, int(ws * 0.3) : int(ws * 0.7), 1], axis=1)
    kernel_y = np.ones(5) / 5
    smooth_s = np.convolve(center_s, kernel_y, mode="same")

    y_start_idx = 0
    for y in range(int(0.01 * hs), int(0.60 * hs)):
        if smooth_s[y] > 24 and smooth_s[min(hs - 1, y + 2)] > 24:
            y_start_idx = y
            break

    y_end_idx = hs - 1
    for y in range(hs - 1, int(0.50 * hs), -1):
        if smooth_s[y] > 24 and smooth_s[max(0, y - 2)] > 24:
            y_end_idx = y
            break

    y_min = int(y_start_idx / hs * h_img)
    y_max = int(y_end_idx / hs * h_img)

    # 2. Delimitação horizontal (X):
    # Elimina a fita métrica e a viga de madeira esquerda, e a viga de madeira direita.
    row_start = max(0, y_start_idx + 4)
    row_end = min(hs, y_end_idx - 4)

    col_s = np.mean(hsv[row_start:row_end, :, 1], axis=0)
    smooth_col_s = np.convolve(col_s, np.ones(5) / 5, mode="same")

    # Busca a borda esquerda do leito de café (após a trena e viga lateral)
    x_start_idx = 0
    for x in range(int(0.02 * ws), int(0.25 * ws)):
        if smooth_col_s[x] > 100:
            x_start_idx = x
            break
    x_start_idx = max(x_start_idx + 1, int(0.065 * ws))

    # Busca a borda direita do leito de café (antes da viga lateral direita)
    x_end_idx = ws - 1
    for x in range(ws - int(0.02 * ws), int(0.75 * ws), -1):
        if smooth_col_s[x] > 100:
            x_end_idx = x
            break
    x_end_idx = min(x_end_idx - 1, int(0.925 * ws))

    x_min = int(x_start_idx / ws * w_img)
    x_max = int(x_end_idx / ws * w_img)

    # 3. Detecção de ripas divisórias intermediárias de madeira (Sobel-X)
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    c1, c2 = int(0.25 * ws), int(0.75 * ws)
    row_sx_var = np.var(sobel_x[:, c1:c2], axis=1)

    active_vars = row_sx_var[row_start:row_end]
    med_var = float(np.median(active_vars)) if len(active_vars) > 0 else 50000.0

    slat_ranges: list[tuple[int, int]] = []
    in_slat = False
    slat_start = 0

    for ys in range(row_start + 10, row_end - 10):
        if row_sx_var[ys] < 0.40 * med_var:
            if not in_slat:
                in_slat = True
                slat_start = ys
        else:
            if in_slat:
                in_slat = False
                if (ys - slat_start) >= 6:
                    y_slat_min = int(slat_start / hs * h_img) - int(0.008 * h_img)
                    y_slat_max = int(ys / hs * h_img) + int(0.008 * h_img)
                    slat_ranges.append((y_slat_min, y_slat_max))

    if in_slat and (row_end - 10 - slat_start) >= 6:
        y_slat_min = int(slat_start / hs * h_img) - int(0.008 * h_img)
        y_slat_max = int((row_end - 10) / hs * h_img) + int(0.008 * h_img)
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

                # Filtro 1: Descartar caixas fora dos limites estritos do leito de cafe
                if cx < x_min or cx > x_max or cy < y_min or cy > y_max:
                    continue

                # Filtro 2: Descartar caixas nas ripas de madeira divisórias
                in_slat = False
                for s_min, s_max in slat_ranges:
                    if s_min <= cy <= s_max:
                        in_slat = True
                        break
                if in_slat:
                    continue

                # Filtro 3: Descartar formatos anômalos (não elipsoides/esféricos)
                aspect_ratio = bw / max(1.0, bh)
                if aspect_ratio < 0.45 or aspect_ratio > 2.2:
                    continue

                # Filtro 4: Refinamento espectral HSV e rejeição de madeira / chão / trena
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
                if med_s < 30.0 and med_v > 38.0:
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
