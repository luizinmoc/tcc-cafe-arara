#!/usr/bin/env python3
"""
data_logger.py — Registro e Histórico de Sessões de Inferência do TCC.

Salva de forma leve e direta as métricas de contagem e maturação
em formato JSON e CSV estruturados em outputs/, sem uso de arquivos compactados ZIP.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("data_logger")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CSV_PATH = OUTPUTS_DIR / "historico_contagens.csv"
JSON_PATH = OUTPUTS_DIR / "historico_contagens.json"

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
    "confianca_minima",
    "modelo",
]


def _ensure_outputs_dir() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        with open(CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMNS)
    if not JSON_PATH.exists():
        JSON_PATH.write_text("[]", encoding="utf-8")


def record_count_session(
    image_name: str,
    counts: dict[str, int],
    ratios: dict[str, float],
    model_name: str = "YOLOv8 Deep Learning + HSV Calibration",
    confidence: float = 0.25,
) -> dict[str, Any]:
    """Registra uma sessão de inferência no histórico em JSON e CSV."""
    _ensure_outputs_dir()

    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_graos = sum(counts.values())

    record: dict[str, Any] = {
        "data_hora": timestamp_str,
        "imagem": Path(image_name).name,
        "total_graos": total_graos,
        "verde": counts.get("verde", 0),
        "amarelo": counts.get("amarelo", 0),
        "cereja_ideal": counts.get("cereja_ideal", 0),
        "passado": counts.get("passado", 0),
        "seco": counts.get("seco", 0),
        "pct_verde": round(ratios.get("verde", 0.0), 2),
        "pct_amarelo": round(ratios.get("amarelo", 0.0), 2),
        "pct_cereja_ideal": round(ratios.get("cereja_ideal", 0.0), 2),
        "pct_passado": round(ratios.get("passado", 0.0), 2),
        "pct_seco": round(ratios.get("seco", 0.0), 2),
        "confianca_minima": confidence,
        "modelo": model_name,
    }

    # Salvar em CSV
    with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([record[col] for col in CSV_COLUMNS])

    # Salvar em JSON
    try:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = []
    data.append(record)
    JSON_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    return record


def get_recent_sessions(limit: int = 20) -> list[dict[str, Any]]:
    """Retorna as sessões mais recentes do histórico."""
    _ensure_outputs_dir()
    try:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        return list(reversed(data[-limit:]))
    except Exception:
        return []
