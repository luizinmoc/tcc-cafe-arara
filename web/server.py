#!/usr/bin/env python3
"""
server.py — Servidor Web ASGI (Starlette + Uvicorn) para o Dashboard do Café Arara.

Fornece endpoints RESTful para inferência de visão computacional, aprendizado contínuo,
gerenciamento de amostras do experimento e serve a interface React 18 moderna.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
from pathlib import Path

# Adicionar a raiz do projeto ao sys.path para garantir importação de 'src'
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Any

import cv2
import numpy as np
import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles

from src.inference_engine import run_inference, get_model
from src.continuous_learning import get_learning_status, execute_continuous_fine_tuning
from src.data_logger import record_count_session, get_recent_sessions

logger = logging.getLogger("web_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_ROOT / "web"
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


async def handle_index(request: Request) -> HTMLResponse:
    """Serve a página principal do aplicativo React."""
    index_file = WEB_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Arquivo web/index.html não encontrado!</h1>", status_code=404)
    return HTMLResponse(index_file.read_text(encoding="utf-8"))


async def handle_status(request: Request) -> JSONResponse:
    """Retorna o status do modelo e do pipeline de aprendizado contínuo."""
    try:
        learning_status = get_learning_status()
        return JSONResponse({
            "status": "online",
            "model_version": learning_status["current_version"],
            "total_fine_tunings": learning_status["total_fine_tunings"],
            "last_modified": learning_status["last_modified"],
            "weights_size_mb": learning_status["weights_size_mb"],
            "history": learning_status["history"],
        })
    except Exception as e:
        logger.error("Erro ao obter status: %s", e)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def handle_samples_list(request: Request) -> JSONResponse:
    """Lista as imagens do experimento disponíveis para teste em 1 clique."""
    samples = []
    if RAW_DATA_DIR.exists():
        for f in sorted(RAW_DATA_DIR.iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                samples.append({
                    "name": f.name,
                    "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                })
    return JSONResponse({"samples": samples})


async def handle_sample_image(request: Request) -> Response:
    """Retorna o arquivo de uma imagem de amostra."""
    name = request.path_params["name"]
    sample_file = RAW_DATA_DIR / name
    if not sample_file.exists() or not sample_file.is_file():
        return Response("Amostra não encontrada", status_code=404)
    return Response(sample_file.read_bytes(), media_type="image/jpeg")


async def handle_analyze(request: Request) -> JSONResponse:
    """Executa a inferência sobre a imagem enviada ou selecionada."""
    try:
        form = await request.form()
        image_bytes: bytes | None = None
        image_name = "upload.jpg"

        # Caso 1: Upload direto de arquivo
        if "file" in form and hasattr(form["file"], "read"):
            upload_file = form["file"]
            image_bytes = await upload_file.read()
            image_name = getattr(upload_file, "filename", "upload.jpg")

        # Caso 2: Amostra pré-carregada do experimento
        elif "sample_name" in form:
            sample_name = str(form["sample_name"])
            sample_file = RAW_DATA_DIR / sample_name
            if sample_file.exists():
                image_bytes = sample_file.read_bytes()
                image_name = sample_name

        if not image_bytes:
            return JSONResponse({"error": "Nenhuma imagem foi enviada."}, status_code=400)

        # Decodificar imagem OpenCV
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img_bgr is None:
            return JSONResponse({"error": "Arquivo de imagem corrompido ou formato inválido."}, status_code=400)

        # Parâmetros opcionais
        confidence = float(form.get("confidence", 0.04))
        iou_threshold = float(form.get("iou", 0.65))
        box_thickness = int(form.get("box_thickness", 2))
        auto_learn = str(form.get("auto_learn", "false")).lower() in ("true", "1")

        # Executar inferência profunda com calibração de cor (Bounding Boxes)
        result = run_inference(
            image_bgr=img_bgr,
            confidence=confidence,
            iou_threshold=iou_threshold,
            draw_style="boxes",
            box_thickness=box_thickness,
        )

        # Registrar no histórico sem zip
        record_count_session(
            image_name=image_name,
            counts=result["counts"],
            ratios=result["ratios"],
            confidence=confidence,
        )

        # Se aprendizado ativo estiver ligado, agendar fine-tuning leve em background
        learning_feedback = None
        if auto_learn:
            try:
                # Rodar 1 ciclo rápido de aprendizado
                learning_feedback = execute_continuous_fine_tuning(epochs=2, batch_size=8)
            except Exception as e:
                logger.warning("Falha no auto-aprendizado: %s", e)

        result["image_name"] = image_name
        result["auto_learn_triggered"] = auto_learn
        if learning_feedback:
            result["learning_feedback"] = learning_feedback

        return JSONResponse(result)

    except Exception as e:
        logger.error("Erro durante análise: %s", e, exc_info=True)
        return JSONResponse({"error": f"Erro interno durante processamento: {str(e)}"}, status_code=500)


async def handle_learn(request: Request) -> JSONResponse:
    """Dispara um ciclo de ajuste fino contínuo (Continuous Learning)."""
    try:
        data = await request.json() if request.headers.get("content-type") == "application/json" else {}
        epochs = int(data.get("epochs", 3))

        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, execute_continuous_fine_tuning, epochs)

        return JSONResponse({
            "status": "sucesso",
            "message": "Ciclo de aprendizado concluído com sucesso!",
            "details": res,
        })
    except Exception as e:
        logger.error("Erro durante aprendizado contínuo: %s", e, exc_info=True)
        return JSONResponse({"status": "erro", "message": str(e)}, status_code=500)


async def handle_history(request: Request) -> JSONResponse:
    """Retorna as últimas sessões de inferência."""
    sessions = get_recent_sessions(limit=30)
    return JSONResponse({"history": sessions})


routes = [
    Route("/", handle_index, methods=["GET"]),
    Route("/api/status", handle_status, methods=["GET"]),
    Route("/api/samples", handle_samples_list, methods=["GET"]),
    Route("/api/sample/{name}", handle_sample_image, methods=["GET"]),
    Route("/api/analyze", handle_analyze, methods=["POST"]),
    Route("/api/learn", handle_learn, methods=["POST"]),
    Route("/api/history", handle_history, methods=["GET"]),
]

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

app = Starlette(routes=routes, middleware=middleware)

def _auto_open_browser():
    import time
    import webbrowser
    time.sleep(1.8)
    try:
        webbrowser.open("http://localhost:8501")
    except Exception:
        pass


if __name__ == "__main__":
    import threading
    threading.Thread(target=_auto_open_browser, daemon=True).start()
    print("========================================================================")
    print("   CAFÉ ARARA AI — SERVIDOR WEB INICIADO")
    print("   Acesse no navegador: http://localhost:8501")
    print("========================================================================")
    uvicorn.run(app, host="127.0.0.1", port=8501, log_level="info")
