"""Processamento em lote de CSV com CPF + data de nascimento."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from config import CPF_OUTPUT_COLUMNS
from cpf_client import CpfApiError, CpfApiResponse, SintegraCpfClient
from normalizer import normalize_cpf
from utils import format_date_br, format_date_ddmmaaaa, parse_date_br

logger = logging.getLogger(__name__)

CPF_INPUT_ALIASES = {"cpf", "documento", "numero_cpf", "nr_cpf"}
BIRTH_INPUT_ALIASES = {
    "data_nascimento",
    "data-nascimento",
    "nascimento",
    "dt_nascimento",
    "data_nasc",
}


def _normalize_column(name: str) -> str:
    return str(name).strip().lower().replace("-", "_").replace(" ", "_")


def _detect_columns(df: pd.DataFrame) -> tuple[str, str]:
    """Detecta colunas de CPF e data de nascimento no CSV de entrada."""
    mapping = {_normalize_column(col): col for col in df.columns}

    cpf_col = next((mapping[a] for a in CPF_INPUT_ALIASES if a in mapping), None)
    birth_col = next((mapping[a] for a in BIRTH_INPUT_ALIASES if a in mapping), None)

    if not cpf_col or not birth_col:
        raise ValueError(
            "CSV deve conter colunas 'cpf' e 'data_nascimento'. "
            f"Colunas encontradas: {list(df.columns)}"
        )

    return cpf_col, birth_col


def _prepare_row(cpf_raw: Any, birth_raw: Any) -> tuple[str | None, str | None, str | None]:
    """
    Valida e normaliza uma linha de entrada.

    Returns:
        (cpf_digits, data_api_ddmmaaaa, data_entrada_legivel)
    """
    cpf_digits = normalize_cpf(str(cpf_raw) if cpf_raw is not None else "")
    birth_parsed = parse_date_br(str(birth_raw) if birth_raw is not None else "")
    birth_api = format_date_ddmmaaaa(birth_parsed) if birth_parsed else None
    birth_display = format_date_br(birth_parsed) if birth_parsed else str(birth_raw or "")

    return cpf_digits, birth_api, birth_display


def _error_row(
    cpf_entrada: str,
    data_entrada: str,
    message: str,
    *,
    code: str = "",
    status: str = "ERROR",
) -> dict[str, Any]:
    row = {col: "" for col in CPF_OUTPUT_COLUMNS}
    row.update(
        {
            "cpf_entrada": cpf_entrada,
            "data_nascimento_entrada": data_entrada,
            "api_code": code,
            "api_status": status,
            "api_message": message,
            "falecido": False,
            "qsa_quantidade": 0,
        }
    )
    return row


def process_cpf_csv(
    input_path: Path,
    *,
    client: SintegraCpfClient | None = None,
    dry_run: bool = False,
) -> pd.DataFrame:
    """
    Lê CSV de entrada, consulta API e retorna DataFrame estruturado.

    CSV de entrada esperado (colunas flexíveis):
        cpf,data_nascimento
        02631521060,24/06/1988
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    df_in = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    cpf_col, birth_col = _detect_columns(df_in)

    logger.info("Processando %d linha(s) de %s", len(df_in), input_path.name)

    api_client = client or SintegraCpfClient()
    rows: list[dict[str, Any]] = []

    for index, record in df_in.iterrows():
        cpf_raw = record.get(cpf_col, "")
        birth_raw = record.get(birth_col, "")
        cpf_digits, birth_api, birth_display = _prepare_row(cpf_raw, birth_raw)

        if not cpf_digits:
            rows.append(_error_row(str(cpf_raw), birth_display, "CPF inválido na linha de entrada."))
            continue

        if not birth_api:
            rows.append(
                _error_row(
                    cpf_digits,
                    birth_display,
                    "Data de nascimento inválida. Use dd/mm/aaaa ou yyyy-mm-dd.",
                )
            )
            continue

        if dry_run:
            rows.append(
                {
                    "cpf_entrada": cpf_digits,
                    "data_nascimento_entrada": birth_display,
                    "api_code": "DRY_RUN",
                    "api_status": "OK",
                    "api_message": "Validação local OK (sem chamada à API).",
                    "cpf": "",
                    "nome": "",
                    "nome_mae": "",
                    "data_nascimento": "",
                    "situacao_cadastral": "",
                    "ano_obito": "",
                    "idade": "",
                    "uf": "",
                    "sexo": "",
                    "data_inscricao": "",
                    "qsa_quantidade": 0,
                    "falecido": False,
                }
            )
            continue

        try:
            response: CpfApiResponse = api_client.consultar(cpf_digits, birth_api)
            row = response.to_flat_dict(cpf_digits, birth_display)
            rows.append(row)

            if response.success:
                logger.info(
                    "Linha %s: %s | situação=%s | ano_obito=%s",
                    index,
                    response.nome or "—",
                    response.situacao_cadastral or "—",
                    response.ano_obito or "—",
                )
            else:
                logger.warning(
                    "Linha %s: code=%s | %s",
                    index,
                    response.code,
                    response.message,
                )
        except CpfApiError as exc:
            rows.append(_error_row(cpf_digits, birth_display, str(exc)))

    return pd.DataFrame(rows, columns=CPF_OUTPUT_COLUMNS)


def save_cpf_results(df: pd.DataFrame, output_path: Path) -> Path:
    """Salva resultados da consulta CPF em CSV."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info("Resultado salvo em %s (%d linhas)", output_path, len(df))
    return output_path
