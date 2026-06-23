"""Normalização de nomes e textos para matching."""

from __future__ import annotations

import unicodedata

import regex


def remove_accents(text: str) -> str:
    """Remove acentos mantendo caracteres base."""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def normalize_name(name: str | None) -> str:
    """
    Normaliza nome para comparação:
    - uppercase
    - remove acentos
    - trim e colapsa espaços
    """
    if not name:
        return ""

    text = regex.sub(r"\s+", " ", str(name).strip())
    text = remove_accents(text).upper()
    return text


def normalize_text(text: str | None) -> str:
    """Normaliza texto livre (espaços, trim)."""
    if not text:
        return ""
    return regex.sub(r"\s+", " ", str(text).strip())


def normalize_cpf(cpf: str | None) -> str | None:
    """Extrai apenas dígitos do CPF."""
    if not cpf:
        return None
    digits = regex.sub(r"\D", "", str(cpf))
    return digits if len(digits) == 11 else None
