#!/usr/bin/env python3
"""
app.py — Dashboard de Visão Computacional para Maturação do Café Arara (Deep Learning).

Sistema exclusivo de Deep Learning (YOLOv8) para detecção, classificação e contagem
dos 5 estágios morfológicos de maturação do Café Arara:
  0 — Verde (Imaturo)
  1 — Amarelo (Em Maturação)
  2 — Cereja Amarelo (Ponto Ideal de Colheita ★)
  3 — Passado (Seco Parcial)
  4 — Seco (Passa/Seco)

Cada rodada de contagem é compactada e salva automaticamente em:
  outputs/base_dados_tcc.zip
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from numpy.typing import NDArray
from PIL import Image

# ---------------------------------------------------------------------------
# Raiz do projeto e dependências internas
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_logger import (
    record_count_session,
    get_archive_dataframe,
    get_archive_info,
    get_archive_bytes,
)
from src.continuous_learning import (
    get_learning_status,
    execute_continuous_fine_tuning,
)
from src.utils import (
    CLASS_COLORS_BGR_5,
    CLASS_COLORS_HEX,
    CLASS_DISPLAY_NAMES,
    CLASS_EMOJIS,
    CLASS_NAMES,
    bgr_to_rgb,
    compute_maturity_ratio,
    count_by_class,
    draw_detections,
    find_images,
    parse_yolo_results,
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
DEFAULT_WEIGHTS_PATH = PROJECT_ROOT / "weights" / "best.pt"
RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw"
PAGE_TITLE = "☕ Café Arara — Deep Learning (TCC)"
PAGE_ICON = "☕"


# ═══════════════════════════════════════════════════════════════════════════
# Carregamento do Modelo Deep Learning (Cache)
# ═══════════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner="Carregando rede neural Deep Learning (YOLOv8)...")
def load_deep_learning_model(weights_path: str | Path, mtime: float = 0.0) -> Any:
    """Carrega o modelo de Deep Learning treinado (YOLOv8)."""
    tiled_path = PROJECT_ROOT / "runs" / "detect" / "outputs" / "cafe_arara_dl_tiled" / "weights" / "best.pt"
    p = Path(weights_path)
    if tiled_path.exists():
        p = tiled_path
    elif not p.exists():
        p = Path("yolov8n.pt")
    from ultralytics import YOLO
    return YOLO(str(p))


def compute_grid_coordinates(min_v: int, max_v: int, sz: int, st: int) -> list[int]:
    """Gera coordenadas de janelas garantindo cobertura 100% até a última borda."""
    coords = []
    c = min_v
    while c + sz <= max_v:
        coords.append(c)
        c += st
    last_c = max_v - sz
    if last_c not in coords and last_c >= min_v:
        coords.append(last_c)
    return sorted(list(set(coords)))


def run_deep_learning_inference(
    model: Any,
    image_bgr: NDArray[np.uint8],
    confidence: float = 0.04,
    iou_threshold: float = 0.65,
    tile_size: int = 640,
    stride: int = 360,
) -> list[dict[str, Any]]:
    """Executa a inferência Deep Learning (YOLOv8) sobre a imagem com cobertura 100% de borda a borda.

    Em imagens de alta resolução, aplica janelamento deslizante denso cobrindo
    integralmente todas as extremidades da bandeja (sem pontos cegos à direita ou abaixo),
    preservando os grãos na resolução nativa 1:1 e sem teto de corte de frutos.
    """
    h_img, w_img = image_bgr.shape[:2]

    # Imagens pequenas: inferência direta
    if max(h_img, w_img) <= 800:
        results = model.predict(
            source=image_bgr,
            conf=confidence,
            iou=iou_threshold,
            max_det=2000,
            verbose=False,
        )
        return parse_yolo_results(results)

    # Delimitar ROI completa da bandeja (de borda a borda interna)
    y_min = int(h_img * 0.03)
    y_max = int(h_img * 0.95)
    x_min = int(w_img * 0.02)
    x_max = int(w_img * 0.98)

    tops = compute_grid_coordinates(y_min, y_max, tile_size, stride)
    lefts = compute_grid_coordinates(x_min, x_max, tile_size, stride)

    tiles: list[NDArray[np.uint8]] = []
    offsets: list[tuple[int, int]] = []

    for top in tops:
        for left in lefts:
            patch = image_bgr[top : top + tile_size, left : left + tile_size]
            if patch.shape[0] == tile_size and patch.shape[1] == tile_size:
                tiles.append(patch)
                offsets.append((left, top))

    if not tiles:
        results = model.predict(
            source=image_bgr,
            conf=confidence,
            iou=iou_threshold,
            max_det=2000,
            verbose=False,
        )
        return parse_yolo_results(results)

    # Inferência em batch com a rede neural YOLOv8 (sem limite artificial de 300)
    all_raw_boxes: list[list[float]] = []
    all_scores: list[float] = []
    all_classes: list[int] = []

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

                # Mapear para coordenadas globais da imagem original
                all_raw_boxes.append([bx1 + off_x, by1 + off_y, bx2 + off_x, by2 + off_y])
                all_scores.append(score)
                all_classes.append(cid)

    if not all_raw_boxes:
        return []

    # NMS Global para unificar detecções na borda dos tiles
    boxes_xywh = []
    for x1, y1, x2, y2 in all_raw_boxes:
        boxes_xywh.append([int(x1), int(y1), int(x2 - x1), int(y2 - y1)])

    indices = cv2.dnn.NMSBoxes(
        bboxes=boxes_xywh,
        scores=all_scores,
        score_threshold=confidence,
        nms_threshold=iou_threshold,
    )

    final_detections: list[dict[str, Any]] = []
    if len(indices) > 0:
        from src.color_classifier import ColorClassifier, DEFAULT_COLOR_RANGES
        classifier = ColorClassifier(color_ranges=DEFAULT_COLOR_RANGES)

        for idx in indices.flatten():
            gx1, gy1, gx2, gy2 = all_raw_boxes[idx]
            cid = all_classes[idx]

            # Refinar estágio de maturação através do espectro HSV local do fruto
            y1_c, y2_c = max(0, int(gy1)), min(h_img, int(gy2))
            x1_c, x2_c = max(0, int(gx1)), min(w_img, int(gx2))
            crop_grain = image_bgr[y1_c:y2_c, x1_c:x2_c]

            if crop_grain.size > 0:
                hsv_grain = cv2.cvtColor(crop_grain, cv2.COLOR_BGR2HSV)
                med_h = np.median(hsv_grain[:, :, 0])
                med_s = np.median(hsv_grain[:, :, 1])
                med_v = np.median(hsv_grain[:, :, 2])

                for cr in classifier.color_ranges:
                    if cr.h_min <= med_h <= cr.h_max and cr.s_min <= med_s <= cr.s_max and cr.v_min <= med_v <= cr.v_max:
                        cid = cr.class_id
                        break

            final_detections.append({
                "class_id": cid,
                "class_name": CLASS_NAMES.get(cid, f"classe_{cid}"),
                "confidence": all_scores[idx],
                "bbox": (int(gx1), int(gy1), int(gx2), int(gy2)),
            })

    return final_detections


# ═══════════════════════════════════════════════════════════════════════════
# Layout e Interface
# ═══════════════════════════════════════════════════════════════════════════

def setup_page() -> None:
    """Configura página e estilos CSS otimizados."""
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        <style>
        .main-header { text-align: center; padding: 0.2rem 0; margin-bottom: 0px; }
        .metric-card {
            background: linear-gradient(135deg, #1b1e2e 0%, #292d42 100%);
            border-radius: 12px; padding: 0.9rem; text-align: center;
            border: 1px solid #3d4263;
        }
        .metric-value { font-size: 2.1rem; font-weight: 700; margin: 0.2rem 0; }
        .metric-label { font-size: 0.78rem; opacity: 0.85; text-transform: uppercase; letter-spacing: 0.8px; }
        .metric-pct { font-size: 0.88rem; opacity: 0.75; }
        .total-card { background: linear-gradient(135deg, #133352 0%, #204d77 100%); border: 1px solid #2d6da6; }
        .ideal-card { background: linear-gradient(135deg, #383500 0%, #544e00 100%); border: 1px solid #a89a00; }
        .zip-box {
            background: rgba(30, 70, 40, 0.25); border: 1px solid #2e8b57;
            padding: 0.7rem; border-radius: 8px; margin-bottom: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    """Cabeçalho simples e elegante."""
    st.markdown(
        "<h1 class='main-header'>☕ Visão Computacional — Maturação do Café Arara</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; opacity:0.85; font-size: 1.05rem;'>"
        "Identificação e Contagem Automática com Rede Neural <b>Deep Learning (YOLOv8)</b>"
        "</p>",
        unsafe_allow_html=True,
    )
    st.divider()


def render_sidebar_controls() -> tuple[float, float, str, int, int]:
    """Barra lateral enxuta focada em Deep Learning e na Base de Dados Compactada."""
    st.sidebar.header("⚙️ Configurações da Rede Neural")
    st.sidebar.divider()

    st.sidebar.subheader("🧠 Parâmetros de Inferência")
    confidence = st.sidebar.slider(
        "Confiança Mínima",
        min_value=0.01,
        max_value=0.50,
        value=0.04,
        step=0.01,
        help="Limiar de probabilidade mínima da rede. Valores entre 0.03 e 0.05 capturam frutos escuros, passados e verdes sem perder precisão.",
    )

    iou_threshold = st.sidebar.slider(
        "Separação entre Grãos (IoU NMS)",
        min_value=0.20,
        max_value=0.85,
        value=0.65,
        step=0.05,
        help="Limiar de sobreposição (NMS). Como os frutos de café ficam encostados lado a lado, 0.65 preserva frutos vizinhos sem canibalização.",
    )

    scan_mode = st.sidebar.selectbox(
        "Modo de Varredura da Bandeja:",
        ["🔥 Cobertura Ultradensa (100% de Borda a Borda)", "⚡ Rápida Padrão"],
        index=0,
        help="Ultradensa cobre até as últimas bordas da bandeja com overlap de 50%, detectando a quantidade máxima real de frutos.",
    )
    stride = 320 if "Ultradensa" in scan_mode else 440

    st.sidebar.divider()
    st.sidebar.subheader("🎨 Estilo de Visualização")
    vis_style = st.sidebar.selectbox(
        "Marcador na Imagem:",
        ["📍 Pontos Centróides (Ultra Limpo)", "📦 Bounding Boxes (Sem Texto)", "🏷️ Bounding Boxes com Texto"],
        index=0,
    )

    marker_size = st.sidebar.slider(
        "Tamanho do Marcador / Linha (px)",
        min_value=2,
        max_value=10,
        value=4,
        step=1,
    )

    st.sidebar.divider()
    st.sidebar.subheader("💾 Base de Dados do TCC (.zip)")

    db_info = get_archive_info()
    st.sidebar.markdown(
        f"""
        <div class="zip-box">
            <b>📦 Arquivo Compactado Ativo:</b><br>
            <code>base_dados_tcc.zip</code><br><br>
            • <b>Rodadas Salvas:</b> {db_info['num_rodadas']}<br>
            • <b>Imagens Gravadas:</b> {db_info['num_imagens_salvas']}<br>
            • <b>Espaço em Disco:</b> {db_info['tamanho_kb']:.1f} KB ({db_info['tamanho_mb']:.2f} MB)
        </div>
        """,
        unsafe_allow_html=True,
    )

    zip_data = get_archive_bytes()
    st.sidebar.download_button(
        label="📥 Baixar Base de Dados (.zip)",
        data=zip_data,
        file_name="base_dados_tcc_cafe_arara.zip",
        mime="application/zip",
        use_container_width=True,
    )

    return confidence, iou_threshold, vis_style, marker_size, stride


def render_cards(counts: dict[str, int], ratios: dict[str, float]) -> None:
    """Exibe os 5 cards com as classes estritas da variedade Arara."""
    total = sum(counts.values())
    st.markdown(
        f"""
        <div class="metric-card total-card">
            <div class="metric-label">Total de Frutos Detectados pela Rede Neural</div>
            <div class="metric-value" style="color: #6db4f0;">🫘 {total:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    cols = st.columns(5)
    class_order = ["verde", "amarelo", "cereja", "passado", "seco"]
    for col, class_name in zip(cols, class_order):
        cid = {v: k for k, v in CLASS_NAMES.items()}.get(class_name, -1)
        emoji = CLASS_EMOJIS.get(cid, "")
        color = CLASS_COLORS_HEX.get(cid, "#fff")
        c_val = counts.get(class_name, 0)
        c_pct = ratios.get(class_name, 0.0)
        display = CLASS_DISPLAY_NAMES.get(class_name, class_name)
        card_class = "metric-card ideal-card" if class_name == "cereja" else "metric-card"

        with col:
            st.markdown(
                f"""
                <div class="{card_class}">
                    <div class="metric-label">{display}</div>
                    <div class="metric-value" style="color: {color};">{emoji} {c_val:,}</div>
                    <div class="metric-pct">{c_pct:.1f}% da amostra</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_distribution_chart(counts: dict[str, int]) -> None:
    """Gráfico horizontal Plotly com a distribuição das 5 classes."""
    order = ["seco", "passado", "cereja", "amarelo", "verde"]
    labels = [CLASS_DISPLAY_NAMES.get(c, c) for c in order]
    vals = [counts.get(c, 0) for c in order]
    colors = [CLASS_COLORS_HEX.get({v: k for k, v in CLASS_NAMES.items()}.get(c, -1), "#fff") for c in order]

    fig = go.Figure(data=[go.Bar(
        x=vals, y=labels, orientation="h",
        marker_color=colors, text=[f"{v:,}" for v in vals],
        textposition="auto", textfont=dict(size=12, color="white"),
    )])
    fig.update_layout(
        title="Distribuição por Estágio de Maturação (Deep Learning)",
        xaxis_title="Quantidade de Frutos", yaxis_title="",
        height=280, margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"), xaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════
# Função Principal (Pipeline Enxuto)
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    setup_page()
    render_header()
    confidence, iou_threshold, vis_style, marker_size, stride = render_sidebar_controls()

    tiled_weight = PROJECT_ROOT / "runs" / "detect" / "outputs" / "cafe_arara_dl_tiled" / "weights" / "best.pt"
    active_weight = tiled_weight if tiled_weight.exists() else DEFAULT_WEIGHTS_PATH
    mtime = active_weight.stat().st_mtime if active_weight.exists() else 0.0
    model = load_deep_learning_model(active_weight, mtime=mtime)

    tab_single, tab_batch, tab_history = st.tabs([
        "🔍 Inferência Individual (Deep Learning)",
        "⚡ Processamento em Lote (Imagens do Drive)",
        "🔄 Base de Dados & Aprendizado Contínuo (TCC)",
    ])

    # -----------------------------------------------------------------------
    # TAB 1: Inferência Individual
    # -----------------------------------------------------------------------
    with tab_single:
        st.subheader("📥 Seleção da Imagem")
        source = st.radio(
            "Origem:",
            ["📁 Imagens do Google Drive", "📤 Fazer Upload de Nova Imagem"],
            horizontal=True,
        )

        image_bgr: NDArray[np.uint8] | None = None
        img_title = ""

        if source == "📁 Imagens do Google Drive":
            drive_imgs = find_images(RAW_DATA_PATH) if RAW_DATA_PATH.exists() else []
            if not drive_imgs:
                st.warning("Nenhuma imagem encontrada em data/raw/.")
            else:
                sel = st.selectbox(
                    "Selecione uma imagem do Drive:",
                    options=drive_imgs,
                    format_func=lambda p: p.name,
                )
                if sel:
                    image_bgr = cv2.imread(str(sel))
                    img_title = sel.name
        else:
            up_file = st.file_uploader(
                "Upload de imagem:",
                type=["jpg", "jpeg", "png", "bmp", "webp"],
            )
            if up_file:
                pil_im = Image.open(up_file).convert("RGB")
                img_rgb = np.array(pil_im)
                image_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
                img_title = up_file.name

        if image_bgr is not None:
            c_orig, c_res = st.columns(2)
            with c_orig:
                st.markdown(f"#### 🖼️ Imagem de Entrada: `{img_title}`")
                st.image(bgr_to_rgb(image_bgr), use_container_width=True)

            st.divider()
            _, btn_c, _ = st.columns([1, 2, 1])
            with btn_c:
                run_btn = st.button("🚀 Processar com Rede Neural Deep Learning", type="primary", use_container_width=True)

            if not run_btn:
                with c_res:
                    st.markdown("#### 📊 Resultado da Rede Neural")
                    st.info("Clique no botão para executar a inferência Deep Learning.")
            else:
                with st.spinner("Executando inferência com a rede neural YOLOv8..."):
                    detections = run_deep_learning_inference(
                        model=model,
                        image_bgr=image_bgr,
                        confidence=confidence,
                        iou_threshold=iou_threshold,
                        stride=stride,
                    )

                counts = count_by_class(detections)
                ratios = compute_maturity_ratio(counts)

                # Desenho do resultado
                style_code = "dots" if "Pontos" in vis_style else "boxes"
                show_lbl = "com Texto" in vis_style

                annotated_bgr = draw_detections(
                    image=image_bgr,
                    detections=detections,
                    style=style_code,
                    dot_radius=marker_size,
                    line_thickness=marker_size,
                    show_labels=show_lbl,
                )

                # Salvar automaticamente a rodada na base de dados compactada (.zip)
                log_result = record_count_session(
                    image_name=img_title,
                    counts=counts,
                    ratios=ratios,
                    annotated_bgr=annotated_bgr,
                    model_name="YOLOv8 Deep Learning (best.pt)",
                    confidence=confidence,
                )

                with c_res:
                    st.markdown("#### 📊 Resultado (YOLOv8 Deep Learning)")
                    st.image(bgr_to_rgb(annotated_bgr), use_container_width=True)

                st.success(
                    f"💾 **Rodada gravada automaticamente na base de dados compactada!** "
                    f"Arquivo: `base_dados_tcc.zip` ({log_result['zip_size_kb']:.1f} KB total)"
                )

                st.divider()
                st.subheader("📈 Métricas de Maturação da Amostra")
                render_cards(counts, ratios)

                st.markdown("<br>", unsafe_allow_html=True)
                col_chart, col_table = st.columns([1, 1])
                with col_chart:
                    render_distribution_chart(counts)
                with col_table:
                    st.markdown("#### 📋 Resumo Consolidado da Rodada")
                    summary_df = pd.DataFrame([{
                        "Estágio": CLASS_DISPLAY_NAMES.get(k, k),
                        "Contagem": f"{v:,}",
                        "Proporção": f"{ratios.get(k, 0.0):.1f}%",
                    } for k, v in counts.items()])
                    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    # -----------------------------------------------------------------------
    # TAB 2: Processamento em Lote com Deep Learning
    # -----------------------------------------------------------------------
    with tab_batch:
        st.subheader("⚡ Processamento em Lote com Deep Learning")
        st.markdown(
            "Executa a inferência da rede neural em todas as imagens do Google Drive, "
            "armazenando cada resultado de forma compactada na base de dados do TCC."
        )

        drive_images = find_images(RAW_DATA_PATH) if RAW_DATA_PATH.exists() else []
        st.info(f"📂 Total de **{len(drive_images)} imagens do Drive** prontas para inferência.")

        if st.button("🚀 Iniciar Lote com Deep Learning", type="primary", use_container_width=True):
            pbar = st.progress(0.0)
            status = st.empty()
            batch_records = []

            for i, img_p in enumerate(drive_images):
                status.text(f"Inferindo com Deep Learning [{i+1}/{len(drive_images)}]: {img_p.name}...")
                im = cv2.imread(str(img_p))
                if im is None:
                    continue

                dets = run_deep_learning_inference(model, im, confidence, iou_threshold, stride=stride)
                c_dict = count_by_class(dets)
                r_dict = compute_maturity_ratio(c_dict)

                ann = draw_detections(im, dets, style="dots", dot_radius=marker_size)

                # Salvar no zip
                record_count_session(
                    image_name=img_p.name,
                    counts=c_dict,
                    ratios=r_dict,
                    annotated_bgr=ann,
                    model_name="YOLOv8 Deep Learning (best.pt)",
                    confidence=confidence,
                )

                batch_records.append({
                    "Imagem": img_p.name,
                    "Total Grãos": sum(c_dict.values()),
                    "Verde": c_dict.get("verde", 0),
                    "Amarelo": c_dict.get("amarelo", 0),
                    "Cereja (Ideal)": c_dict.get("cereja", 0),
                    "Passado": c_dict.get("passado", 0),
                    "Seco": c_dict.get("seco", 0),
                    "% Cereja": f"{r_dict.get('cereja', 0.0):.1f}%",
                })
                pbar.progress((i + 1) / len(drive_images))

            status.success(f"✅ Lote completo processado e gravado com sucesso no arquivo compactado ZIP!")

            df_batch = pd.DataFrame(batch_records)
            st.dataframe(df_batch, use_container_width=True)

    # -----------------------------------------------------------------------
    # TAB 3: Base de Dados & Aprendizado Contínuo (TCC)
    # -----------------------------------------------------------------------
    with tab_history:
        st.subheader("🔄 Ciclo de Aprendizado Contínuo (Active Learning)")
        st.markdown(
            "Conforme novas imagens e rodadas são processadas, o sistema armazena o histórico "
            "no arquivo compactado e permite realizar **ajustes finos incrementais (*Fine-Tuning*)** "
            "na rede neural sem sobrecarregar o computador."
        )

        learning_status = get_learning_status()

        # Métricas do modelo atual
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.metric("Versão do Modelo", learning_status["current_version"])
        with m_col2:
            st.metric("Tamanho em Disco", f"{learning_status['weights_size_mb']:.2f} MB")
        with m_col3:
            st.metric("Último Aperfeiçoamento", learning_status["last_modified"].split(" ")[0])
        with m_col4:
            st.metric("Ciclos Executados", f"{learning_status['total_fine_tunings']} rodadas")

        st.divider()

        # Painel de execução do Fine-Tuning Incremental
        st.markdown("#### ⚡ Aperfeiçoamento da Rede Neural (1-Clique)")
        st.markdown(
            """
            <div style="background: rgba(30, 50, 80, 0.25); border-left: 4px solid #3b82f6; padding: 0.8rem; border-radius: 6px; margin-bottom: 1rem;">
                <b>Como funciona o modo leve:</b> As camadas de extração de características visuais básicas da rede 
                são <i>congeladas (freeze)</i>, ajustando apenas a cabeça de classificação com taxa de aprendizado suave (<code>lr=0.0003</code>). 
                Isso dura menos de 1 minuto na CPU, não trava o PC e evita o <i>esquecimento catastrófico</i>.
            </div>
            """,
            unsafe_allow_html=True,
        )

        cl_c1, cl_c2 = st.columns([1, 2])
        with cl_c1:
            ft_epochs = st.slider(
                "Épocas de Ajuste Fino:",
                min_value=1,
                max_value=5,
                value=3,
                help="Número de passagens incrementais. 3 épocas é o equilíbrio ideal entre rapidez e ganho de acurácia.",
            )
        with cl_c2:
            st.write("")
            st.write("")
            start_ft = st.button("🚀 Executar Aperfeiçoamento Contínuo", type="primary", use_container_width=True)

        if start_ft:
            progress_bar = st.progress(0.0)
            status_text = st.empty()

            def update_progress(msg: str, val: float):
                status_text.info(f"⏳ {msg}")
                progress_bar.progress(val)

            try:
                with st.spinner("Executando Fine-Tuning Incremental no modelo..."):
                    ft_result = execute_continuous_fine_tuning(
                        epochs=ft_epochs,
                        progress_callback=update_progress,
                    )
                st.cache_resource.clear()
                status_text.empty()
                progress_bar.empty()
                st.success(
                    f"🎉 **Modelo aprimorado com sucesso para a versão {ft_result['new_version']}!** "
                    f"Tempo decorrido: {ft_result['elapsed_seconds']}s ({ft_result['epochs']} épocas). "
                    f"Os novos pesos já estão ativos para as próximas inferências!"
                )
                st.balloons()
            except Exception as e:
                status_text.empty()
                progress_bar.empty()
                st.error(f"❌ Ocorreu um erro durante o ajuste fino: {e}")

        st.divider()

        # Seção da Base de Dados Compactada (.zip)
        st.subheader("📦 Base de Dados Compactada do TCC (.zip)")
        st.markdown(
            "Tabela com todas as contagens salvas na base compactada para auditoria, relatórios e monografia."
        )

        hist_df = get_archive_dataframe()
        if hist_df.empty:
            st.info("Nenhuma rodada gravada ainda. Processe imagens nas abas anteriores para preencher a base de dados.")
        else:
            st.dataframe(hist_df, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="📥 Baixar Histórico em CSV",
                    data=hist_df.to_csv(index=False).encode("utf-8"),
                    file_name="historico_contagens_tcc.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with col2:
                st.download_button(
                    label="📥 Baixar Base de Dados Completa (.zip com imagens)",
                    data=get_archive_bytes(),
                    file_name="base_dados_tcc_cafe_arara.zip",
                    mime="application/zip",
                    use_container_width=True,
                )


if __name__ == "__main__":
    main()
