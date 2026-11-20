#!/usr/bin/env python3
"""
continuous_learning.py — Módulo de Aprendizado Contínuo (Active / Continuous Learning).

Implementa o ciclo leve de re-treinamento incremental sob demanda
para o modelo YOLOv8 no projeto de TCC de Maturação do Café Arara.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ultralytics import YOLO

logger = logging.getLogger("continuous_learning")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEIGHTS_DIR = PROJECT_ROOT / "weights"
BEST_WEIGHTS_PATH = WEIGHTS_DIR / "best.pt"
BACKUP_WEIGHTS_PATH = WEIGHTS_DIR / "best_previous_backup.pt"
DATASET_YAML = PROJECT_ROOT / "dataset.yaml"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
HISTORY_FILE = OUTPUTS_DIR / "historico_aprendizado.json"


def get_learning_status() -> dict[str, Any]:
    """Retorna o status atual do modelo e do pipeline de aprendizado contínuo."""
    weights_exist = BEST_WEIGHTS_PATH.exists()
    weights_size_mb = (
        BEST_WEIGHTS_PATH.stat().st_size / (1024 * 1024) if weights_exist else 0.0
    )
    last_modified = (
        datetime.fromtimestamp(BEST_WEIGHTS_PATH.stat().st_mtime).strftime("%d/%m/%Y %H:%M:%S")
        if weights_exist
        else "Nunca"
    )

    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            history = []

    version_count = len(history)
    current_version = f"v1.{version_count}" if version_count > 0 else "v1.0 (Inicial)"

    return {
        "weights_path": str(BEST_WEIGHTS_PATH),
        "weights_exist": weights_exist,
        "weights_size_mb": round(weights_size_mb, 2),
        "last_modified": last_modified,
        "current_version": current_version,
        "total_fine_tunings": version_count,
        "history": list(reversed(history[-10:])),
    }


def execute_continuous_fine_tuning(
    epochs: int = 3,
    batch_size: int = 8,
    learning_rate: float = 0.0003,
    freeze_layers: int = 10,
    progress_callback: Callable[[str, float], None] | None = None,
) -> dict[str, Any]:
    """Executa um ciclo rápido e leve de Fine-Tuning Incremental."""
    start_time = time.time()

    if not BEST_WEIGHTS_PATH.exists():
        raise FileNotFoundError(f"Pesos base não encontrados em: {BEST_WEIGHTS_PATH}")

    if progress_callback:
        progress_callback("Inicializando modelo pré-treinado e dados...", 0.15)

    run_name = f"cl_finetune_{int(time.time())}"
    project_run_dir = PROJECT_ROOT / "runs" / "detect" / "outputs" / run_name

    logger.info("Carregando modelo base: %s", BEST_WEIGHTS_PATH)
    model = YOLO(str(BEST_WEIGHTS_PATH))

    if progress_callback:
        progress_callback("Executando ajuste fino incremental nos neurônios...", 0.40)

    try:
        results = model.train(
            data=str(DATASET_YAML),
            epochs=epochs,
            batch=batch_size,
            imgsz=640,
            lr0=learning_rate,
            device="cpu",
            workers=2,
            freeze=freeze_layers,
            project=str(PROJECT_ROOT / "runs" / "detect" / "outputs"),
            name=run_name,
            exist_ok=True,
            verbose=False,
            plots=False,
            save=True,
        )
    except Exception as e:
        logger.error("Erro durante o fine-tuning: %s", e)
        raise RuntimeError(f"Falha no fine-tuning incremental: {e}") from e

    if progress_callback:
        progress_callback("Otimizando e consolidando novos pesos...", 0.85)

    new_best = project_run_dir / "weights" / "best.pt"
    if not new_best.exists():
        new_best = project_run_dir / "weights" / "last.pt"

    if new_best.exists():
        if BEST_WEIGHTS_PATH.exists():
            shutil.copy2(BEST_WEIGHTS_PATH, BACKUP_WEIGHTS_PATH)
        shutil.copy2(new_best, BEST_WEIGHTS_PATH)
        logger.info("Pesos atualizados com sucesso em: %s", BEST_WEIGHTS_PATH)

    elapsed_seconds = round(time.time() - start_time, 1)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            history = []

    version_num = len(history) + 1
    new_version_tag = f"v1.{version_num}"
    record = {
        "version": new_version_tag,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "epochs": epochs,
        "batch_size": batch_size,
        "elapsed_seconds": elapsed_seconds,
        "device": "cpu",
        "freeze_layers": freeze_layers,
        "status": "sucesso",
    }
    history.append(record)
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")

    # Limpar diretório temporário do run para economizar espaço em disco
    try:
        shutil.rmtree(project_run_dir, ignore_errors=True)
    except Exception:
        pass

    if progress_callback:
        progress_callback("Aprendizado concluído com sucesso!", 1.0)

    return {
        "status": "sucesso",
        "new_version": new_version_tag,
        "elapsed_seconds": elapsed_seconds,
        "epochs": epochs,
        "weights_path": str(BEST_WEIGHTS_PATH),
    }
