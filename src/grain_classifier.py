#!/usr/bin/env python3
"""
grain_classifier.py — Classificador Machine Learning de Fruto de Café vs Madeira/Fundo.

Diferencia com precisão um grão de café real de tocos de madeira, ripas,
vigas, fita métrica e chão de asfalto, baseado nas propriedades intrínsecas
de um fruto esférico 3D (geometria, gradiente radial convergente, sombreamento
convexo de bordas e assinatura espectral cromática do Café Arara).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import joblib
import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import ExtraTreesClassifier

logger = logging.getLogger("grain_classifier")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "weights" / "grain_classifier.joblib"

_CACHED_CLASSIFIER: ExtraTreesClassifier | None = None
_CACHED_MTIME: float = 0.0


def get_grain_classifier() -> ExtraTreesClassifier:
    """Carrega o modelo ExtraTrees treinado para diferenciar grão de café vs madeira."""
    global _CACHED_CLASSIFIER, _CACHED_MTIME

    if not MODEL_PATH.exists():
        logger.warning("Modelo grain_classifier.joblib não encontrado em %s. Usando fallback heurístico.", MODEL_PATH)
        return None

    current_mtime = MODEL_PATH.stat().st_mtime
    if _CACHED_CLASSIFIER is None or current_mtime != _CACHED_MTIME:
        logger.info("Carregando Classificador de Grão vs Madeira: %s", MODEL_PATH)
        _CACHED_CLASSIFIER = joblib.load(MODEL_PATH)
        _CACHED_MTIME = current_mtime

    return _CACHED_CLASSIFIER


def precompute_image_maps(image_bgr: NDArray[np.uint8]) -> dict[str, NDArray[Any]]:
    """Pré-computa mapas de cinza, HSV e gradientes Sobel para extração instantânea O(1)."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    return {"gray": gray, "hsv": hsv, "gx": gx, "gy": gy}


def extract_grain_features(
    c_gray: NDArray[np.uint8],
    c_hsv: NDArray[np.uint8],
    c_gx: NDArray[np.float64],
    c_gy: NDArray[np.float64],
    conf: float,
) -> list[float] | None:
    """Extrai vetor de características 3D, espectrais e morfológicas de um fruto candidato."""
    ch, cw = c_gray.shape[:2]
    if ch < 6 or cw < 6:
        return None

    ar = cw / float(ch)
    area = cw * ch

    # Estatísticas HSV de maturação Arara
    s_med = float(np.median(c_hsv[:, :, 1]))
    s_std = float(np.std(c_hsv[:, :, 1]))
    v_med = float(np.median(c_hsv[:, :, 2]))
    v_std = float(np.std(c_hsv[:, :, 2]))
    h_med = float(np.median(c_hsv[:, :, 0]))

    # Curvatura volumétrica 3D: centro do domo do fruto é mais brilhante que as bordas
    ch1, ch2 = max(1, int(0.25 * ch)), min(ch - 1, int(0.75 * ch))
    cw1, cw2 = max(1, int(0.25 * cw)), min(cw - 1, int(0.75 * cw))
    center_v = np.mean(c_gray[ch1:ch2, cw1:cw2]) if ch2 > ch1 and cw2 > cw1 else float(np.mean(c_gray))

    top_v = float(np.mean(c_gray[: max(1, int(0.2 * ch)), :]))
    bot_v = float(np.mean(c_gray[min(ch - 1, int(0.8 * ch)) :, :]))
    left_v = float(np.mean(c_gray[:, : max(1, int(0.2 * cw))]))
    right_v = float(np.mean(c_gray[:, min(cw - 1, int(0.8 * cw)) :]))

    # Contrastes centro-borda
    c2b = center_v - (top_v + bot_v + left_v + right_v) / 4.0
    min_d = min(center_v - top_v, center_v - bot_v, center_v - left_v, center_v - right_v)
    max_d = max(center_v - top_v, center_v - bot_v, center_v - left_v, center_v - right_v)

    # Gradiente radial convergente esférico (vetores apontam para o centro)
    rad = (np.mean(c_gx[:, : int(0.35 * cw)]) - np.mean(c_gx[:, int(0.65 * cw) :])) + (
        np.mean(c_gy[: int(0.35 * ch), :]) - np.mean(c_gy[int(0.65 * ch) :, :])
    )

    # Variação das bordas (sulcos de contato entre grãos vs madeira contínua)
    border_pixels = np.concatenate([c_gray[0, :], c_gray[-1, :], c_gray[:, 0], c_gray[:, -1]])
    border_std = float(np.std(border_pixels))

    # Variância Laplaciana (nitidez de textura)
    lap_v = float(cv2.Laplacian(c_gray, cv2.CV_64F).var())

    return [c2b, min_d, max_d, float(rad), s_med, s_std, v_med, v_std, h_med, ar, float(area), border_std, lap_v, conf]


def is_grain_heuristic(
    crop_gray: NDArray[np.uint8],
    crop_hsv: NDArray[np.uint8],
    crop_gx: NDArray[np.float64],
    crop_gy: NDArray[np.float64],
) -> bool:
    """Validador físico-geométrico de fruto esférico 3D (usado como fallback)."""
    ch, cw = crop_gray.shape[:2]
    if ch < 6 or cw < 6:
        return False

    ar = cw / float(ch)
    if ar < 0.55 or ar > 1.80:
        return False

    s_med = float(np.median(crop_hsv[:, :, 1]))
    v_med = float(np.median(crop_hsv[:, :, 2]))

    # Rejeição imediata de asfalto cinza e madeira seca desbotada
    if s_med < 28.0 and v_med > 35.0:
        return False

    center_v = np.mean(crop_gray[int(0.25 * ch) : int(0.75 * ch), int(0.25 * cw) : int(0.75 * cw)])
    top_v = np.mean(crop_gray[: max(1, int(0.2 * ch)), :])
    bot_v = np.mean(crop_gray[min(ch - 1, int(0.8 * ch)) :, :])
    left_v = np.mean(crop_gray[:, : max(1, int(0.2 * cw))])
    right_v = np.mean(crop_gray[:, min(cw - 1, int(0.8 * cw)) :])
    c2b = center_v - (top_v + bot_v + left_v + right_v) / 4.0

    rad = (np.mean(crop_gx[:, : int(0.35 * cw)]) - np.mean(crop_gx[:, int(0.65 * cw) :])) + (
        np.mean(crop_gy[: int(0.35 * ch), :]) - np.mean(crop_gy[int(0.65 * ch) :, :])
    )

    # Frutos reais possuem relevo 3D evidente (c2b > 24 ou gradiente radial convergente > 45)
    return bool(c2b >= 24.0 or rad >= 45.0)


def classify_candidates(
    crops_features: list[list[float]],
) -> list[bool]:
    """Classifica um lote de características candidatas como Grão de Café (True) ou Madeira/Fundo (False)."""
    clf = get_grain_classifier()
    if clf is None or len(crops_features) == 0:
        # Fallback heurístico
        return [bool(f[0] >= 24.0 or f[3] >= 45.0) for f in crops_features]

    X = np.array(crops_features)
    # Probabilidade de ser grão de café (classe 1)
    probs = clf.predict_proba(X)
    is_coffee = probs[:, 1] >= 0.50

    return is_coffee.tolist()
