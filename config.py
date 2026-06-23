"""Configurações centralizadas do pipeline de obituários."""

from __future__ import annotations

import os
from pathlib import Path

# Diretórios
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
SAMPLES_DIR = BASE_DIR / "samples"

# Arquivos padrão — obituários
OUTPUT_CSV = OUTPUT_DIR / "obitos.csv"

# Arquivos padrão — base de clientes (BD.csv)
BD_INPUT_CSV = INPUT_DIR / "BD.csv"
BD_OUTPUT_CSV = OUTPUT_DIR / "BD_processado.csv"
BD_OUTPUT_XLSX = OUTPUT_DIR / "BD_processado.xlsx"
BD_FALECIDOS_CSV = OUTPUT_DIR / "BD_falecidos.csv"

# Consulta CPF genérica
OUTPUT_CPF_CSV = OUTPUT_DIR / "cpf_consulta.csv"
CPF_INPUT_SAMPLE = SAMPLES_DIR / "cpf_entrada.exemplo.csv"

# HTTP
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0
REQUEST_DELAY = 1.0

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# API Sintegra WS — Receita Federal CPF
SINTEGRA_API_URL = "https://www.sintegraws.com.br/api/v1/execute-api.php"
SINTEGRA_PLUGIN = "CPF"
SINTEGRA_TOKEN = os.getenv("SINTEGRA_TOKEN", "")
SINTEGRA_REQUEST_DELAY = float(os.getenv("SINTEGRA_REQUEST_DELAY", "1.5"))

OBITUARY_SOURCES: list[dict[str, str]] = [
    {
        "name": "demo_local",
        "url": str(SAMPLES_DIR / "exemplo.html"),
        "parser": "generic",
        "type": "file",
    },
]

CSV_COLUMNS = [
    "nome",
    "cidade",
    "uf",
    "data_obito",
    "idade",
    "data_nascimento",
    "texto_completo",
    "fonte",
]

CPF_OUTPUT_COLUMNS = [
    "cpf_entrada",
    "data_nascimento_entrada",
    "api_code",
    "api_status",
    "api_message",
    "cpf",
    "nome",
    "nome_mae",
    "data_nascimento",
    "situacao_cadastral",
    "ano_obito",
    "idade",
    "uf",
    "sexo",
    "data_inscricao",
    "qsa_quantidade",
    "falecido",
]

# Colunas de saída do BD.csv processado (Databricks / Power BI)
BD_OUTPUT_COLUMNS = [
    "CPF",
    "Nome",
    "Data de Nascimento",
    "nome_receita",
    "situacao_cadastral",
    "ano_obito",
    "Titular falecido",
    "api_code",
    "api_message",
]

DEDUP_KEYS = ("nome", "cidade", "data_obito")
SITUACAO_FALECIDO = "Titular falecido"
