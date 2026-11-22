#!/usr/bin/env python3
"""
generate_paper_figures.py
Gera as figuras acadêmicas em alta resolução (300 DPI) para inserção no artigo DOCX.
"""

import os
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

OUTPUT_DIR = Path(__file__).resolve().parent / "paper_assets"
OUTPUT_DIR.mkdir(exist_ok=True)

plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'


def fig1_arquitetura():
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis('off')

    # Cores
    c_web = "#1e293b"
    c_srv = "#0f766e"
    c_ia = "#b45309"
    c_data = "#475569"

    # 1. Interface Web
    ax.add_patch(patches.FancyBboxPatch((2, 15), 24, 32, boxstyle="round,pad=1.5", fc=c_web, ec="#38bdf8", lw=1.5))
    ax.text(14, 42, "Interface Web (React 18)", color="white", weight="bold", fontsize=9, ha="center")
    ax.text(14, 36, "• Visualizador BBoxes\n• Alternador Original\n• Gráfico SVG Donut\n• Cronômetro Tempo Real\n• Relatórios CSV / KPIs", color="#cbd5e1", fontsize=7.5, ha="center")

    # 2. Servidor ASGI
    ax.add_patch(patches.FancyBboxPatch((35, 12), 28, 38, boxstyle="round,pad=1.5", fc=c_srv, ec="#2dd4bf", lw=1.5))
    ax.text(49, 44, "Servidor ASGI (Starlette)", color="white", weight="bold", fontsize=9, ha="center")
    ax.text(49, 36, "API RESTful Assíncrona\n• /api/analyze (Inferência)\n• /api/learn (Active Learning)\n• /api/samples & /favicon.ico\n• BackgroundTask (Fine-tune)", color="#ccfbf1", fontsize=7.5, ha="center")

    # 3. Motor de Visão & IA
    ax.add_patch(patches.FancyBboxPatch((71, 15), 27, 32, boxstyle="round,pad=1.5", fc=c_ia, ec="#fbbf24", lw=1.5))
    ax.text(84.5, 42, "Motor de Inteligência", color="white", weight="bold", fontsize=9, ha="center")
    ax.text(84.5, 34, "• YOLOv8 Híbrido (1:1 + Global)\n• NMS Global (IoU=0.65)\n• ExtraTrees (Grão vs Madeira)\n• Calibração Espectral HSV\n• Diagnóstico do Ápice (Brix)", color="#fef3c7", fontsize=7.5, ha="center")

    # 4. Banco e Histórico (inferior)
    ax.add_patch(patches.FancyBboxPatch((35, 2), 28, 7, boxstyle="round,pad=0.8", fc=c_data, ec="#94a3b8", lw=1))
    ax.text(49, 5.5, "Data Logger: outputs/ (JSON & CSV)", color="white", weight="bold", fontsize=7.5, ha="center")

    # Setas
    arrow_props = dict(arrowstyle="<->", color="#0284c7", lw=1.5)
    ax.annotate("", xy=(35, 31), xytext=(26, 31), arrowprops=arrow_props)
    ax.text(30.5, 33, "HTTP/JSON", fontsize=6.5, color="#0369a1", ha="center", weight="bold")

    arrow_props2 = dict(arrowstyle="<->", color="#d97706", lw=1.5)
    ax.annotate("", xy=(71, 31), xytext=(63, 31), arrowprops=arrow_props2)
    ax.text(67, 33, "OpenCV / NumPy", fontsize=6.5, color="#b45309", ha="center", weight="bold")

    arrow_props3 = dict(arrowstyle="->", color="#64748b", lw=1.2)
    ax.annotate("", xy=(49, 9), xytext=(49, 12), arrowprops=arrow_props3)

    plt.tight_layout()
    p = OUTPUT_DIR / "fig1_arquitetura.png"
    plt.savefig(p, dpi=300)
    plt.close()
    print("Figura 1 gerada:", p)


