"""
utils.py — Funções utilitárias compartilhadas para o pipeline do TCC.

Módulo contendo helpers reutilizáveis para manipulação de imagens,
desenho de bounding boxes, definição de cores por classe e
cálculos auxiliares de métricas.

Atualizado para suportar 5 estágios de maturação do Café Arara:
    0 — Verde (Imaturo)
    1 — Amarelo (Em Maturação / Pálido)
    2 — Cereja (Ponto Ideal / Amarelo Vibrante)
    3 — Passado (Seco Parcial / Ocre)
    4 — Seco (Preto / Marrom)

Autor: [Seu Nome]
Projeto: TCC — Visão Computacional Aplicada à Maturação do Café Arara
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

# ---------------------------------------------------------------------------
# Configuração de logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# Constantes — 5 Estágios de Maturação
# ═══════════════════════════════════════════════════════════════════════════

# Mapeamento de índice de classe → nome legível
CLASS_NAMES: dict[int, str] = {
    0: "verde",
    1: "amarelo",
    2: "cereja",
    3: "passado",
    4: "seco",
}

# Nomes para exibição amigável no dashboard
CLASS_DISPLAY_NAMES: dict[str, str] = {
    "verde":   "Verde (Imaturo)",
    "amarelo": "Amarelo (Em Maturação)",
    "cereja":  "Cereja Amarelo (Ponto Ideal)",
    "passado": "Passado (Seco Parcial)",
    "seco":    "Seco (Passa/Seco)",
}

# Cores BGR para desenho no OpenCV (uma por classe)
CLASS_COLORS_BGR_5: dict[int, tuple[int, int, int]] = {
    0: (0, 160, 0),        # Verde
    1: (0, 230, 230),      # Amarelo pálido (BGR)
    2: (0, 215, 255),      # Amarelo vivo/dourado (BGR)
    3: (15, 130, 180),     # Ocre/amarelo-escuro (BGR)
    4: (40, 40, 40),       # Preto/marrom-escuro
}

# Alias para compatibilidade
CLASS_COLORS_BGR = CLASS_COLORS_BGR_5

# Cores HEX para uso no Streamlit / HTML
CLASS_COLORS_HEX: dict[int, str] = {
    0: "#00A000",   # verde
    1: "#E6E600",   # amarelo pálido
    2: "#FFD700",   # cereja (amarelo vibrante / dourado)
    3: "#B4820F",   # passado (ocre)
    4: "#282828",   # seco (preto)
}

# Emojis para exibição nos cards
CLASS_EMOJIS: dict[int, str] = {
    0: "🟢",   # verde
    1: "🟡",   # amarelo
    2: "🌟",   # cereja (ponto ideal)
    3: "🟤",   # passado
    4: "⚫",   # seco
}

# Extensões de imagem suportadas
SUPPORTED_IMAGE_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


# ═══════════════════════════════════════════════════════════════════════════
# Funções de manipulação de imagem
# ═══════════════════════════════════════════════════════════════════════════

def load_image(image_path: str | Path) -> NDArray[np.uint8]:
    """Carrega uma imagem do disco usando OpenCV.

    Args:
        image_path: Caminho absoluto ou relativo para o arquivo de imagem.

    Returns:
        Array NumPy BGR da imagem carregada.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        ValueError: Se o arquivo não puder ser decodificado como imagem.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Imagem não encontrada: {path}")

    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Não foi possível decodificar a imagem: {path}")

    logger.info("Imagem carregada: %s (%dx%d)", path.name, image.shape[1], image.shape[0])
    return image


