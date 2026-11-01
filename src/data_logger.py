#!/usr/bin/env python3
"""
data_logger.py — Gerenciador da Base de Dados Compactada do TCC.

Salva e arquiva automaticamente todas as rodadas de contagem da rede neural
Deep Learning em um único arquivo compactado ZIP (outputs/base_dados_tcc.zip),
evitando consumo excessivo de disco e mantendo um histórico auditável para a pesquisa.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
from numpy.typing import NDArray

logger = logging.getLogger("data_logger")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
ZIP_DATABASE_PATH = OUTPUTS_DIR / "base_dados_tcc.zip"
CSV_FILENAME = "historico_contagens_tcc.csv"
JSON_FILENAME = "historico_contagens_tcc.json"

CSV_COLUMNS = [
    "data_hora",
    "imagem",
    "total_graos",
    "verde",
    "amarelo",
    "cereja_ideal",
    "passado",
    "seco",
    "pct_verde",
    "pct_amarelo",
    "pct_cereja_ideal",
    "pct_passado",
    "pct_seco",
    "modelo",
    "confianca_minima",
    "arquivo_imagem_anotada",
]


def _ensure_zip_structure() -> None:
    """Garante a existência do diretório outputs e do arquivo ZIP com cabeçalho CSV."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    if not ZIP_DATABASE_PATH.exists():
        with zipfile.ZipFile(ZIP_DATABASE_PATH, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            header_csv = io.StringIO()
            writer = csv.writer(header_csv)
            writer.writerow(CSV_COLUMNS)
            zf.writestr(CSV_FILENAME, header_csv.getvalue().encode("utf-8"))
            zf.writestr(JSON_FILENAME, json.dumps([], indent=2).encode("utf-8"))


def record_count_session(
    image_name: str,
    counts: dict[str, int],
    ratios: dict[str, float],
    annotated_bgr: NDArray[np.uint8] | None = None,
    model_name: str = "YOLOv8 Deep Learning",
    confidence: float = 0.25,
) -> dict[str, Any]:
    """Registra uma rodada de contagem dentro do arquivo compactado ZIP do TCC.

    Args:
        image_name: Nome do arquivo de imagem processado.
        counts: Dicionário com a contagem de cada classe.
        ratios: Dicionário com os percentuais de cada classe.
        annotated_bgr: Imagem anotada resultante (opcional, salva comprimida).
        model_name: Identificador da rede neural.
        confidence: Limiar de confiança utilizado.

    Returns:
        Dicionário com os dados salvos e metadados do arquivo compactado.
    """
    _ensure_zip_structure()

    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    total_graos = sum(counts.values())

    clean_img_stem = Path(image_name).stem
    annotated_filename = f"anotadas/{clean_img_stem}_{timestamp_id}.jpg"

    row_dict = {
        "data_hora": timestamp_str,
        "imagem": image_name,
        "total_graos": total_graos,
        "verde": counts.get("verde", 0),
        "amarelo": counts.get("amarelo", 0),
        "cereja_ideal": counts.get("cereja", 0),
        "passado": counts.get("passado", 0),
        "seco": counts.get("seco", 0),
        "pct_verde": f"{ratios.get('verde', 0.0):.1f}",
        "pct_amarelo": f"{ratios.get('amarelo', 0.0):.1f}",
        "pct_cereja_ideal": f"{ratios.get('cereja', 0.0):.1f}",
        "pct_passado": f"{ratios.get('passado', 0.0):.1f}",
        "pct_seco": f"{ratios.get('seco', 0.0):.1f}",
        "modelo": model_name,
        "confianca_minima": f"{confidence:.2f}",
        "arquivo_imagem_anotada": annotated_filename if annotated_bgr is not None else "N/A",
    }

    # Ler dados existentes do ZIP
    existing_records = []
    with zipfile.ZipFile(ZIP_DATABASE_PATH, mode="r") as zf:
        if JSON_FILENAME in zf.namelist():
            try:
                existing_records = json.loads(zf.read(JSON_FILENAME).decode("utf-8"))
            except Exception:
                existing_records = []

    existing_records.append(row_dict)

    # Comprimir imagem em JPEG com compressão otimizada
    img_bytes = None
    if annotated_bgr is not None:
        # Redimensionar suavemente se for 4K para ocupar menos de 300KB
        h, w = annotated_bgr.shape[:2]
        max_dim = 1600
        if max(h, w) > max_dim:
            scale = max_dim / float(max(h, w))
            resized = cv2.resize(annotated_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        else:
            resized = annotated_bgr
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 82]
        _, img_buf = cv2.imencode(".jpg", resized, encode_params)
        img_bytes = img_buf.tobytes()

    # Re-escrever ZIP atualizado
    # Ler todos os arquivos existentes exceto os que vamos atualizar
    all_files_data: dict[str, bytes] = {}
    with zipfile.ZipFile(ZIP_DATABASE_PATH, mode="r") as zf:
        for item in zf.infolist():
            if item.filename not in [CSV_FILENAME, JSON_FILENAME]:
                all_files_data[item.filename] = zf.read(item.filename)

    # Novo CSV
    df = pd.DataFrame(existing_records)
    csv_buf = io.StringIO()
    df.to_csv(csv_buf, index=False)
    csv_bytes = csv_buf.getvalue().encode("utf-8")
    json_bytes = json.dumps(existing_records, indent=2, ensure_ascii=False).encode("utf-8")

    all_files_data[CSV_FILENAME] = csv_bytes
    all_files_data[JSON_FILENAME] = json_bytes
    if img_bytes is not None:
        all_files_data[annotated_filename] = img_bytes

    with zipfile.ZipFile(ZIP_DATABASE_PATH, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname, fbytes in all_files_data.items():
            zf.writestr(fname, fbytes)

    zip_size_kb = ZIP_DATABASE_PATH.stat().st_size / 1024.0

    return {
        "registro": row_dict,
        "total_registros": len(existing_records),
        "zip_path": str(ZIP_DATABASE_PATH),
        "zip_size_kb": zip_size_kb,
    }


def get_archive_dataframe() -> pd.DataFrame:
    """Lê o histórico tabular consolidado de dentro do arquivo compactado ZIP."""
    _ensure_zip_structure()
    with zipfile.ZipFile(ZIP_DATABASE_PATH, mode="r") as zf:
        if CSV_FILENAME in zf.namelist():
            csv_data = zf.read(CSV_FILENAME).decode("utf-8")
            return pd.read_csv(io.StringIO(csv_data))
    return pd.DataFrame(columns=CSV_COLUMNS)


def get_archive_bytes() -> bytes:
    """Retorna os bytes do arquivo compactado para download direto."""
    _ensure_zip_structure()
    return ZIP_DATABASE_PATH.read_bytes()


def get_archive_info() -> dict[str, Any]:
    """Retorna informações estatísticas da base de dados compactada."""
    _ensure_zip_structure()
    size_bytes = ZIP_DATABASE_PATH.stat().st_size
    with zipfile.ZipFile(ZIP_DATABASE_PATH, mode="r") as zf:
        names = zf.namelist()
        num_images = sum(1 for n in names if n.startswith("anotadas/"))
        df = get_archive_dataframe()
    return {
        "num_rodadas": len(df),
        "num_imagens_salvas": num_images,
        "tamanho_kb": size_bytes / 1024.0,
        "tamanho_mb": size_bytes / (1024.0 * 1024.0),
        "caminho": str(ZIP_DATABASE_PATH),
    }
