"""Pipeline principal: coleta, parse, normalização e exportação CSV."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from config import CSV_COLUMNS, DEDUP_KEYS, OBITUARY_SOURCES, OUTPUT_CSV, OUTPUT_DIR
from matcher import rank_matches
from parser import get_parser
from scraper import fetch_multiple
from utils import deduplicate_records, format_date, setup_logging

logger = logging.getLogger(__name__)


def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Converte registros internos para DataFrame pronto para CSV."""
    rows: list[dict[str, Any]] = []
    for record in records:
        rows.append(
            {
                "nome": record.get("nome") or "",
                "cidade": record.get("cidade") or "",
                "uf": record.get("uf") or "",
                "data_obito": format_date(record.get("data_obito")),
                "idade": record.get("idade") if record.get("idade") is not None else "",
                "data_nascimento": format_date(record.get("data_nascimento")),
                "texto_completo": record.get("texto_completo") or "",
                "fonte": record.get("fonte") or "",
            }
        )

    df = pd.DataFrame(rows, columns=CSV_COLUMNS)
    return df.replace({pd.NA: "", None: ""})


def run_pipeline(sources: list[dict[str, str]] | None = None) -> pd.DataFrame:
    """Executa coleta, parsing, deduplicação e retorna DataFrame."""
    sources = sources or OBITUARY_SOURCES
    logger.info("Iniciando pipeline com %d fonte(s)", len(sources))

    fetched = fetch_multiple(sources)
    all_records: list[dict[str, Any]] = []

    for item in fetched:
        parser = get_parser(item["parser"])
        records = parser(item["html"], item["url"])
        logger.info("[%s] %d registro(s) extraído(s)", item["source_name"], len(records))
        all_records.extend(records)

    deduped = deduplicate_records(all_records, DEDUP_KEYS)
    return records_to_dataframe(deduped)


def save_csv(df: pd.DataFrame, output_path: Path = OUTPUT_CSV) -> Path:
    """Salva DataFrame em CSV UTF-8."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info("CSV salvo em %s (%d linhas)", output_path, len(df))
    return output_path


def demo_matching(df: pd.DataFrame) -> None:
    """Demonstração de scoring fuzzy com clientes fictícios."""
    if df.empty:
        logger.warning("Sem registros para demonstrar matching")
        return

    sample_obit = {
        "nome": df.iloc[0]["nome"],
        "cidade": df.iloc[0]["cidade"],
        "idade": int(df.iloc[0]["idade"]) if str(df.iloc[0]["idade"]).isdigit() else None,
        "data_nascimento": None,
    }

    fake_clients = [
        {"nome": sample_obit["nome"], "cidade": sample_obit["cidade"], "idade": sample_obit["idade"]},
        {"nome": "Maria Oliveira", "cidade": sample_obit["cidade"], "idade": 40},
    ]

    ranked = rank_matches(sample_obit, fake_clients, min_score=0)
    logger.info("Demo matching para '%s':", sample_obit["nome"])
    for match in ranked:
        logger.info(
            "  cliente=%s | score=%.1f (nome=%.1f, cidade=%.1f, idade/nasc=%.1f)",
            match["cliente"],
            match["score_total"],
            match["score_nome"],
            match["score_cidade"],
            match["score_idade_nasc"],
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pipeline de coleta e estruturação de obituários públicos brasileiros.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUTPUT_CSV,
        help=f"Caminho do CSV de saída (padrão: {OUTPUT_CSV})",
    )
    parser.add_argument(
        "--demo-match",
        action="store_true",
        help="Executa demonstração de scoring fuzzy após exportação",
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

    df = run_pipeline()
    save_csv(df, args.output)

    if args.demo_match:
        demo_matching(df)

    print(f"\nConcluído: {len(df)} registro(s) -> {args.output}")


if __name__ == "__main__":
    main()