def bgr_to_rgb(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Converte uma imagem de BGR (OpenCV) para RGB (Pillow/Streamlit).

    Args:
        image: Array BGR.

    Returns:
        Array RGB.
    """
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def rgb_to_bgr(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Converte uma imagem de RGB para BGR.

    Args:
        image: Array RGB.

    Returns:
        Array BGR.
    """
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


# ═══════════════════════════════════════════════════════════════════════════
# Funções de desenho (Bounding Boxes)
# ═══════════════════════════════════════════════════════════════════════════

def draw_detections(
    image: NDArray[np.uint8],
    detections: list[dict[str, Any]],
    line_thickness: int = 2,
    font_scale: float = 0.5,
    style: str = "dots",
    dot_radius: int = 6,
    show_labels: bool = False,
) -> NDArray[np.uint8]:
    """Desenha detecções com renderização limpa e científica.

    Evita a poluição visual em massas densas de milhares de grãos:
      • "dots" (Padrão): Desenha círculos preenchidos compactos no centróide
        de cada fruto com borda fina de contraste. Não obstrui a imagem.
      • "boxes": Bounding boxes finas. Rótulos de texto só são desenhados
        se show_labels=True.
      • "density": Mapa translúcido destacando a maturação na massa de grãos.

    Args:
        image: Imagem BGR sobre a qual desenhar.
        detections: Lista de dicionários de detecção.
        line_thickness: Espessura de linha para boxes.
        font_scale: Escala da fonte (se labels ativos).
        style: "dots" | "boxes" | "density".
        dot_radius: Raio dos pontos no modo dots.
        show_labels: Se True, exibe rótulos de texto sobre caixas.

    Returns:
        Imagem anotada (cópia).
    """
    annotated = image.copy()

    if style == "density":
        overlay = image.copy()
        for det in detections:
            cid = det["class_id"]
            x1, y1, x2, y2 = det["bbox"]
            color = CLASS_COLORS_BGR_5.get(cid, (200, 200, 200))
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        return cv2.addWeighted(image, 0.45, overlay, 0.55, 0)

    if style == "dots":
        # Desenha círculos nítidos no centróide de cada fruto
        for det in detections:
            cid = det["class_id"]
            x1, y1, x2, y2 = det["bbox"]
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            color = CLASS_COLORS_BGR_5.get(cid, (200, 200, 200))

            # Ponto colorido com anel externo preto para contraste perfeito
            cv2.circle(annotated, (cx, cy), dot_radius, color, -1, cv2.LINE_AA)
            cv2.circle(annotated, (cx, cy), dot_radius + 1, (20, 20, 20), 1, cv2.LINE_AA)

        return annotated

    # Modo "boxes" (caixas limpas)
    for det in detections:
        cid = det["class_id"]
        class_name = det["class_name"]
        x1, y1, x2, y2 = det["bbox"]
        color = CLASS_COLORS_BGR_5.get(cid, (200, 200, 200))

        # Desenhar contorno da caixa
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, line_thickness)

        if show_labels:
            short_name = class_name.upper()
            label = f"{short_name}"
            (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
            cv2.rectangle(annotated, (x1, y1 - th - baseline - 2), (x1 + tw + 2, y1), color, cv2.FILLED)
            text_color = (0, 0, 0) if cid in (1, 2) else (255, 255, 255)
            cv2.putText(annotated, label, (x1 + 1, y1 - baseline - 1), cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_color, 1, cv2.LINE_AA)

    return annotated


def filter_detections_by_roi(
    detections: list[dict[str, Any]],
    img_shape: tuple[int, int, ...],
    top_pct: float = 0.0,
    bottom_pct: float = 0.22,
    left_pct: float = 0.02,
    right_pct: float = 0.02,
) -> list[dict[str, Any]]:
    """Filtra detecções para manter apenas frutos dentro da Região de Interesse (ROI).

    Descarta regiões fora da bandeja/terreiro (como o chão de lona, pés do operador,
    madeira de borda).

    Args:
        detections: Lista de detecções.
        img_shape: Shape da imagem (h, w, ...).
        top_pct: Percentual a descartar do topo.
        bottom_pct: Percentual a descartar da base (ex: 22% corta o chão e os sapatos).
        left_pct: Percentual a descartar da esquerda.
        right_pct: Percentual a descartar da direita.

    Returns:
        Lista filtrada de detecções contidas na área da bandeja.
    """
    h_img, w_img = img_shape[:2]
    y_min = int(h_img * top_pct)
    y_max = int(h_img * (1.0 - bottom_pct))
    x_min = int(w_img * left_pct)
    x_max = int(w_img * (1.0 - right_pct))

    filtered = []
    for d in detections:
        x1, y1, x2, y2 = d["bbox"]
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        if x_min <= cx <= x_max and y_min <= cy <= y_max:
            filtered.append(d)

    return filtered


# ═══════════════════════════════════════════════════════════════════════════
# Parsing de resultados YOLO
# ═══════════════════════════════════════════════════════════════════════════

def parse_yolo_results(results: Any) -> list[dict[str, Any]]:
    """Converte os resultados brutos do modelo YOLO em uma lista de dicionários.

    Args:
        results: Objeto ``ultralytics.engine.results.Results`` retornado
                 pela inferência do modelo.

    Returns:
        Lista de detecções, cada uma como dicionário com:
            - ``class_id``: int
            - ``class_name``: str
            - ``confidence``: float
            - ``bbox``: tuple[int, int, int, int]
    """
    detections: list[dict[str, Any]] = []

    for result in results:
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            continue

        for box in boxes:
            class_id = int(box.cls.item())
            confidence = float(box.conf.item())
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int).tolist()

            detections.append({
                "class_id": class_id,
                "class_name": CLASS_NAMES.get(class_id, f"classe_{class_id}"),
                "confidence": confidence,
                "bbox": (x1, y1, x2, y2),
            })

    logger.info("Total de detecções parseadas: %d", len(detections))
    return detections


# ═══════════════════════════════════════════════════════════════════════════
# Contagem e métricas
# ═══════════════════════════════════════════════════════════════════════════

def count_by_class(detections: list[dict[str, Any]]) -> dict[str, int]:
    """Conta o número de detecções por classe.

    Args:
        detections: Lista de detecções.

    Returns:
        Dicionário {nome_da_classe: contagem}.
    """
    counts: dict[str, int] = {name: 0 for name in CLASS_NAMES.values()}
    for det in detections:
        class_name = det["class_name"]
        if class_name in counts:
            counts[class_name] += 1
        else:
            counts[class_name] = counts.get(class_name, 0) + 1
    return counts


def compute_maturity_ratio(counts: dict[str, int]) -> dict[str, float]:
    """Calcula a proporção percentual de cada classe em relação ao total.

    Args:
        counts: Dicionário de contagens por classe.

    Returns:
        Dicionário {nome_da_classe: percentual (0–100)}.
    """
    total = sum(counts.values())
    if total == 0:
        return {name: 0.0 for name in counts}
    return {name: round((count / total) * 100, 1) for name, count in counts.items()}


# ═══════════════════════════════════════════════════════════════════════════
# Validação de arquivos
# ═══════════════════════════════════════════════════════════════════════════

def is_valid_image(file_path: str | Path) -> bool:
    """Verifica se um arquivo possui extensão de imagem suportada.

    Args:
        file_path: Caminho do arquivo.

    Returns:
        ``True`` se a extensão for suportada.
    """
    return Path(file_path).suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def find_images(directory: str | Path) -> list[Path]:
    """Lista todos os arquivos de imagem em um diretório.

    Args:
        directory: Caminho do diretório a ser escaneado.

    Returns:
        Lista de objetos ``Path`` com as imagens encontradas (ordenada).
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Diretório não encontrado: {dir_path}")

    images = sorted(
        p for p in dir_path.iterdir()
        if p.is_file() and is_valid_image(p)
    )
    logger.info("Encontradas %d imagens em %s", len(images), dir_path)
    return images
