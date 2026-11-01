#!/usr/bin/env python3
"""
train.py — Script de Treinamento do Modelo YOLOv8.

Configura e executa o treinamento do modelo de detecção de objetos
YOLOv8 para classificação do nível de maturação do café Arara.

Uso:
    python src/train.py \\
        --data dataset.yaml \\
        --epochs 100 \\
        --imgsz 640 \\
        --batch 16 \\
        --model yolov8n.pt \\
        --project outputs \\
        --name cafe_arara_v1

Autor: [Seu Nome]
Projeto: TCC — Visão Computacional Aplicada à Maturação do Café Arara
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from ultralytics import YOLO

# ---------------------------------------------------------------------------
# Configuração de logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger("train")


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def validate_dataset_config(data_path: Path) -> None:
    """Valida se o arquivo de configuração do dataset existe e é legível.

    Args:
        data_path: Caminho para o arquivo ``dataset.yaml``.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        ValueError: Se o arquivo estiver malformado.
    """
    if not data_path.exists():
        raise FileNotFoundError(
            f"Arquivo de configuração do dataset não encontrado: {data_path}\n"
            f"Certifique-se de que 'dataset.yaml' está na raiz do projeto."
        )

    # Validação básica do conteúdo YAML
    try:
        import yaml
        with open(data_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        required_keys = {"train", "val", "nc", "names"}
        missing = required_keys - set(config.keys())
        if missing:
            raise ValueError(
                f"Chaves obrigatórias ausentes no dataset.yaml: {missing}"
            )

        nc = config["nc"]
        names = config["names"]
        if isinstance(names, dict) and len(names) != nc:
            raise ValueError(
                f"Inconsistência: nc={nc} mas {len(names)} classes definidas em 'names'."
            )

        logger.info(
            "Dataset config validado — %d classes: %s",
            nc,
            list(names.values()) if isinstance(names, dict) else names,
        )

    except ImportError:
        logger.warning("PyYAML não disponível; pulando validação detalhada do YAML.")
    except Exception as e:
        raise ValueError(f"Erro ao validar dataset.yaml: {e}") from e


def check_data_directories(data_path: Path) -> None:
    """Verifica se os diretórios de treino e validação contêm imagens.

    Args:
        data_path: Caminho para o arquivo ``dataset.yaml``.
    """
    try:
        import yaml
        with open(data_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        base = Path(config.get("path", "."))
        train_dir = base / config.get("train", "data/images/train")
        val_dir = base / config.get("val", "data/images/val")

        for label, d in [("Treino", train_dir), ("Validação", val_dir)]:
            if not d.exists():
                logger.warning("⚠ Diretório de %s não encontrado: %s", label, d)
            else:
                n_files = len([f for f in d.iterdir() if f.is_file()])
                if n_files == 0:
                    logger.warning("⚠ Diretório de %s está vazio: %s", label, d)
                else:
                    logger.info("✓ %s: %d arquivo(s) em %s", label, n_files, d)

    except Exception:
        pass  # Validação opcional, não bloquear o treinamento


def export_best_weights(
    run_dir: Path,
    destination: Path = Path("weights/best.pt"),
) -> None:
    """Copia o melhor modelo treinado para a pasta de pesos.

    Args:
        run_dir: Diretório da run de treinamento (ex: ``outputs/cafe_arara_v1``).
        destination: Caminho de destino para o arquivo ``best.pt``.
    """
    best_pt = run_dir / "weights" / "best.pt"
    if best_pt.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best_pt, destination)
        logger.info("[OK] Melhor modelo copiado para: %s", destination)
    else:
        logger.warning("[AVISO] Arquivo best.pt nao encontrado em: %s", best_pt)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def main() -> None:
    """Ponto de entrada principal para o treinamento do modelo YOLO."""
    parser = argparse.ArgumentParser(
        description="Treinamento YOLOv8 — Detecção de Maturação do Café Arara",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplo:
  python src/train.py --data dataset.yaml --epochs 100 --batch 16
        """,
    )

    # Argumentos do dataset e modelo
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("dataset.yaml"),
        help="Caminho para o arquivo YAML de configuração do dataset (padrão: dataset.yaml).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="yolov8n.pt",
        help="Modelo base pré-treinado (padrão: yolov8n.pt). "
             "Opções: yolov8n.pt, yolov8s.pt, yolov8m.pt, yolov8l.pt, yolov8x.pt",
    )

    # Hiperparâmetros de treinamento
    parser.add_argument("--epochs", type=int, default=100, help="Número de épocas (padrão: 100).")
    parser.add_argument("--imgsz", type=int, default=640, help="Tamanho da imagem de entrada (padrão: 640).")
    parser.add_argument("--batch", type=int, default=16, help="Tamanho do batch (padrão: 16).")
    parser.add_argument("--lr0", type=float, default=0.01, help="Learning rate inicial (padrão: 0.01).")
    parser.add_argument("--patience", type=int, default=20, help="Early stopping patience (padrão: 20).")
    parser.add_argument("--workers", type=int, default=4, help="Número de data-loader workers (padrão: 4).")

    # Augmentação
    parser.add_argument("--augment", action="store_true", default=True, help="Ativar augmentação (padrão: True).")
    parser.add_argument("--mosaic", type=float, default=1.0, help="Probabilidade de Mosaic augmentation (padrão: 1.0).")

    # Saída
    parser.add_argument(
        "--project",
        type=str,
        default="outputs",
        help="Diretório raiz para salvar resultados (padrão: outputs/).",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="cafe_arara_v1",
        help="Nome da run de treinamento (padrão: cafe_arara_v1).",
    )

    # Opções adicionais
    parser.add_argument("--device", type=str, default="", help="Dispositivo: '' (auto), 'cpu', '0' (GPU 0), etc.")
    parser.add_argument("--resume", action="store_true", help="Retomar treinamento do último checkpoint.")
    parser.add_argument("--no-export", action="store_true", help="Não copiar best.pt para weights/ ao final.")

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # 1. Validar dataset
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("🔍 Validando configuração do dataset...")
    logger.info("=" * 60)

    validate_dataset_config(args.data)
    check_data_directories(args.data)

    # ------------------------------------------------------------------
    # 2. Carregar modelo base
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("=" * 60)
    logger.info("[MODEL] Carregando modelo base: %s", args.model)
    logger.info("=" * 60)

    try:
        model = YOLO(args.model)
        logger.info("Modelo carregado com sucesso.")
    except Exception as e:
        logger.error("Falha ao carregar o modelo '%s': %s", args.model, e)
        sys.exit(1)

    # ------------------------------------------------------------------
    # 3. Configurar e iniciar treinamento
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("=" * 60)
    logger.info("[TRAIN] Iniciando treinamento")
    logger.info("   Epocas:      %d", args.epochs)
    logger.info("   Imagem:      %dpx", args.imgsz)
    logger.info("   Batch:       %d", args.batch)
    logger.info("   LR0:         %f", args.lr0)
    logger.info("   Patience:    %d", args.patience)
    logger.info("   Dispositivo: %s", args.device or "auto")
    logger.info("=" * 60)

    try:
        results = model.train(
            data=str(args.data),
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            lr0=args.lr0,
            patience=args.patience,
            workers=args.workers,
            augment=args.augment,
            mosaic=args.mosaic,
            project=args.project,
            name=args.name,
            device=args.device if args.device else None,
            resume=args.resume,
            verbose=True,
            save=True,
            save_period=10,     # Salvar checkpoint a cada 10 épocas
            plots=True,         # Gerar gráficos de métricas
            exist_ok=True,      # Permitir sobrescrever runs existentes
        )
    except Exception as e:
        logger.error("Erro durante o treinamento: %s", e)
        sys.exit(1)

    # ------------------------------------------------------------------
    # 4. Pós-treinamento
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("=" * 60)
    logger.info("[OK] Treinamento concluido!")
    logger.info("=" * 60)

    run_dir = Path(args.project) / args.name
    logger.info("Resultados salvos em: %s", run_dir)

    # Exportar best.pt
    if not args.no_export:
        export_best_weights(run_dir)

    # Sumário final
    print("\n" + "=" * 60)
    print("[SUMMARY] SUMARIO DO TREINAMENTO")
    print("=" * 60)
    print(f"   Modelo base:      {args.model}")
    print(f"   Epocas:           {args.epochs}")
    print(f"   Resultados em:    {run_dir}")
    print(f"   Melhor peso:      weights/best.pt")
    print(f"\n   Proximo passo:    streamlit run app/app.py")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
