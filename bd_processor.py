"""Processamento da base BD.csv: consulta CPF e flag de titular falecido."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from config import BD_OUTPUT_COLUMNS, SITUACAO_FALECIDO
from cpf_client import CpfApiError, CpfApiResponse, SintegraCpfClient
from cpf_batch import _prepare_row
from normalizer import normalize_cpf
from utils import format_date_br, parse_date_br

logger = logging.getLogger(__name__)

CPF_ALIASES = {"cpf", "documento", "numero_cpf"}
NOME_ALIASES = {"nome", "name", "cliente", "nome_cliente"}
BIRTH_ALIASES = {
    "data de nascimento",
    "data_nascimento",
    "data-nascimento",
    "nascimento",
    "dt_nascimento",
}


def _normalize_column(name: str) -> str:
    return str(name).strip().lower().replace("_", " ").replace("-", " ")


def _detect_bd_columns(df: pd.DataFrame) -> tuple[str, str, str]:
    mapping = {_normalize_column(col): col for col in df.columns}

    cpf_col = next((mapping[a] for a in CPF_ALIASES if a in mapping), None)
    nome_col = next((mapping[a] for a in NOME_ALIASES if a in mapping), None)
    birth_col = next((mapping[a] for a in BIRTH_ALIASES if a in mapping), None)

    if not cpf_col or not nome_col or not birth_col:
        raise ValueError(
            "BD.csv deve conter as colunas CPF, Nome e Data de Nascimento. "
            f"Encontradas: {list(df.columns)}"
        )

    return cpf_col, nome_col, birth_col


def is_titular_falecido(situacao_cadastral: str | None) -> int:
    """Retorna 1 se situacao_cadastral for 'Titular falecido', senão 0."""
    if not situacao_cadastral:
        return 0
    return 1 if situacao_cadastral.strip().lower() == SITUACAO_FALECIDO.lower() else 0


def _base_error_row(
    cpf: str,
    nome: str,
    data_nascimento: str,
    message: str,
    *,
    code: str = "",
) -> dict[str, Any]:
    return {
        "CPF": cpf,
        "Nome": nome,
        "Data de Nascimento": data_nascimento,
        "nome_receita": "",
        "situacao_cadastral": "",
        "ano_obito": "",
        "Titular falecido": 0,
        "api_code": code,
        "api_message": message,
    }


def process_bd_csv(
    input_path: Path,
    *,
    client: SintegraCpfClient | None = None,
    dry_run: bool = False,
) -> pd.DataFrame:
    """
    Lê input/BD.csv, consulta a API Sintegra e enriquece com flag de falecimento.

    Colunas de entrada esperadas: CPF, Nome, Data de Nascimento
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {input_path}\n"
            f"Coloque seu arquivo em: {input_path.parent / 'BD.csv'}"
        )

    df_in = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    cpf_col, nome_col, birth_col = _detect_bd_columns(df_in)

    logger.info("Processando BD: %d registro(s) em %s", len(df_in), input_path.name)

    api_client = client or SintegraCpfClient()
    rows: list[dict[str, Any]] = []

    for index, record in df_in.iterrows():
        cpf_raw = record.get(cpf_col, "")
        nome_raw = str(record.get(nome_col, "") or "").strip()
        birth_raw = record.get(birth_col, "")

        cpf_digits, birth_api, birth_display = _prepare_row(cpf_raw, birth_raw)
        birth_parsed = parse_date_br(str(birth_raw))
        data_nascimento = format_date_br(birth_parsed) if birth_parsed else str(birth_raw or "")

        if not cpf_digits:
            rows.append(_base_error_row(str(cpf_raw), nome_raw, data_nascimento, "CPF inválido."))
            continue

        if not birth_api:
            rows.append(
                _base_error_row(
                    cpf_digits,
                    nome_raw,
                    data_nascimento,
                    "Data de nascimento inválida. Use dd/mm/aaaa.",
                )
            )
            continue

        if dry_run:
            rows.append(
                {
                    "CPF": cpf_digits,
                    "Nome": nome_raw,
                    "Data de Nascimento": data_nascimento,
                    "nome_receita": "",
                    "situacao_cadastral": "",
                    "ano_obito": "",
                    "Titular falecido": 0,
                    "api_code": "DRY_RUN",
                    "api_message": "Validação local OK (sem chamada à API).",
                }
            )
            continue

        try:
            response: CpfApiResponse = api_client.consultar(cpf_digits, birth_api)
            titular_falecido = is_titular_falecido(response.situacao_cadastral)

            row = {
                "CPF": cpf_digits,
                "Nome": nome_raw,
                "Data de Nascimento": data_nascimento,
                "nome_receita": response.nome,
                "situacao_cadastral": response.situacao_cadastral,
                "ano_obito": response.ano_obito,
                "Titular falecido": titular_falecido,
                "api_code": response.code,
                "api_message": response.message,
            }
            rows.append(row)

            if titular_falecido == 1:
                logger.info("FALECIDO | %s | CPF %s***", nome_raw, cpf_digits[:3])
            elif response.success:
                logger.info("OK | %s | situação=%s", nome_raw, response.situacao_cadastral)
            else:
                logger.warning("AVISO | %s | code=%s | %s", nome_raw, response.code, response.message)

        except CpfApiError as exc:
            rows.append(_base_error_row(cpf_digits, nome_raw, data_nascimento, str(exc)))

    return pd.DataFrame(rows, columns=BD_OUTPUT_COLUMNS)


def export_bd_results(
    df: pd.DataFrame,
    *,
    csv_path: Path,
    xlsx_path: Path,
    falecidos_csv_path: Path | None = None,
) -> dict[str, Path]:
    """Exporta BD processado para CSV (Databricks), Excel e lista só de falecidos."""
    csv_path = Path(csv_path)
    xlsx_path = Path(xlsx_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.info("CSV Databricks salvo: %s (%d linhas)", csv_path, len(df))

    df_falecidos = df[df["Titular falecido"] == 1].copy()
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Base completa", index=False)
        df_falecidos.to_excel(writer, sheet_name="Clientes falecidos", index=False)
    logger.info(
        "Excel salvo: %s (falecidos=%d)",
        xlsx_path,
        len(df_falecidos),
    )

    paths: dict[str, Path] = {"csv": csv_path, "xlsx": xlsx_path}

    if falecidos_csv_path:
        falecidos_csv_path = Path(falecidos_csv_path)
        df_falecidos.to_csv(falecidos_csv_path, index=False, encoding="utf-8-sig")
        logger.info("CSV falecidos salvo: %s (%d linhas)", falecidos_csv_path, len(df_falecidos))
        paths["falecidos_csv"] = falecidos_csv_path

    return paths
