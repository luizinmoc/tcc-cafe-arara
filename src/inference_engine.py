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
from src.grain_classifier import (
    classify_candidates,
    extract_grain_features,
    precompute_image_maps,
)
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


def compute_grid_coordinates(min_v: int, max_v: int, sz: int, st: int) -> list[int]:
    """Gera coordenadas de janelas garantindo cobertura 100% até a última borda."""
    if max_v - min_v <= sz:
        return [max(0, min_v)]
    coords = []
    c = min_v
    while c + sz <= max_v:
        coords.append(c)
        c += st
    last_c = max_v - sz
    if last_c not in coords and last_c >= 0:
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
    """Executa a inferência híbrida adaptativa sobre a imagem.
    
    1. Executa inferência na imagem completa (imgsz=640) para detectar frutos
       de qualquer tamanho, em close-up, fotos de internet ou fotos de galho.
    2. Para imagens de alta resolução (4K / bandejas coletivas), executa fatiamento
       em grade (tiling) de alta densidade 1:1 para detectar milhares de micro-grãos.
    3. Unifica e deduplica todas as propostas via NMS global.
    4. Aplica o classificador morfológico de Machine Learning para rejeitar ripas, tocos e chão.
    """
    model = get_model()
    h_img, w_img = image_bgr.shape[:2]

    all_raw_boxes: list[list[float]] = []
    all_scores: list[float] = []
    all_classes: list[int] = []

    # ══════════════════════════════════════════════════════════════════════════
    # PASSO 1: Inferência Global na Imagem Completa (Escala Global)
    # Suporta qualquer resolução (fotos pequenas de internet, galho ou close-up)
    # ══════════════════════════════════════════════════════════════════════════
    full_conf = max(0.02, confidence)
    try:
        full_results = model.predict(
            source=image_bgr,
            imgsz=640,
            conf=full_conf,
            max_det=3000,
            verbose=False,
        )
        if full_results and len(full_results) > 0 and full_results[0].boxes is not None:
            for b in full_results[0].boxes:
                bx1, by1, bx2, by2 = b.xyxy[0].cpu().numpy().tolist()
                score = float(b.conf.item())
                cid = int(b.cls.item())
                all_raw_boxes.append([bx1, by1, bx2, by2])
                all_scores.append(score)
                all_classes.append(cid)
    except Exception as e:
        logger.warning("Falha no passe global da imagem: %s", e)

    # ══════════════════════════════════════════════════════════════════════════
    # PASSO 2: Fatiamento em Grade (Tiling) para Imagens de Alta Resolução
    # Ativado quando a imagem tem dimensões suficientes para conter micro-grãos
    # ══════════════════════════════════════════════════════════════════════════
    if w_img >= 640 and h_img >= 640:
        tops = compute_grid_coordinates(0, h_img, tile_size, stride)
        lefts = compute_grid_coordinates(0, w_img, tile_size, stride)

        tiles: list[NDArray[np.uint8]] = []
        offsets: list[tuple[int, int]] = []

        for top in tops:
            for left in lefts:
                patch = image_bgr[top : min(h_img, top + tile_size), left : min(w_img, left + tile_size)]
                ph, pw = patch.shape[:2]
                if ph < tile_size or pw < tile_size:
                    patch = cv2.copyMakeBorder(
                        patch, 0, tile_size - ph, 0, tile_size - pw, cv2.BORDER_REFLECT
                    )
                tiles.append(patch)
                offsets.append((left, top))

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

                    gx1 = min(w_img, max(0, bx1 + off_x))
                    gy1 = min(h_img, max(0, by1 + off_y))
                    gx2 = min(w_img, max(0, bx2 + off_x))
                    gy2 = min(h_img, max(0, by2 + off_y))

                    all_raw_boxes.append([gx1, gy1, gx2, gy2])
                    all_scores.append(score)
                    all_classes.append(cid)

    # NMS Global
    detections: list[dict[str, Any]] = []
    counts = {"verde": 0, "cereja_1": 0, "cereja_2": 0, "passa": 0, "seco": 0}

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
            # Pré-computa mapas de gradiente e HSV uma única vez
            maps = precompute_image_maps(image_bgr)
            classifier = ColorClassifier(color_ranges=DEFAULT_COLOR_RANGES)

            # Extração de características de cada caixa para Machine Learning
            features_list: list[list[float]] = []
            box_indices: list[int] = []

            for idx in indices.flatten():
                gx1, gy1, gx2, gy2 = map(int, all_raw_boxes[idx])
                cw, ch = gx2 - gx1, gy2 - gy1
                if cw < 6 or ch < 6:
                    continue

                x1_c, x2_c = max(0, gx1), min(w_img, gx2)
                y1_c, y2_c = max(0, gy1), min(h_img, gy2)

                feat = extract_grain_features(
                    maps["gray"][y1_c:y2_c, x1_c:x2_c],
                    maps["hsv"][y1_c:y2_c, x1_c:x2_c],
                    maps["gx"][y1_c:y2_c, x1_c:x2_c],
                    maps["gy"][y1_c:y2_c, x1_c:x2_c],
                    all_scores[idx],
                )
                if feat is not None:
                    features_list.append(feat)
                    box_indices.append(idx)

            # Classificação por Machine Learning: Grão de Café (True) vs Madeira/Fundo (False)
            is_coffee_list = classify_candidates(features_list)

            for i, is_coffee in enumerate(is_coffee_list):
                if not is_coffee:
                    # Descartado como madeira, toco, ripa ou chão pelo modelo ML
                    continue

                idx = box_indices[i]
                gx1, gy1, gx2, gy2 = all_raw_boxes[idx]
                cid = all_classes[idx]

                x1_c, x2_c = max(0, int(gx1)), min(w_img, int(gx2))
                y1_c, y2_c = max(0, int(gy1)), min(h_img, int(gy2))
                crop_grain = image_bgr[y1_c:y2_c, x1_c:x2_c]

                if crop_grain.size > 0:
                    hsv_grain = cv2.cvtColor(crop_grain, cv2.COLOR_BGR2HSV)
                    med_h = float(np.median(hsv_grain[:, :, 0]))
                    med_s = float(np.median(hsv_grain[:, :, 1]))
                    med_v = float(np.median(hsv_grain[:, :, 2]))

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

                cname = CLASS_NAMES.get(cid, "desconhecido")
                if cname in counts:
                    counts[cname] += 1

                detections.append({
                    "class_id": cid,
                    "class_name": cname,
                    "confidence": round(all_scores[idx], 3),
                    "bbox": [int(gx1), int(gy1), int(gx2), int(gy2)],
                    "center": [int((gx1 + gx2) / 2), int((gy1 + gy2) / 2)],
                })

    total_graos = len(detections)
    ratios = {
        k: round((v / total_graos * 100), 1) if total_graos > 0 else 0.0
        for k, v in counts.items()
    }

    # Recomendação agronômica: Ápice da qualidade está entre Cereja II e Passa
    pct_apice = ratios.get("cereja_2", 0.0) + ratios.get("passa", 0.0)
    pct_cereja_1 = ratios.get("cereja_1", 0.0)
    pct_verde = ratios.get("verde", 0.0)
    pct_seco = ratios.get("seco", 0.0)

    if pct_apice >= 50.0:
        recomendacao = (
            "Lote no Ápice da Qualidade! Predomínio de frutos em Cereja II e Passa, "
            "com máxima concentração de açúcares (grau Brix) e perfil ideal para cafés especiais."
        )
        status_colheita = "Ápice da Qualidade ★"
        badge_cor = "#10b981"
    elif (pct_apice + pct_cereja_1) >= 60.0:
        recomendacao = (
            "Excelente maturação. Alta concentração de frutos entre Cereja I e o Ápice (Cereja II e Passa). "
            "Ponto muito favorável para colheita."
        )
        status_colheita = "Excelente Ponto de Colheita"
        badge_cor = "#f59e0b"
    elif pct_verde > 35.0:
        recomendacao = (
            "Lote predominantemente imaturo (Verde). "
            "Recomenda-se aguardar evolução fisiológica para atingir o ápice de qualidade."
        )
        status_colheita = "Aguardar Maturação"
        badge_cor = "#3b82f6"
    else:
        recomendacao = (
            "Presença significativa de frutos secos. "
            "Recomenda-se catação/separação prévia para evitar perda sensorial na bebida."
        )
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
        "detections": detections,
        "recomendacao": recomendacao,
        "status_colheita": status_colheita,
        "badge_cor": badge_cor,
        "annotated_image_b64": f"data:image/jpeg;base64,{b64_image}",
        "dimensoes": {"largura": w_img, "altura": h_img},
    }
