"""Extração estruturada de obituários via HTML e regex."""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any, Callable

import regex
from bs4 import BeautifulSoup, Tag

from normalizer import normalize_cpf, normalize_name, normalize_text
from utils import (
    calculate_age,
    clean_text,
    infer_birth_date,
    null_safe,
    parse_date_br,
    parse_year,
    split_city_uf,
)

logger = logging.getLogger(__name__)

# --- Padrões regex para extração textual ---

RE_BIRTH_FULL = regex.compile(
    r"nascid[oa]\s+(?:em\s+)?"
    r"((?:0?[1-9]|[12]\d|3[01])[/\-.](?:0?[1-9]|1[0-2])[/\-.]\d{4}|\d{4})",
    regex.IGNORECASE,
)
RE_BIRTH_YEAR = regex.compile(
    r"nascid[oa]\s+(?:em\s+)?((?:19|20)\d{2})",
    regex.IGNORECASE,
)
RE_YEAR_RANGE = regex.compile(
    r"\(\s*((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2})\s*\)"
)
RE_DEATH_DATE = regex.compile(
    r"(?:faleceu|falecimento|óbito|obito|partiu)\s+(?:em\s+)?"
    r"((?:0?[1-9]|[12]\d|3[01])[/\-.](?:0?[1-9]|1[0-2])[/\-.]\d{4})",
    regex.IGNORECASE,
)
RE_AGE = regex.compile(
    r"(?:aos|com|tinha|completou)\s+(\d{1,3})\s+anos?",
    regex.IGNORECASE,
)
RE_CPF = regex.compile(
    r"(?:cpf\s*[:\-]?\s*)?"
    r"(\d{3}\.?\d{3}\.?\d{3}[-.]?\d{2}|\d{11})",
    regex.IGNORECASE,
)
RE_CITY_UF = regex.compile(
    r"(?:cidade|municipio|município|local)\s*[:\-]?\s*"
    r"([A-Za-zÀ-ÿ\s\.\']+?)\s*[/,\-]\s*([A-Z]{2})",
    regex.IGNORECASE,
)

NAME_SELECTORS = [
    ".obituary h1",
    ".obituary h2",
    ".obituary h3",
    ".obituario h1",
    ".obituario h2",
    "article h1",
    "article h2",
    ".nome",
    ".name",
    "h1",
    "h2",
]

CITY_SELECTORS = [
    ".city",
    ".cidade",
    ".location",
    ".local",
    "[class*='city']",
    "[class*='cidade']",
    "[class*='local']",
]


def extract_birth_from_text(text: str) -> tuple[date | None, int | None]:
    """Extrai data ou ano de nascimento via regex."""
    match_full = RE_BIRTH_FULL.search(text)
    if match_full:
        raw = match_full.group(1)
        parsed = parse_date_br(raw)
        if parsed:
            return parsed, None
        year = parse_year(raw)
        if year:
            return None, year

    match_year = RE_BIRTH_YEAR.search(text)
    if match_year:
        return None, int(match_year.group(1))

    match_range = RE_YEAR_RANGE.search(text)
    if match_range:
        return None, int(match_range.group(1))

    return None, None


def extract_death_from_text(text: str) -> date | None:
    """Extrai data de óbito via regex."""
    match = RE_DEATH_DATE.search(text)
    if match:
        return parse_date_br(match.group(1))

    match_range = RE_YEAR_RANGE.search(text)
    if match_range:
        return date(int(match_range.group(2)), 1, 1)

    return None


def extract_age_from_text(text: str) -> int | None:
    """Extrai idade informada no texto."""
    match = RE_AGE.search(text)
    if match:
        age = int(match.group(1))
        return age if 0 < age <= 130 else None
    return None


def extract_cpf_from_text(text: str) -> str | None:
    """Extrai CPF quando presente no texto."""
    match = RE_CPF.search(text)
    if not match:
        return None
    return normalize_cpf(match.group(1))


def extract_city_uf_from_text(text: str) -> tuple[str | None, str | None]:
    """Tenta extrair cidade/UF de padrões textuais."""
    match = RE_CITY_UF.search(text)
    if match:
        return match.group(1).strip(), match.group(2).upper()

    for line in text.split("."):
        city, uf = split_city_uf(line.strip())
        if uf:
            return city, uf

    return None, None