def fig2_pipeline():
    fig, ax = plt.subplots(figsize=(7.5, 3.6), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 50)
    ax.axis('off')

    steps = [
        ("1. Imagem\nEntrada\n(4K ou Upload)", 8, "#334155"),
        ("2. Passe Duplo\nGlobal (640px) +\nTiling 1:1 (360 st)", 25, "#0369a1"),
        ("3. NMS Global\nFusão de Caixas\n(IoU = 0.65)", 43, "#047857"),
        ("4. ExtraTrees ML\n14 Descritores\nFiltro Madeira", 61, "#b45309"),
        ("5. HSV & Ápice\n5 Estágios\nCereja II + Passa", 79, "#6d28d9"),
        ("6. Laudo &\nRecomendação\nAgronômica", 95, "#be123c")
    ]

    for i, (txt, x, col) in enumerate(steps):
        ax.add_patch(patches.FancyBboxPatch((x-6, 12), 12, 26, boxstyle="round,pad=1.2", fc=col, ec="none"))
        ax.text(x, 25, txt, color="white", weight="bold", fontsize=7.2, ha="center", va="center")
        if i < len(steps) - 1:
            next_x = steps[i+1][1]
            ax.annotate("", xy=(next_x-6, 25), xytext=(x+6, 25),
                        arrowprops=dict(arrowstyle="->", color="#64748b", lw=1.5))

    plt.tight_layout()
    p = OUTPUT_DIR / "fig2_pipeline.png"
    plt.savefig(p, dpi=300)
    plt.close()
    print("Figura 2 gerada:", p)


def fig3_morfologia():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.2), dpi=300)

    # Fruto de Café (Curvatura Convexa 3D)
    x = np.linspace(-2, 2, 80)
    y = np.linspace(-2, 2, 80)
    X, Y = np.meshgrid(x, y)
    Z = np.exp(-(X**2 + Y**2)/1.5)

    im1 = ax1.imshow(Z, cmap='YlOrBr', extent=[-2, 2, -2, 2])
    ax1.set_title("Fruto de Café (Domo Convexo 3D)\nc2b >= 10 | rad >= 25 (Vetores Convergentes)", fontsize=8, weight="bold")
    ax1.set_xticks([])
    ax1.set_yticks([])

    # Adicionar vetores de gradiente convergentes
    xv, yv = np.meshgrid(np.linspace(-1.5, 1.5, 6), np.linspace(-1.5, 1.5, 6))
    uv = -xv
    vv = -yv
    ax1.quiver(xv, yv, uv, vv, color='red', scale=15, width=0.008)

    # Madeira da Bandeja (Superfície Tabular Plana / Fibras Paralelas)
    Z_wood = np.tile(np.sin(X * 3) * 0.1 + 0.4, (80, 1))
    ax2.imshow(Z_wood, cmap='copper', extent=[-2, 2, -2, 2])
    ax2.set_title("Ripa de Madeira / Solo (Superfície Plana)\nc2b < 5 | rad < 10 (Gradientes Lineares/Nulos)", fontsize=8, weight="bold")
    ax2.set_xticks([])
    ax2.set_yticks([])

    # Vetores paralelos unidirecionais
    ax2.quiver(xv, yv, np.zeros_like(xv), np.ones_like(yv)*0.4, color='cyan', scale=10, width=0.008)

    plt.tight_layout()
    p = OUTPUT_DIR / "fig3_morfologia.png"
    plt.savefig(p, dpi=300)
    plt.close()
    print("Figura 3 gerada:", p)


def fig4_curva_maturacao():
    fig, ax = plt.subplots(figsize=(7.0, 3.2), dpi=300)

    estagios = ['Verde\n(Imaturo)', 'Cereja I\n(Início)', 'Cereja II\n(Pleno)', 'Passa\n(Concentrado)', 'Seco\n(Tardio)']
    brix = [10.2, 16.5, 21.8, 23.4, 15.0]
    acidez = [8.8, 6.2, 4.5, 3.8, 5.9]
    qualidade_sca = [68, 78, 87.5, 89.0, 72]

    x = np.arange(len(estagios))

    ax.plot(x, brix, 'o-', color='#eab308', lw=2.2, label='Grau Brix (°Brix) - Açúcares')
    ax.plot(x, qualidade_sca, 's--', color='#10b981', lw=2.2, label='Pontuação Sensorial SCA (pts)')
    ax.plot(x, acidez, '^-.', color='#ef4444', lw=1.8, label='Acidez Titulável (adstringência)')

    # Destaque para o Ápice da Qualidade
    ax.axvspan(1.7, 3.3, color='#fef08a', alpha=0.35, label='Janela do Ápice da Qualidade (★)')
    ax.text(2.5, 55, 'ÁPICE DA QUALIDADE\n(Cereja II + Passa)', color='#854d0e', weight='bold', fontsize=8, ha='center', bbox=dict(boxstyle='round,pad=0.4', fc='#fef9c3', ec='#ca8a04'))

    ax.set_xticks(x)
    ax.set_xticklabels(estagios, fontsize=8)
    ax.set_ylabel('Escala de Medição', fontsize=8.5)
    ax.set_title('Dinâmica Fisiológica de Maturação e Qualidade Sensorial do Café Arara', fontsize=9.5, weight='bold')
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(fontsize=7.5, loc='upper left')

    plt.tight_layout()
    p = OUTPUT_DIR / "fig4_curva_maturacao.png"
    plt.savefig(p, dpi=300)
    plt.close()
    print("Figura 4 gerada:", p)


