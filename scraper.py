"""Coleta de HTML com retry, timeout e suporte a múltiplas URLs."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import requests
from requests.exceptions import RequestException

from config import HEADERS, MAX_RETRIES, REQUEST_DELAY, REQUEST_TIMEOUT, RETRY_BACKOFF

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """Erro genérico de scraping."""


def _read_local_file(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        raise ScraperError(f"Arquivo local não encontrado: {path}")
    return file_path.read_text(encoding="utf-8", errors="replace")


def fetch_html(
    url: str,
    *,
    source_type: str = "http",
    timeout: int = REQUEST_TIMEOUT,
    max_retries: int = MAX_RETRIES,
) -> str:
    """
    Obtém HTML de uma URL HTTP ou arquivo local.

    Args:
        url: Endereço web ou caminho de arquivo.
        source_type: 'http' ou 'file'.
        timeout: Timeout em segundos.
        max_retries: Tentativas em caso de falha transitória.
    """
    if source_type == "file" or url.startswith("file://"):
        local_path = url.removeprefix("file://")
        logger.info("Lendo arquivo local: %s", local_path)
        return _read_local_file(local_path)

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("GET %s (tentativa %d/%d)", url, attempt, max_retries)
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=timeout,
                allow_redirects=True,
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except RequestException as exc:
            last_error = exc
            logger.warning("Falha ao acessar %s: %s", url, exc)
            if attempt < max_retries:
                sleep_time = RETRY_BACKOFF ** (attempt - 1)
                logger.info("Aguardando %.1fs antes de retry...", sleep_time)
                time.sleep(sleep_time)

    raise ScraperError(f"Não foi possível obter HTML de {url}: {last_error}") from last_error


def fetch_multiple(sources: list[dict[str, Any]]) -> list[dict[str, str]]:
    """
    Coleta HTML de múltiplas fontes configuradas.

    Returns:
        Lista de dicts com keys: source_name, url, html, parser.
    """
    results: list[dict[str, str]] = []

    for index, source in enumerate(sources):
        url = source["url"]
        source_name = source.get("name", url)
        source_type = source.get("type", "http")
        parser_name = source.get("parser", "generic")

        try:
            html = fetch_html(url, source_type=source_type)
            results.append(
                {
                    "source_name": source_name,
                    "url": url,
                    "html": html,
                    "parser": parser_name,
                }
            )
        except ScraperError as exc:
            logger.error("[%s] %s", source_name, exc)

        if index < len(sources) - 1 and source_type == "http":
            time.sleep(REQUEST_DELAY)

    logger.info("Coleta concluída: %d/%d fonte(s) com sucesso", len(results), len(sources))
    return results
