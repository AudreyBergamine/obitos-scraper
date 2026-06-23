"""Funções auxiliares: datas, idade, logging e deduplicação."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

import regex

logger = logging.getLogger(__name__)

DATE_BR_PATTERN = regex.compile(
    r"(?<!\d)(0?[1-9]|[12]\d|3[01])[/\-.](0?[1-9]|1[0-2])[/\-.](\d{4})(?!\d)"
)
YEAR_PATTERN = regex.compile(r"(?<!\d)(19\d{2}|20[0-2]\d)(?!\d)")


def setup_logging(level: int = logging.INFO) -> None:
    """Configura logging básico para o pipeline."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_date_br(value: str | None) -> date | None:
    """Converte string dd/mm/yyyy (ou variantes) em date."""
    if not value:
        return None

    text = str(value).strip()
    match = DATE_BR_PATTERN.search(text)
    if not match:
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text[:10], fmt).date()
            except ValueError:
                continue
        return None

    day, month, year = match.groups()
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        logger.debug("Data inválida: %s", text)
        return None


def parse_year(value: str | None) -> int | None:
    """Extrai ano de 4 dígitos de um texto."""
    if not value:
        return None
    match = YEAR_PATTERN.search(str(value))
    return int(match.group(1)) if match else None


def infer_birth_date(
    birth_date: date | None,
    birth_year: int | None,
    age: int | None,
    death_date: date | None,
) -> date | None:
    """
    Aplica regras de fallback para data de nascimento.

    Prioridade:
    1. Data completa já extraída
    2. Ano detectado (01/01/YYYY)
    3. Inferência via idade e data de óbito
    """
    if birth_date:
        return birth_date

    if birth_year:
        return date(birth_year, 1, 1)

    if age is not None and death_date is not None:
        inferred_year = death_date.year - age
        if 1900 <= inferred_year <= date.today().year:
            return date(inferred_year, 1, 1)

    return None


def calculate_age(birth_date: date | None, death_date: date | None) -> int | None:
    """Calcula idade em anos completos."""
    if not birth_date or not death_date:
        return None
    age = death_date.year - birth_date.year
    if (death_date.month, death_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age if age >= 0 else None


def clean_text(value: str | None) -> str:
    """Normaliza espaços e quebras de linha em texto livre."""
    if not value:
        return ""
    text = regex.sub(r"\s+", " ", str(value)).strip()
    return text


def null_safe(value: Any) -> Any:
    """Converte strings vazias e valores falsy em None para campos opcionais."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def format_date(value: date | None) -> str:
    """Formata date para CSV (ISO) ou string vazia."""
    return value.isoformat() if value else ""


def deduplicate_records(records: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    """Remove duplicatas com base em chaves normalizadas."""
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []

    for record in records:
        fingerprint = tuple(
            (record.get(key) or "").strip().lower() if isinstance(record.get(key), str) else record.get(key)
            for key in keys
        )
        if fingerprint in seen:
            logger.debug("Duplicata ignorada: %s", fingerprint)
            continue
        seen.add(fingerprint)
        unique.append(record)

    removed = len(records) - len(unique)
    if removed:
        logger.info("Deduplicação removeu %d registro(s)", removed)

    return unique


def split_city_uf(location: str | None) -> tuple[str | None, str | None]:
    """Separa 'Cidade/UF' ou 'Cidade - UF' em componentes."""
    if not location:
        return None, None

    text = clean_text(location)
    patterns = [
        r"^(?P<cidade>.+?)\s*[/\-|]\s*(?P<uf>[A-Z]{2})$",
        r"^(?P<cidade>.+?)\s*,\s*(?P<uf>[A-Z]{2})$",
    ]
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if match:
            cidade = match.group("cidade").strip()
            uf = match.group("uf").upper()
            return cidade, uf

    return text, None
