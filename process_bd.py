"""CLI para processar input/BD.csv e gerar CSV + Excel para Databricks/Power BI."""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

import argparse
import logging

from bd_processor import export_bd_results, process_bd_csv
from config import BD_FALECIDOS_CSV, BD_INPUT_CSV, BD_OUTPUT_CSV, BD_OUTPUT_XLSX
from utils import setup_logging


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Processa input/BD.csv (CPF, Nome, Data de Nascimento), "
            "consulta a Receita Federal via Sintegra e gera CSV + Excel "
            "com a coluna 'Titular falecido' para Databricks e Power BI."
        ),
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=BD_INPUT_CSV,
        help=f"CSV de entrada (padrão: {BD_INPUT_CSV})",
    )
    parser.add_argument(
        "--csv-out",
        type=Path,
        default=BD_OUTPUT_CSV,
        help=f"CSV de saída para Databricks (padrão: {BD_OUTPUT_CSV})",
    )
    parser.add_argument(
        "--xlsx-out",
        type=Path,
        default=BD_OUTPUT_XLSX,
        help=f"Excel de saída (padrão: {BD_OUTPUT_XLSX})",
    )
    parser.add_argument(
        "--falecidos-out",
        type=Path,
        default=BD_FALECIDOS_CSV,
        help=f"CSV só com falecidos (padrão: {BD_FALECIDOS_CSV})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida BD.csv sem consumir créditos da API",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Logs DEBUG",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)

    df = process_bd_csv(args.input, dry_run=args.dry_run)
    paths = export_bd_results(
        df,
        csv_path=args.csv_out,
        xlsx_path=args.xlsx_out,
        falecidos_csv_path=args.falecidos_out,
    )

    total = len(df)
    falecidos = int((df["Titular falecido"] == 1).sum())

    print(f"\nProcessamento concluído: {total} registro(s)")
    print(f"Titulares falecidos: {falecidos}")
    print(f"CSV Databricks : {paths['csv']}")
    print(f"Excel          : {paths['xlsx']}")
    print(f"CSV falecidos  : {paths.get('falecidos_csv', '—')}")
    if args.dry_run:
        print("\nModo dry-run: nenhuma consulta à API foi realizada.")


if __name__ == "__main__":
    main()