def _first_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            text = clean_text(element.get_text(" ", strip=True))
            if text:
                return text
    return ""


def _is_nested(child: Tag, parent: Tag) -> bool:
    """Verifica se child está contido em parent."""
    for ancestor in child.parents:
        if ancestor is parent:
            return True
    return False


def _collect_obituary_blocks(soup: BeautifulSoup) -> list[Tag]:
    """
    Coleta blocos de obituário evitando duplicatas por aninhamento.

    Prioriza seletores específicos (.obituary, article) e só usa
    containers genéricos (main, body) quando nenhum bloco específico existe.
    """
    specific_selectors = [
        ".obituary",
        ".obituario",
        ".obit-text",
        ".texto",
        "article",
    ]
    generic_selectors = [".content", "main"]

    blocks: list[Tag] = []
    for selector in specific_selectors:
        blocks.extend(soup.select(selector))

    if not blocks:
        for selector in generic_selectors:
            blocks.extend(soup.select(selector))

    if not blocks:
        return [soup.body] if soup.body else [soup]

    # Remove blocos genéricos que apenas envolvem blocos específicos
    filtered: list[Tag] = []
    for block in blocks:
        if any(_is_nested(specific, block) for specific in blocks if specific is not block):
            continue
        filtered.append(block)

    seen_ids: set[int] = set()
    unique_blocks: list[Tag] = []
    for block in filtered:
        block_id = id(block)
        if block_id not in seen_ids:
            seen_ids.add(block_id)
            unique_blocks.append(block)

    return unique_blocks


def _parse_block(block: Tag, source_url: str) -> dict[str, Any] | None:
    """Extrai um registro de um bloco HTML de obituário."""
    block_soup = BeautifulSoup(str(block), "lxml")
    texto_completo = clean_text(block.get_text(" ", strip=True))

    if len(texto_completo) < 15:
        return None

    nome = _first_text(block_soup, NAME_SELECTORS)
    if not nome or len(nome.split()) < 2:
        heading = block_soup.find(re.compile(r"^h[1-4]$"))
        if heading:
            nome = clean_text(heading.get_text(strip=True))

    cidade_html = _first_text(block_soup, CITY_SELECTORS)
    cidade, uf = split_city_uf(cidade_html) if cidade_html else (None, None)

    birth_date, birth_year = extract_birth_from_text(texto_completo)
    death_date = extract_death_from_text(texto_completo)
    idade = extract_age_from_text(texto_completo)
    cpf = extract_cpf_from_text(texto_completo)

    if not cidade:
        cidade_txt, uf_txt = extract_city_uf_from_text(texto_completo)
        cidade = cidade or cidade_txt
        uf = uf or uf_txt

    data_nascimento = infer_birth_date(birth_date, birth_year, idade, death_date)

    if idade is None and data_nascimento and death_date:
        idade = calculate_age(data_nascimento, death_date)

    if not nome:
        logger.debug("Bloco ignorado por falta de nome: %s", source_url)
        return None

    record: dict[str, Any] = {
        "nome": normalize_text(nome),
        "nome_normalizado": normalize_name(nome),
        "cpf": cpf,
        "cidade": null_safe(cidade),
        "uf": null_safe(uf),
        "data_obito": death_date,
        "idade": idade,
        "data_nascimento": data_nascimento,
        "texto_completo": texto_completo,
        "fonte": source_url,
    }
    return record


def parse_obituary_html(html: str, source_url: str) -> list[dict[str, Any]]:
    """
    Extrai registros de obituário a partir de HTML.

    Suporta páginas com um ou múltiplos blocos `.obituary`, `article`, etc.
    """
    soup = BeautifulSoup(html, "lxml")
    blocks = _collect_obituary_blocks(soup)

    records: list[dict[str, Any]] = []
    for block in blocks:
        try:
            record = _parse_block(block, source_url)
            if record:
                records.append(record)
        except Exception as exc:
            logger.warning("Erro ao parsear bloco em %s: %s", source_url, exc)

    if not records:
        logger.warning("Nenhum registro extraído de %s", source_url)

    return records


PARSERS: dict[str, Callable[[str, str], list[dict[str, Any]]]] = {
    "generic": parse_obituary_html,
}


def get_parser(name: str) -> Callable[[str, str], list[dict[str, Any]]]:
    """Retorna parser registrado ou fallback genérico."""
    return PARSERS.get(name, parse_obituary_html)
