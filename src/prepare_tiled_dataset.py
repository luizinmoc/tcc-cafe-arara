#!/usr/bin/env python3
"""
prepare_tiled_dataset.py — Prepara dataset de patches 640x640 em escala real (1:1)
a partir de todas as 15 imagens do Google Drive.

Como as imagens 4K possuem grãos de ~15 a 25 pixels, o treinamento em patches
de 640x640 preserva a escala original dos grãos, permitindo que a rede neural
YOLOv8 convirja e detecte centenas de frutos com alta acurácia.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
TRAIN_IMG = PROJECT_ROOT / "data" / "images" / "train"
VAL_IMG = PROJECT_ROOT / "data" / "images" / "val"
TRAIN_LBL = PROJECT_ROOT / "data" / "labels" / "train"
VAL_LBL = PROJECT_ROOT / "data" / "labels" / "val"

import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.color_classifier import ColorClassifier, DEFAULT_COLOR_RANGES

def main():
    # Limpar diretórios de treino e validação
    for d in [TRAIN_IMG, VAL_IMG, TRAIN_LBL, VAL_LBL]:
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*.*"):
            f.unlink()

    raw_images = sorted([f for f in RAW_DIR.glob("*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png"]])
    print(f"Encontradas {len(raw_images)} imagens brutas no Google Drive.")

    classifier = ColorClassifier(color_ranges=DEFAULT_COLOR_RANGES)

    tile_size = 640
    step_y = 500
    step_x = 500
    half_box = 11  # raio estimado do fruto (~22px de diâmetro)

    total_tiles_train = 0
    total_tiles_val = 0
    total_annotations = 0

    for img_idx, img_path in enumerate(raw_images, 1):
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        h_img, w_img = img.shape[:2]

        # ROI da bandeja (evita bordas de madeira e chão)
        y_min = int(h_img * 0.10)
        y_max = int(h_img * 0.88)
        x_min = int(w_img * 0.08)
        x_max = int(w_img * 0.92)

        # Determinar posições dos tiles
        tile_count_in_image = 0
        for top in range(y_min, y_max - tile_size, step_y):
            for left in range(x_min, x_max - tile_size, step_x):
                bottom = top + tile_size
                right = left + tile_size

                patch = img[top:bottom, left:right]
                patch_hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)

                # Detecção de centros de frutos no patch
                gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                cl = clahe.apply(gray)
                blurred = cv2.GaussianBlur(cl, (9, 9), 0)

                # Máximos locais (grãos de café)
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19))
                dilated = cv2.dilate(blurred, kernel)
                local_max = (blurred == dilated) & (blurred > 45)

                y_pts, x_pts = np.where(local_max)
                if len(y_pts) < 10:
                    continue  # patch vazio ou fora de foco

                # Amostrar até 120 frutos mais representativos por tile para manter treino rápido
                if len(y_pts) > 120:
                    indices = np.linspace(0, len(y_pts) - 1, 120, dtype=int)
                    y_pts = y_pts[indices]
                    x_pts = x_pts[indices]

                annotations = []
                for py, px in zip(y_pts, x_pts):
                    # Evitar borda imediata do tile
                    if py < half_box or py > tile_size - half_box or px < half_box or px > tile_size - half_box:
                        continue

                    # Patch HSV local do grão
                    hsv_sub = patch_hsv[max(0, py - 5):min(tile_size, py + 6), max(0, px - 5):min(tile_size, px + 6)]
                    if hsv_sub.size == 0:
                        continue

                    med_h = np.median(hsv_sub[:, :, 0])
                    med_s = np.median(hsv_sub[:, :, 1])
                    med_v = np.median(hsv_sub[:, :, 2])

                    matched_class = -1
                    for cr in classifier.color_ranges:
                        if cr.h_min <= med_h <= cr.h_max and cr.s_min <= med_s <= cr.s_max and cr.v_min <= med_v <= cr.v_max:
                            matched_class = cr.class_id
                            break

                    if matched_class < 0:
                        diffs = [abs(cr.h_min + (cr.h_max - cr.h_min)/2 - med_h) for cr in classifier.color_ranges]
                        matched_class = int(np.argmin(diffs))

                    # Coordenadas YOLO relativas ao tile 640x640
                    x_center = px / float(tile_size)
                    y_center = py / float(tile_size)
                    w_box = (half_box * 2) / float(tile_size)
                    h_box = (half_box * 2) / float(tile_size)

                    annotations.append(f"{matched_class} {x_center:.6f} {y_center:.6f} {w_box:.6f} {h_box:.6f}")

                if len(annotations) < 10:
                    continue

                tile_name = f"{img_path.stem}_tile_{tile_count_in_image:02d}"
                tile_count_in_image += 1

                # Divisão 80% treino / 20% validação
                is_val = (tile_count_in_image % 5 == 0)
                target_img_dir = VAL_IMG if is_val else TRAIN_IMG
                target_lbl_dir = VAL_LBL if is_val else TRAIN_LBL

                cv2.imwrite(str(target_img_dir / f"{tile_name}.jpg"), patch, [cv2.IMWRITE_JPEG_QUALITY, 92])
                (target_lbl_dir / f"{tile_name}.txt").write_text("\n".join(annotations) + "\n", encoding="utf-8")

                if is_val:
                    total_tiles_val += 1
                else:
                    total_tiles_train += 1
                total_annotations += len(annotations)

        print(f"[{img_idx}/{len(raw_images)}] {img_path.name}: {tile_count_in_image} tiles de 640x640 gerados.")

    print("\n" + "=" * 60)
    print(f"RESUMO DO DATASET TILED (ESCALA REAL 1:1):")
    print(f"Tiles de Treino:    {total_tiles_train}")
    print(f"Tiles de Validacao: {total_tiles_val}")
    print(f"Total de Anotacoes: {total_annotations:,}")
    print("=" * 60)

if __name__ == "__main__":
    main()
