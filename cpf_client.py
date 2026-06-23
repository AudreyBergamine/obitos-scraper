"""Cliente da API Receita Federal CPF via Sintegra WS."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests
from requests.exceptions import RequestException

from config import (
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_BACKOFF,
    SINTEGRA_API_URL,
    SINTEGRA_PLUGIN,
    SINTEGRA_REQUEST_DELAY,
    SINTEGRA_TOKEN,
)
from normalizer import normalize_cpf

logger = logging.getLogger(__name__)

# Códigos que indicam instabilidade e permitem retry (doc Sintegra)
RETRYABLE_CODES = {"7"}


class CpfApiError(Exception):
    """Erro na consulta à API de CPF."""


@dataclass
class CpfApiResponse:
    """Resposta normalizada da API Sintegra CPF."""

    raw: dict[str, Any] = field(default_factory=dict)
    code: str = ""
    status: str = ""
    message: str = ""
    cpf: str = ""
    nome: str = ""
    nome_mae: str = ""
    data_nascimento: str = ""
    situacao_cadastral: str = ""
    ano_obito: str = ""
    idade: str = ""
    uf: str = ""
    sexo: str = ""
    data_inscricao: str = ""
    qsa_quantidade: int = 0
    falecido: bool = False
    success: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CpfApiResponse":
        genero = payload.get("genero") or {}
        uf_list = payload.get("uf") or []
        qsa = payload.get("qsa") or []
        situacao = str(payload.get("situacao_cadastral") or "")
        ano_obito = str(payload.get("ano_obito") or "").strip()

        response = cls(
            raw=payload,
            code=str(payload.get("code", "")),
            status=str(payload.get("status", "")),
            message=str(payload.get("message", "")),
            cpf=str(payload.get("cpf") or ""),
            nome=str(payload.get("nome") or ""),
            nome_mae=str(payload.get("nome_mae") or ""),
            data_nascimento=str(payload.get("data_nascimento") or ""),
            situacao_cadastral=situacao,
            ano_obito=ano_obito,
            idade=str(payload.get("idade") or ""),
            uf=", ".join(uf_list) if isinstance(uf_list, list) else str(uf_list),
            sexo=str(genero.get("sexo") or ""),
            data_inscricao=str(payload.get("data_inscricao") or ""),
            qsa_quantidade=len(qsa) if isinstance(qsa, list) else 0,
            falecido=bool(ano_obito) or situacao.lower() == "titular falecido",
            success=str(payload.get("code")) == "0" and str(payload.get("status")) == "OK",
        )
        return response

    def to_flat_dict(
        self,
        cpf_entrada: str = "",
        data_nascimento_entrada: str = "",
    ) -> dict[str, Any]:
        """Converte resposta para linha de CSV."""
        return {
            "cpf_entrada": cpf_entrada,
            "data_nascimento_entrada": data_nascimento_entrada,
            "api_code": self.code,
            "api_status": self.status,
            "api_message": self.message,
            "cpf": self.cpf,
            "nome": self.nome,
            "nome_mae": self.nome_mae,
            "data_nascimento": self.data_nascimento,
            "situacao_cadastral": self.situacao_cadastral,
            "ano_obito": self.ano_obito,
            "idade": self.idade,
            "uf": self.uf,
            "sexo": self.sexo,
            "data_inscricao": self.data_inscricao,
            "qsa_quantidade": self.qsa_quantidade,
            "falecido": self.falecido,
        }


class SintegraCpfClient:
    """
    Cliente HTTP para a API Receita Federal CPF (Sintegra WS).

    Documentação: https://www.sintegraws.com.br/api/cpf/documentacao
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        timeout: int = REQUEST_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        request_delay: float = SINTEGRA_REQUEST_DELAY,
    ) -> None:
        self.token = token or os.getenv("SINTEGRA_TOKEN", "") or SINTEGRA_TOKEN
        self.timeout = timeout
        self.max_retries = max_retries
        self.request_delay = request_delay
        self._last_request_at: float = 0.0

    def _ensure_token(self) -> None:
        if not self.token:
            raise CpfApiError(
                "Token Sintegra não configurado. Defina a variável SINTEGRA_TOKEN "
                "ou crie um arquivo .env (veja .env.example)."
            )

    def _wait_rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_at
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)

    def consultar(self, cpf: str, data_nascimento: str) -> CpfApiResponse:
        """
        Consulta CPF na Receita Federal via Sintegra.

        Args:
            cpf: Apenas dígitos (00000000000).
            data_nascimento: Formato ddmmaaaa exigido pela API.
        """
        self._ensure_token()

        cpf_digits = normalize_cpf(cpf)
        if not cpf_digits:
            raise CpfApiError(f"CPF inválido para consulta: {cpf}")

        if not data_nascimento or len(data_nascimento) != 8 or not data_nascimento.isdigit():
            raise CpfApiError(
                f"Data de nascimento inválida para API (use ddmmaaaa): {data_nascimento}"
            )

        params = {
            "token": self.token,
            "cpf": cpf_digits,
            "data-nascimento": data_nascimento,
            "plugin": SINTEGRA_PLUGIN,
        }

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            self._wait_rate_limit()
            try:
                logger.info(
                    "Consultando CPF %s*** (tentativa %d/%d)",
                    cpf_digits[:3],
                    attempt,
                    self.max_retries,
                )
                response = requests.get(
                    SINTEGRA_API_URL,
                    params=params,
                    timeout=self.timeout,
                )
                self._last_request_at = time.time()

                if response.status_code == 401:
                    raise CpfApiError("Token inválido (HTTP 401). Verifique SINTEGRA_TOKEN.")

                response.raise_for_status()
                payload = response.json()
                result = CpfApiResponse.from_dict(payload)

                if result.code in RETRYABLE_CODES and attempt < self.max_retries:
                    sleep_time = RETRY_BACKOFF ** (attempt - 1)
                    logger.warning(
                        "API instável (code=%s). Retry em %.1fs...",
                        result.code,
                        sleep_time,
                    )
                    time.sleep(sleep_time)
                    continue

                return result

            except (RequestException, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning("Erro na requisição CPF: %s", exc)
                if attempt < self.max_retries:
                    time.sleep(RETRY_BACKOFF ** (attempt - 1))

        raise CpfApiError(f"Falha ao consultar CPF após {self.max_retries} tentativas: {last_error}")
