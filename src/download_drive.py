#!/usr/bin/env python3
"""
download_drive.py — Download e Organização das Imagens do Google Drive.

Baixa automaticamente as imagens do experimento da variedade Arara da pasta
compartilhada do Google Drive e organiza o split de treino e validação.

Link da pasta:
    https://drive.google.com/drive/folders/14I4xBUsVE2QAh1Hc3LkRJHSgD4E7fld1

Uso:
    python src/download_drive.py [--val-ratio 0.2] [--seed 42]

Autor: [Seu Nome]
Projeto: TCC — Visão Computacional Aplicada à Maturação do Café Arara
"""

from __future__ import annotations

import argparse
import logging
import random
import shutil
import urllib.request
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger("download_drive")

# Mapeamento oficial dos arquivos de imagem da pasta compartilhada do Google Drive
DRIVE_FILES: list[tuple[str, str]] = [
    ("IMG_3280_2.jpg", "1xkOKFq36IJCY6DfLFZp361GR9prUkZM1"),
    ("IMG_3280.JPG",   "1C4vFTkTCHFOCyGhzWBr9MoYj6sMsEDFx"),
    ("IMG_3281_2.jpg", "1N15AWAoP9-BKm6FqFj8kEJcrLyUSsiGr"),
    ("IMG_3281.JPG",   "1c8RpiTt0OJJJR8jlPVL2VA6G7zGGGXHY"),
    ("IMG_3282_2.jpg", "1LB1kESG6CGgARHtHGxH5zvwJ94acOUZv"),
    ("IMG_3282.JPG",   "1CAuNS5r7uTnZAfNkq2cmzIhg4FkUxqaj"),
    ("IMG_3283_2.jpg", "1QbLqwT76uM1FnYMsZCnWB0Dmm6zv5LZ9"),
    ("IMG_3283.JPG",   "10IgpRTuelaGrmwcIFNsACgabNC6iMyp7"),
    ("IMG_3284_2.jpg", "1dojY5omOgrPRE6Gbw_4snpG5oVrDoIh0"),
    ("IMG_3284.JPG",   "194k1m9CrLobEoxd8huY5ZqN4eWbSIAX2"),
    ("IMG_3316.JPG",   "1ape_o70O6l3geQHV3VNUqeTJ2T_itPfu"),
    ("IMG_3317.JPG",   "1cabn67vesKDl1lcpReGoiZnENsP0QO0J"),
    ("IMG_3318.JPG",   "1PsSc34XR1WG0qpW3LNPGa9pfFHUOu1u2"),
    ("IMG_3319.JPG",   "1ArcDrkNQ-OwWdh80QyqPA3r8QU4w0ZxA"),
    ("IMG_3320.JPG",   "1kQub1u6cWKM2A9Y0GhlysOuH0P8mAmdS"),
]


def download_images(output_dir: Path) -> list[Path]:
    """Baixa as imagens do Google Drive para o diretório de destino.

    Args:
        output_dir: Diretório onde as imagens serão salvas.

    Returns:
        Lista de caminhos dos arquivos baixados.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []

    logger.info("Verificando/baixando %d imagens da pasta do Google Drive...", len(DRIVE_FILES))

    for filename, file_id in DRIVE_FILES:
        target_path = output_dir / filename
        if target_path.exists() and target_path.stat().st_size > 1000:
            logger.info("✓ [Cache] %s já existe (%d KB)", filename, target_path.stat().st_size // 1024)
            downloaded.append(target_path)
            continue

        url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download"
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)

        try:
            logger.info("Baixando %s...", filename)
            with urllib.request.urlopen(req, timeout=45) as resp, open(target_path, "wb") as out_f:
                content = resp.read()
                out_f.write(content)
            logger.info("  ✓ Concluído: %s (%d KB)", filename, len(content) // 1024)
            downloaded.append(target_path)
        except Exception as e:
            logger.error("  ✕ Falha ao baixar %s: %s", filename, e)

    return downloaded


def organize_split(
    images: list[Path],
    base_data_dir: Path,
    val_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[list[Path], list[Path]]:
    """Organiza o split das imagens em pastas de treino e validação.

    Args:
        images: Lista de imagens disponíveis.
        base_data_dir: Diretório raiz `data/`.
        val_ratio: Proporção para o conjunto de validação (padrão: 0.2).
        seed: Semente aleatória para reprodutibilidade.

    Returns:
        Tupla com listas de arquivos de treino e validação.
    """
    train_dir = base_data_dir / "images" / "train"
    val_dir = base_data_dir / "images" / "val"
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)

    # Limpar diretórios de destino para manter consistência
    for f in train_dir.glob("*.*"):
        f.unlink()
    for f in val_dir.glob("*.*"):
        f.unlink()

    shuffled = list(images)
    random.seed(seed)
    random.shuffle(shuffled)

    split_idx = int(len(shuffled) * (1.0 - val_ratio))
    train_files = shuffled[:split_idx]
    val_files = shuffled[split_idx:]

    for f in train_files:
        shutil.copy2(f, train_dir / f.name)

    for f in val_files:
        shutil.copy2(f, val_dir / f.name)

    logger.info("Split organizado com sucesso:")
    logger.info("  Treino:    %d imagens em %s", len(train_files), train_dir)
    logger.info("  Validação: %d imagens em %s", len(val_files), val_dir)

    return train_files, val_files


def main() -> None:
    """Ponto de entrada do script."""
    parser = argparse.ArgumentParser(description="Download e preparação das imagens do Google Drive.")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"), help="Diretório para imagens brutas.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="Diretório base de dados.")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Proporção para validação (padrão: 0.2).")
    parser.add_argument("--seed", type=int, default=42, help="Semente aleatória (padrão: 42).")

    args = parser.parse_args()

    downloaded = download_images(args.raw_dir)
    if not downloaded:
        logger.error("Nenhuma imagem pôde ser obtida.")
        return

    train_files, val_files = organize_split(
        images=downloaded,
        base_data_dir=args.data_dir,
        val_ratio=args.val_ratio,
        seed=args.seed,
    )

    print("\n" + "=" * 60)
    print("✅ DOWNLOAD E PREPARAÇÃO CONCLUÍDOS COM SUCESSO!")
    print("=" * 60)
    print(f"Total baixado do Google Drive: {len(downloaded)} imagens")
    print(f"Treino:    {len(train_files)} imagens -> data/images/train/")
    print(f"Validação: {len(val_files)} imagens -> data/images/val/")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
