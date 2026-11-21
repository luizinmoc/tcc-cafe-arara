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
    "cereja_1",
    "cereja_2",
    "passa",
    "seco",
    "pct_verde",
    "pct_cereja_1",
    "pct_cereja_2",
    "pct_passa",
    "pct_seco",
    "pct_apice_qualidade",
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

    c1 = counts.get("cereja_1", counts.get("amarelo", 0))
    c2 = counts.get("cereja_2", counts.get("cereja", 0))
    cp = counts.get("passa", counts.get("passado", 0))
    cv = counts.get("verde", 0)
    cs = counts.get("seco", 0)

    p1 = ratios.get("cereja_1", ratios.get("amarelo", 0.0))
    p2 = ratios.get("cereja_2", ratios.get("cereja", 0.0))
    pp = ratios.get("passa", ratios.get("passado", 0.0))
    pv = ratios.get("verde", 0.0)
    ps = ratios.get("seco", 0.0)

    record: dict[str, Any] = {
        "data_hora": timestamp_str,
        "imagem": Path(image_name).name,
        "total_graos": total_graos,
        "verde": cv,
        "cereja_1": c1,
        "cereja_2": c2,
        "passa": cp,
        "seco": cs,
        "pct_verde": round(pv, 2),
        "pct_cereja_1": round(p1, 2),
        "pct_cereja_2": round(p2, 2),
        "pct_passa": round(pp, 2),
        "pct_seco": round(ps, 2),
        "pct_apice_qualidade": round(p2 + pp, 2),
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
