"""Scoring de matching entre obituários e base de clientes."""

from __future__ import annotations

from datetime import date
from typing import Any

from rapidfuzz import fuzz

from normalizer import normalize_name, normalize_text
from utils import parse_year


def _score_name(obit_name: str, client_name: str) -> float:
    """Similaridade fuzzy entre nomes normalizados (0-100)."""
    left = normalize_name(obit_name)
    right = normalize_name(client_name)
    if not left or not right:
        return 0.0
    return float(fuzz.token_sort_ratio(left, right))


def _score_city(obit_city: str | None, client_city: str | None) -> float:
    """Compara cidade normalizada."""
    left = normalize_text(obit_city or "").lower()
    right = normalize_text(client_city or "").lower()
    if not left or not right:
        return 0.0
    if left == right:
        return 100.0
    return float(fuzz.partial_ratio(left, right))


def _score_age_or_birth(
    obit_age: int | None,
    obit_birth: date | None,
    client_age: int | None,
    client_birth: date | None,
) -> float:
    """Compara idade ou ano de nascimento."""
    if obit_birth and client_birth:
        if obit_birth == client_birth:
            return 100.0
        if obit_birth.year == client_birth.year:
            return 85.0

    if obit_age is not None and client_age is not None:
        diff = abs(obit_age - client_age)
        if diff == 0:
            return 100.0
        if diff <= 1:
            return 90.0
        if diff <= 3:
            return 70.0
        return max(0.0, 60.0 - diff * 5)

    obit_year = obit_birth.year if obit_birth else None
    client_year = client_birth.year if client_birth else parse_year(str(client_birth)) if client_birth else None
    if obit_year and client_year and obit_year == client_year:
        return 85.0

    return 0.0


def score_match(
    obituary: dict[str, Any],
    client: dict[str, Any],
    *,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Calcula score composto para matching antifraude.

    Pesos padrão: nome 0.55, cidade 0.25, idade/nascimento 0.20
    """
    default_weights = {"nome": 0.55, "cidade": 0.25, "idade_nasc": 0.20}
    w = {**default_weights, **(weights or {})}

    name_score = _score_name(obituary.get("nome", ""), client.get("nome", ""))
    city_score = _score_city(obituary.get("cidade"), client.get("cidade"))
    age_score = _score_age_or_birth(
        obituary.get("idade"),
        obituary.get("data_nascimento"),
        client.get("idade"),
        client.get("data_nascimento"),
    )

    total = (
        name_score * w["nome"]
        + city_score * w["cidade"]
        + age_score * w["idade_nasc"]
    )

    return {
        "score_total": round(total, 2),
        "score_nome": round(name_score, 2),
        "score_cidade": round(city_score, 2),
        "score_idade_nasc": round(age_score, 2),
        "obituario": obituary.get("nome"),
        "cliente": client.get("nome"),
    }


def rank_matches(
    obituary: dict[str, Any],
    clients: list[dict[str, Any]],
    *,
    min_score: float = 60.0,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """Ranqueia clientes candidatos para um obituário."""
    scored = [score_match(obituary, client) for client in clients]
    filtered = [item for item in scored if item["score_total"] >= min_score]
    filtered.sort(key=lambda x: x["score_total"], reverse=True)
    return filtered[:top_n]
