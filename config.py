"""Configurações centralizadas do pipeline de obituários."""

from __future__ import annotations

from pathlib import Path

# Diretórios
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_CSV = OUTPUT_DIR / "obitos.csv"
SAMPLES_DIR = BASE_DIR / "samples"

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

# URLs de obituários públicos brasileiros (adicione novas fontes aqui)
# Cada entrada pode definir um parser específico ou usar "generic".
OBITUARY_SOURCES: list[dict[str, str]] = [
    {
        "name": "demo_local",
        "url": str(SAMPLES_DIR / "exemplo.html"),
        "parser": "generic",
        "type": "file",
    },
    # Exemplos de fontes reais — descomente e ajuste conforme necessário:
    # {
    #     "name": "exemplo_funeral",
    #     "url": "https://www.exemplo.com.br/obituarios",
    #     "parser": "generic",
    #     "type": "http",
    # },
]

# Colunas do CSV de saída
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

# Chaves usadas na deduplicação
DEDUP_KEYS = ("nome", "cidade", "data_obito")
