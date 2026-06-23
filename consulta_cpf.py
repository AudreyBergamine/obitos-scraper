"""CLI para consulta em lote de CPF via API Sintegra WS."""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Carrega variáveis de um arquivo .env local, se existir."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

import argparse
import logging

from config import OUTPUT_CPF_CSV
from cpf_batch import process_cpf_csv, save_cpf_results
from utils import setup_logging


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Consulta CPF em lote via API Receita Federal (Sintegra WS). "
            "Documentação: https://www.sintegraws.com.br/api/cpf/documentacao"
        ),
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="CSV de entrada com colunas cpf e data_nascimento",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUTPUT_CPF_CSV,
        help=f"CSV de saída (padrão: {OUTPUT_CPF_CSV})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida o CSV de entrada sem chamar a API (economiza créditos)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Ativa logs DEBUG",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)

    df = process_cpf_csv(args.input, dry_run=args.dry_run)
    save_cpf_results(df, args.output)

    sucesso = len(df[df["api_code"] == "0"]) if not args.dry_run else len(df)
    falecidos = len(df[df["falecido"] == True])  # noqa: E712

    print(f"\nConcluído: {len(df)} linha(s) -> {args.output}")
    if args.dry_run:
        print("Modo dry-run: nenhuma chamada à API foi feita.")
    else:
        print(f"Consultas OK (code=0): {sucesso} | Possível falecimento: {falecidos}")


if __name__ == "__main__":
    main()
