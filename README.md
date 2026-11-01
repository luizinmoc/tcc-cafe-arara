# ☕ Visão Computacional Aplicada à Identificação e Contagem Automática do Nível de Maturação do Café Arara

<p align="center">
  <img src="assets/banner_placeholder.png" alt="Banner do Projeto" width="720"/>
</p>

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-purple?logo=yolo)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red?logo=streamlit)
![License](https://img.shields.io/badge/License-MIT-green)

## 📋 Sobre o Projeto

Trabalho de Conclusão de Curso que utiliza **Visão Computacional** com modelos de detecção **YOLOv8** para identificar, classificar e contabilizar automaticamente o nível de maturação dos frutos de café da variedade **Arara** — cuja particularidade botânica é que os frutos maduros apresentam coloração **amarelada**, e não vermelha como nas variedades tradicionais.

### Classes de Classificação

| Classe | Descrição | Cor Predominante |
|---|---|---|
| `cafe_amarelado` | Frutos maduros (ponto ideal de colheita) | Amarelo / Amarelo-alaranjado |
| `cafe_verde` | Frutos imaturos (ainda em desenvolvimento) | Verde |
| `cafe_preto` | Frutos secos / passados / defeituosos | Preto / Marrom-escuro |

## 🏗️ Estrutura do Repositório

```
tcc-cafe-arara/
├── app/
│   └── app.py                 # Dashboard Streamlit (interface web)
├── assets/                    # Imagens e recursos visuais do README
├── data/
│   ├── images/
│   │   ├── train/             # Imagens de treinamento
│   │   └── val/               # Imagens de validação
│   └── labels/
│       ├── train/             # Anotações YOLO (.txt) de treinamento
│       └── val/               # Anotações YOLO (.txt) de validação
├── outputs/                   # Resultados de treinamento (runs/)
├── src/
│   ├── __init__.py
│   ├── dataset_prep.py        # Preparação e split do dataset
│   ├── train.py               # Script de treinamento do modelo
│   └── utils.py               # Funções utilitárias compartilhadas
├── weights/
│   └── .gitkeep               # Pesos do modelo treinado (best.pt)
├── .gitignore
├── dataset.yaml               # Configuração das classes YOLO
├── requirements.txt           # Dependências do projeto
└── README.md                  # Este arquivo
```

## ⚙️ Pré-requisitos

- **Python** 3.10 ou superior
- **pip** (gerenciador de pacotes)
- **GPU com CUDA** (recomendado para treinamento; CPU funciona para inferência)
- Imagens anotadas no formato **YOLO** (bounding boxes `.txt`)

## 🚀 Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/<seu-usuario>/tcc-cafe-arara.git
cd tcc-cafe-arara
```

### 2. Crie um ambiente virtual (recomendado)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

## 📂 Imagens do Experimento (Google Drive) e Dataset

As 15 imagens de alta resolução da colheita do experimento já estão integradas ao projeto:
- **Origem**: [Google Drive - Imagens Colheita Experimento](https://drive.google.com/drive/folders/14I4xBUsVE2QAh1Hc3LkRJHSgD4E7fld1)
- **Local bruto**: `data/raw/` (15 imagens originais)
- **Imagens de Treino**: `data/images/train/` (12 imagens, 80%)
- **Imagens de Validação**: `data/images/val/` (3 imagens, 20%)

Para resincronizar ou baixar novamente as imagens do Drive a qualquer momento:

```bash
python src/download_drive.py --val-ratio 0.2 --seed 42
```

## ⚡ Contabilização em Lote dos Grãos (Drive)

Para rodar a contagem e classificação de todas as 15 imagens do experimento de uma só vez via terminal:

```bash
python src/count_batch.py --input-dir data/raw --output-dir outputs
```

Isso gera automaticamente:
- `outputs/contagem_lote.csv`: Tabela com contagens detalhadas por classe para cada imagem.
- `outputs/contagem_lote.json`: Resumo estruturado das métricas.
- `outputs/inferences/`: Imagens anotadas com os frutos delimitados.

## 📂 Preparação de Imagens Anotadas (Split Treino/Validação)

Ao gerar anotações manuais YOLO (`.txt`), organize os pares usando:

```bash
python src/dataset_prep.py \
    --images-dir data/raw \
    --labels-dir data/raw_labels \
    --output-dir data \
    --val-ratio 0.2 \
    --seed 42
```

## 🏋️ Treinamento do Modelo

```bash
python src/train.py \
    --data dataset.yaml \
    --epochs 100 \
    --imgsz 640 \
    --batch 16 \
    --model yolov8n.pt \
    --project outputs \
    --name cafe_arara_v1
```

> **Dica**: Para máquinas com pouca VRAM, reduza o `--batch` para 8 ou 4.

Após o treinamento, copie o melhor peso para a pasta `weights/`:

```bash
cp outputs/cafe_arara_v1/weights/best.pt weights/best.pt
```

## 🖥️ Dashboard Web (Streamlit)

```bash
streamlit run app/app.py
```

Acesse `http://localhost:8501` no navegador. Na interface você poderá:

1. 📤 **Fazer upload** de uma imagem do cafeeiro
2. ⚙️ **Ajustar** o limiar de confiança da detecção
3. 🔍 **Processar** a imagem com o modelo treinado
4. 📊 **Visualizar** a imagem anotada com bounding boxes e cards de contagem por classe

## 📈 Métricas Esperadas

| Métrica | Descrição |
|---|---|
| **mAP@50** | Mean Average Precision a IoU 0.50 |
| **mAP@50:95** | Mean Average Precision de IoU 0.50 a 0.95 |
| **Precision** | Taxa de verdadeiros positivos |
| **Recall** | Taxa de detecção dos frutos presentes |

## 🛠️ Stack Tecnológica

| Tecnologia | Uso |
|---|---|
| [Ultralytics YOLOv8](https://docs.ultralytics.com/) | Detecção de objetos (treinamento e inferência) |
| [OpenCV](https://opencv.org/) | Manipulação e processamento de imagem |
| [Streamlit](https://streamlit.io/) | Interface web interativa |
| [NumPy](https://numpy.org/) | Computação numérica |
| [Pillow](https://pillow.readthedocs.io/) | Carregamento e conversão de imagens |

## 📝 Licença

Este projeto está licenciado sob a licença MIT. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.

## 👤 Autor

**Luiz Gustavo Souza Santos**
- Curso: Engenharia de Sistemas
- Instituição: Unimontes
- Orientador(a): Steve Lacerda

---

> *Desenvolvido como Trabalho de Conclusão de Curso — 2026*
