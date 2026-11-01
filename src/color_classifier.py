"""
color_classifier.py — Classificação por Faixa de Cor HSV.

Módulo responsável pela classificação dos frutos de café Arara
com base na análise de cor da região detectada (bounding box),
utilizando o espaço de cores HSV (Hue, Saturation, Value).

As 5 faixas de maturação são definidas por intervalos de HSV
calibrados a partir do guia visual de cores da variedade Arara:

    1. Verde (Imaturo)         → Frutos duros, verdes
    2. Amarelo Pálido          → Início da mudança de cor
    3. Cereja Amarelo          → Ponto ideal de colheita (amarelo vibrante)
    4. Passado (Amarelo Ocre)  → Frutos murchando, cor escurecendo
    5. Seco (Marrom/Preto)     → Casca preta enrugada

Autor: [Seu Nome]
Projeto: TCC — Visão Computacional Aplicada à Maturação do Café Arara
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Estrutura de dados para faixa de cor
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ColorRange:
    """Define uma faixa de cor HSV para uma classe de maturação.

    OpenCV usa: H [0–179], S [0–255], V [0–255].

    Attributes:
        class_id: Índice numérico da classe.
        class_name: Nome legível da classe.
        h_min: Hue mínimo.
        h_max: Hue máximo.
        s_min: Saturation mínima.
        s_max: Saturation máxima.
        v_min: Value mínimo.
        v_max: Value máximo.
        description: Descrição do estágio de maturação.
    """

    class_id: int
    class_name: str
    h_min: int
    h_max: int
    s_min: int
    s_max: int
    v_min: int
    v_max: int
    description: str = ""

    @property
    def lower(self) -> NDArray[np.uint8]:
        """Limite inferior HSV como array NumPy."""
        return np.array([self.h_min, self.s_min, self.v_min], dtype=np.uint8)

    @property
    def upper(self) -> NDArray[np.uint8]:
        """Limite superior HSV como array NumPy."""
        return np.array([self.h_max, self.s_max, self.v_max], dtype=np.uint8)

    def __str__(self) -> str:
        return (
            f"{self.class_name}: "
            f"H[{self.h_min}–{self.h_max}] "
            f"S[{self.s_min}–{self.s_max}] "
            f"V[{self.v_min}–{self.v_max}]"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Faixas de cor padrão para Café Arara (calibradas pelo guia visual)
# ═══════════════════════════════════════════════════════════════════════════
#
# ┌──────────────────┬───────────────────────────────────────────────────┐
# │ Estágio          │ Descrição de Cor                                 │
# ├──────────────────┼───────────────────────────────────────────────────┤
# │ 1. Verde         │ Verde intenso → verde claro                      │
# │ 2. Amarelo       │ Verde-amarelado → amarelo pálido (transição)     │
# │ 3. Cereja        │ Amarelo vivo e brilhante (ponto ideal)           │
# │ 4. Passado       │ Amarelo-escuro → ocre/amarronzado                │
# │ 5. Seco          │ Marrom-escuro → preto (casca enrugada)           │
# └──────────────────┴───────────────────────────────────────────────────┘
#
# NOTA: Estes valores são pontos de partida. Ajuste fino deve ser feito
# com imagens reais do seu dataset. Use a função `calibrate_preview()`
# do dashboard para visualizar a máscara de cada faixa.

DEFAULT_COLOR_RANGES: list[ColorRange] = [
    ColorRange(
        class_id=0,
        class_name="verde",
        h_min=35, h_max=85,
        s_min=40, s_max=255,
        v_min=30, v_max=255,
        description="Frutos verdes, duros e sem maturação",
    ),
    ColorRange(
        class_id=1,
        class_name="amarelo",
        h_min=22, h_max=34,
        s_min=40, s_max=170,
        v_min=130, v_max=255,
        description="Início da mudança de cor — verde para amarelo claro",
    ),
    ColorRange(
        class_id=2,
        class_name="cereja",
        h_min=18, h_max=33,
        s_min=150, s_max=255,
        v_min=150, v_max=255,
        description="Ponto ideal de colheita — amarelo vivo e brilhante",
    ),
    ColorRange(
        class_id=3,
        class_name="passado",
        h_min=8, h_max=24,
        s_min=50, s_max=200,
        v_min=40, v_max=150,
        description="Frutos murchando — cor amarela-escura / ocre",
    ),
    ColorRange(
        class_id=4,
        class_name="seco",
        h_min=0, h_max=179,
        s_min=0, s_max=120,
        v_min=0, v_max=75,
        description="Frutos secos — casca preta enrugada",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# Classificador por Cor
# ═══════════════════════════════════════════════════════════════════════════

class ColorClassifier:
    """Classifica regiões de imagem por faixa de cor HSV.

    O classificador recebe uma região (crop) da imagem correspondente
    a um fruto detectado pelo YOLO e determina o estágio de maturação
    com base na cor predominante.

    Attributes:
        color_ranges: Lista de faixas de cor HSV para cada classe.
        min_pixel_ratio: Fração mínima de pixels que devem pertencer
                         a uma faixa para que a classificação seja válida.
    """

    def __init__(
        self,
        color_ranges: list[ColorRange] | None = None,
        min_pixel_ratio: float = 0.05,
    ) -> None:
        """Inicializa o classificador.

        Args:
            color_ranges: Faixas de cor customizadas. Se ``None``,
                          usa ``DEFAULT_COLOR_RANGES``.
            min_pixel_ratio: Fração mínima de pixels para uma
                             classificação válida (padrão: 5%).
        """
        self.color_ranges = color_ranges or DEFAULT_COLOR_RANGES
        self.min_pixel_ratio = min_pixel_ratio

        logger.info(
            "ColorClassifier inicializado com %d faixas de cor",
            len(self.color_ranges),
        )

    def _extract_roi(
        self,
        image_bgr: NDArray[np.uint8],
        bbox: tuple[int, int, int, int],
        margin_pct: float = 0.1,
    ) -> NDArray[np.uint8]:
        """Extrai a região de interesse (ROI) da imagem com margem interna.

        Uma margem interna (shrink) é aplicada para evitar pixels de borda
        que podem pertencer ao fundo ou a outros frutos.

        Args:
            image_bgr: Imagem completa em BGR.
            bbox: Bounding box ``(x1, y1, x2, y2)``.
            margin_pct: Percentual de margem interna (padrão: 10%).

        Returns:
            Crop BGR da região de interesse.
        """
        x1, y1, x2, y2 = bbox
        w = x2 - x1
        h = y2 - y1

        # Margem interna para pegar a região central do fruto
        mx = int(w * margin_pct)
        my = int(h * margin_pct)

        x1_inner = max(x1 + mx, 0)
        y1_inner = max(y1 + my, 0)
        x2_inner = min(x2 - mx, image_bgr.shape[1])
        y2_inner = min(y2 - my, image_bgr.shape[0])

        return image_bgr[y1_inner:y2_inner, x1_inner:x2_inner]

    def classify_roi(
        self,
        roi_bgr: NDArray[np.uint8],
    ) -> dict[str, Any]:
        """Classifica uma região (crop) por cor HSV.

        Calcula a fração de pixels em cada faixa de cor e retorna
        a classe com maior cobertura.

        Args:
            roi_bgr: Região da imagem em BGR.

        Returns:
            Dicionário com:
                - ``class_id``: int
                - ``class_name``: str
                - ``confidence``: float (fração de pixels na faixa vencedora)
                - ``scores``: dict[str, float] (cobertura de todas as faixas)
                - ``dominant_hsv``: tuple[int, int, int] (mediana HSV)
        """
        if roi_bgr.size == 0:
            return {
                "class_id": -1,
                "class_name": "indefinido",
                "confidence": 0.0,
                "scores": {},
                "dominant_hsv": (0, 0, 0),
            }

        # Converter para HSV
        roi_hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        total_pixels = roi_hsv.shape[0] * roi_hsv.shape[1]

        # HSV mediano (cor dominante)
        h_median = int(np.median(roi_hsv[:, :, 0]))
        s_median = int(np.median(roi_hsv[:, :, 1]))
        v_median = int(np.median(roi_hsv[:, :, 2]))

        # Calcular cobertura de cada faixa
        scores: dict[str, float] = {}
        best_class_id = -1
        best_class_name = "indefinido"
        best_score = 0.0

        for cr in self.color_ranges:
            mask = cv2.inRange(roi_hsv, cr.lower, cr.upper)
            pixel_count = cv2.countNonZero(mask)
            ratio = pixel_count / total_pixels

            scores[cr.class_name] = round(ratio, 4)

            if ratio > best_score:
                best_score = ratio
                best_class_id = cr.class_id
                best_class_name = cr.class_name

        # Se nenhuma faixa atingiu o mínimo, marcar como indefinido
        if best_score < self.min_pixel_ratio:
            best_class_id = -1
            best_class_name = "indefinido"

        return {
            "class_id": best_class_id,
            "class_name": best_class_name,
            "confidence": round(best_score, 4),
            "scores": scores,
            "dominant_hsv": (h_median, s_median, v_median),
        }

    def classify_detection(
        self,
        image_bgr: NDArray[np.uint8],
        bbox: tuple[int, int, int, int],
        margin_pct: float = 0.1,
    ) -> dict[str, Any]:
        """Classifica um fruto detectado com base na sua região na imagem.

        Args:
            image_bgr: Imagem completa em BGR.
            bbox: Bounding box ``(x1, y1, x2, y2)`` do fruto.
            margin_pct: Margem interna para crop (padrão: 10%).

        Returns:
            Resultado da classificação (mesma estrutura de ``classify_roi``).
        """
        roi = self._extract_roi(image_bgr, bbox, margin_pct)
        return self.classify_roi(roi)

    def reclassify_detections(
        self,
        image_bgr: NDArray[np.uint8],
        detections: list[dict[str, Any]],
        margin_pct: float = 0.1,
    ) -> list[dict[str, Any]]:
        """Reclassifica todas as detecções do YOLO usando análise de cor.

        Para cada detecção, extrai o crop da bounding box, analisa a cor
        predominante e atribui a classe de maturação baseada nas faixas HSV.

        Args:
            image_bgr: Imagem completa em BGR.
            detections: Lista de detecções do YOLO (com ``bbox``).
            margin_pct: Margem interna para crop.

        Returns:
            Nova lista de detecções com campos adicionais:
                - ``color_class_id``: Classe pelo classificador de cor.
                - ``color_class_name``: Nome da classe por cor.
                - ``color_confidence``: Confiança da classificação por cor.
                - ``color_scores``: Cobertura de todas as faixas.
                - ``dominant_hsv``: HSV mediano do crop.
        """
        enriched: list[dict[str, Any]] = []

        for det in detections:
            bbox = det["bbox"]
            color_result = self.classify_detection(image_bgr, bbox, margin_pct)

            enriched_det = {
                **det,
                # Substituir classe YOLO pela classe de cor
                "class_id": color_result["class_id"],
                "class_name": color_result["class_name"],
                # Manter confiança do YOLO como detecção, adicionar cor
                "yolo_confidence": det["confidence"],
                "color_confidence": color_result["confidence"],
                "color_scores": color_result["scores"],
                "dominant_hsv": color_result["dominant_hsv"],
            }
            enriched.append(enriched_det)

        logger.info(
            "Reclassificação por cor concluída — %d detecções processadas",
            len(enriched),
        )
        return enriched

    def generate_color_mask(
        self,
        image_bgr: NDArray[np.uint8],
        class_id: int,
    ) -> NDArray[np.uint8]:
        """Gera máscara binária para uma faixa de cor específica.

        Útil para calibração e visualização — mostra quais pixels
        da imagem se enquadram na faixa de cor de uma classe.

        Args:
            image_bgr: Imagem completa em BGR.
            class_id: ID da classe para gerar a máscara.

        Returns:
            Máscara binária (0 ou 255) do mesmo tamanho da imagem.

        Raises:
            ValueError: Se o ``class_id`` não existir nas faixas.
        """
        cr = next(
            (r for r in self.color_ranges if r.class_id == class_id),
            None,
        )
        if cr is None:
            raise ValueError(f"class_id {class_id} não encontrado nas faixas de cor")

        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        return cv2.inRange(hsv, cr.lower, cr.upper)

    def generate_all_masks_overlay(
        self,
        image_bgr: NDArray[np.uint8],
        alpha: float = 0.5,
    ) -> NDArray[np.uint8]:
        """Gera uma sobreposição colorida de todas as faixas sobre a imagem.

        Cada faixa de cor é pintada com sua cor representativa sobre a
        imagem original, útil para calibração visual.

        Args:
            image_bgr: Imagem completa em BGR.
            alpha: Transparência da sobreposição (0 = invisível, 1 = opaco).

        Returns:
            Imagem BGR com sobreposição colorida.
        """
        from src.utils import CLASS_COLORS_BGR_5

        overlay = image_bgr.copy()
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)

        for cr in self.color_ranges:
            mask = cv2.inRange(hsv, cr.lower, cr.upper)
            color = CLASS_COLORS_BGR_5.get(cr.class_id, (255, 255, 255))
            overlay[mask > 0] = color

        blended = cv2.addWeighted(image_bgr, 1 - alpha, overlay, alpha, 0)
        return blended


# ═══════════════════════════════════════════════════════════════════════════
# Funções utilitárias
# ═══════════════════════════════════════════════════════════════════════════

def get_default_classifier() -> ColorClassifier:
    """Retorna uma instância do classificador com as faixas padrão.

    Returns:
        Instância de ``ColorClassifier`` configurada.
    """
    return ColorClassifier(color_ranges=DEFAULT_COLOR_RANGES)


def color_ranges_to_dict(ranges: list[ColorRange]) -> list[dict[str, Any]]:
    """Converte lista de ``ColorRange`` para dicionários serializáveis.

    Args:
        ranges: Lista de faixas de cor.

    Returns:
        Lista de dicionários.
    """
    return [
        {
            "class_id": cr.class_id,
            "class_name": cr.class_name,
            "h_min": cr.h_min,
            "h_max": cr.h_max,
            "s_min": cr.s_min,
            "s_max": cr.s_max,
            "v_min": cr.v_min,
            "v_max": cr.v_max,
            "description": cr.description,
        }
        for cr in ranges
    ]


def dict_to_color_ranges(data: list[dict[str, Any]]) -> list[ColorRange]:
    """Converte dicionários de volta para objetos ``ColorRange``.

    Args:
        data: Lista de dicionários com chaves de ``ColorRange``.

    Returns:
        Lista de ``ColorRange``.
    """
    return [ColorRange(**d) for d in data]