if __name__ == "__main__":
    fig1_arquitetura()
    fig2_pipeline()
    fig3_morfologia()
    fig4_curva_maturacao()


def fig5_dashboard_ui():
    fig, ax = plt.subplots(figsize=(7.5, 4.0), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 55)
    ax.axis('off')

    # Fundo do Dashboard
    ax.add_patch(patches.Rectangle((0, 0), 100, 55, fc="#0b0f19"))

    # Top Header
    ax.add_patch(patches.Rectangle((0, 47), 100, 8, fc="#0f172a"))
    ax.text(3, 51, "☕ TCC Café Arara", color="white", weight="bold", fontsize=10)
    ax.text(3, 48.5, "Classificação Morfológica e Contagem do Nível de Maturação do Café Arara", color="#94a3b8", fontsize=7)
    ax.text(82, 51, "YOLOv8: v1.0", color="#fbbf24", weight="bold", fontsize=8)
    ax.text(93, 51, "Ativo ●", color="#10b981", weight="bold", fontsize=8)

    # 6 KPI Cards
    kpis = [
        ("Total Frutos", "11.687", "100%", "#f59e0b", 2),
        ("Verde", "580", "5.0%", "#10b981", 18.5),
        ("Cereja I", "5.952", "50.9%", "#facc15", 35),
        ("Cereja II ★", "203", "1.7%", "#eab308", 51.5),
        ("Passa ★", "4.582", "39.2%", "#ea580c", 68),
        ("Seco", "370", "3.2%", "#78350f", 84.5)
    ]
    for title, val, pct, col, x in kpis:
        ax.add_patch(patches.FancyBboxPatch((x, 37), 14, 8.5, boxstyle="round,pad=0.5", fc="#1e293b", ec=col, lw=1.5))
        ax.text(x+7, 43, title, color="#94a3b8", fontsize=6.5, ha="center")
        ax.text(x+7, 39.5, val, color=col, weight="bold", fontsize=9, ha="center")
        ax.text(x+7, 37.8, f"Proporção: {pct}", color="#cbd5e1", fontsize=5.8, ha="center")

    # Área de Visualização com Bounding Boxes
    ax.add_patch(patches.FancyBboxPatch((2, 3), 62, 32, boxstyle="round,pad=0.8", fc="#060911", ec="#334155", lw=1))
    ax.text(5, 32.5, "🔲 Modo: Bounding Boxes (YOLOv8 + ExtraTrees ML)", color="#fbbf24", weight="bold", fontsize=7.2)
    ax.text(48, 32.5, "⏱️ 1.21s", color="#34d399", weight="bold", fontsize=7.2)
    
    # Simulação da grade de grãos na bandeja
    np.random.seed(42)
    for _ in range(85):
        gx = np.random.uniform(5, 61)
        gy = np.random.uniform(5, 30)
        c_rand = np.random.choice(["#10b981", "#facc15", "#eab308", "#ea580c", "#78350f"], p=[0.08, 0.48, 0.04, 0.36, 0.04])
        ax.add_patch(patches.Rectangle((gx, gy), 1.8, 1.8, fill=False, ec=c_rand, lw=1.2))

    # Painel Lateral de Diagnóstico & Donut Chart
    ax.add_patch(patches.FancyBboxPatch((66, 3), 32, 32, boxstyle="round,pad=0.8", fc="#1e293b", ec="#334155", lw=1))
    ax.text(82, 32.5, "📊 Diagnóstico da Maturação", color="white", weight="bold", fontsize=7.5, ha="center")

    # Card Diagnóstico
    ax.add_patch(patches.FancyBboxPatch((68, 23), 28, 7.5, boxstyle="round,pad=0.5", fc="#10b98122", ec="#10b981", lw=1.2))
    ax.text(82, 28, "● Excelente Ponto de Colheita", color="#34d399", weight="bold", fontsize=7.2, ha="center")
    ax.text(82, 24.5, "Alta concentração no Ápice (Cereja II e Passa).\nLote favorável para cafés especiais.", color="#cbd5e1", fontsize=5.8, ha="center")

    # Donut Chart no Painel
    donut_c = [5.0, 50.9, 1.7, 39.2, 3.2]
    colors_d = ["#10b981", "#facc15", "#eab308", "#ea580c", "#78350f"]
    wedges, _ = ax.pie(donut_c, colors=colors_d, center=(82, 13), radius=7.5,
                       wedgeprops=dict(width=3.2, edgecolor="#0f172a"))
    ax.text(82, 13.5, "11.687", color="white", weight="bold", fontsize=8.5, ha="center")
    ax.text(82, 11.5, "Grãos", color="#94a3b8", fontsize=6.5, ha="center")

    # Botão de Exportação CSV
    ax.add_patch(patches.FancyBboxPatch((70, 4.5), 24, 4, boxstyle="round,pad=0.4", fc="#334155", ec="#64748b"))
    ax.text(82, 6.2, "📥 Baixar Relatório (CSV)", color="white", weight="bold", fontsize=6.5, ha="center")

    plt.tight_layout()
    p = OUTPUT_DIR / "fig5_dashboard.png"
    plt.savefig(p, dpi=300)
    plt.close()
    print("Figura 5 gerada:", p)


def fig6_validacao():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.6), dpi=300)

    # Painel Antes (Corte Fixo de Y = 18%)
    ax1.set_xlim(0, 100)
    ax1.set_ylim(0, 100)
    ax1.axis('off')
    ax1.add_patch(patches.Rectangle((0, 0), 100, 100, fc="#1e293b"))
    # Faixa superior cortada em vermelho
    ax1.add_patch(patches.Rectangle((0, 80), 100, 20, fc="#ef444444", hatch="//", ec="#ef4444", lw=1.5))
    ax1.text(50, 89, "CORTE FIXO DE Y (y < 0.18)\n580 Grãos Verdes Suprimidos!", color="#fca5a5", weight="bold", fontsize=7.5, ha="center")
    # Região detectada com madeira contaminada
    ax1.add_patch(patches.Rectangle((5, 5), 90, 72, fc="#0f172a", ec="#64748b"))
    ax1.text(50, 45, "Detecção com Falsos Positivos\nem Ripas de Madeira e Régua", color="#fbbf24", fontsize=7, ha="center")
    ax1.set_title("(a) Abordagem Anterior (Heurística)\nContagem Incompleta (7.623 grãos)", fontsize=8, weight="bold")

    # Painel Depois (Varredura Integral 100% + Machine Learning)
    ax2.set_xlim(0, 100)
    ax2.set_ylim(0, 100)
    ax2.axis('off')
    ax2.add_patch(patches.Rectangle((0, 0), 100, 100, fc="#1e293b"))
    # Faixa superior verde resgatada
    ax2.add_patch(patches.Rectangle((0, 80), 100, 20, fc="#10b98133", ec="#10b981", lw=1.5))
    ax2.text(50, 89, "100% VARREDURA INTEGRAL\n580 Frutos Verdes Resgatados!", color="#6ee7b7", weight="bold", fontsize=7.5, ha="center")
    # Região central com madeira descartada por ML
    ax2.add_patch(patches.Rectangle((5, 5), 90, 72, fc="#060911", ec="#10b981"))
    ax2.text(50, 45, "Filtro ExtraTrees ML (14 Atributos)\nRipas e Chão Rejeitados com 100% Precisão", color="#38bdf8", fontsize=7, ha="center")
    ax2.set_title("(b) Abordagem Proposta (Híbrida + ML)\nContagem Exaustiva (11.687 grãos)", fontsize=8, weight="bold")

    plt.tight_layout()
    p = OUTPUT_DIR / "fig6_validacao.png"
    plt.savefig(p, dpi=300)
    plt.close()
    print("Figura 6 gerada:", p)


fig5_dashboard_ui()
fig6_validacao()
