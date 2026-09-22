"""Classificacao de falhas e decisao de retry/escalation.

Modulo puro: nao faz chamada de IA, nao faz IO de rede, nao importa
maestro_run nem maestro_state. Apenas classifica um tipo de falha conhecido
e retorna a decisao (mesmo modelo, modelo superior, aguardar cooldown ou
parar). A execucao real da decisao e feita pelo caller.
"""

from __future__ import annotations

from dataclasses import dataclass

LEVELS = ("C1", "C2", "C3", "C4", "C5")

# Fallback usado quando config["modelos"] nao e fornecido. Os rotulos
# (haiku/sonnet/opus) sao apenas identificadores de tier internos a este
# modulo; o caller que possuir um config real deve passa-lo para obter os
# nomes de modelo completos.
_MODEL_FALLBACK = {
    "C1": "haiku",
    "C2": "haiku",
    "C3": "sonnet",
    "C4": "sonnet",
    "C5": "opus",
}

_TIPOS_FALHA = (
    "teste_falhou",
    "review_reprovado",
    "timeout",
    "provider_error",
    "bloco_invalido",
)


class RetryError(Exception):
    """Erro ao classificar uma falha (tipo_falha desconhecido)."""


@dataclass
class RetryDecision:
    should_retry: bool
    action: str  # "same_model" | "escalate_model" | "wait_cooldown" | "stop"
    model: str | None
    reason: str
    tipo_falha: str
    bloqueado_por: "str | None" = None  # preenchido quando action=="stop"; gravar em block["bloqueado_por"]


class RetryClassifier:
    """Classifica falhas de execucao de bloco e decide a acao de retry."""

    def classify(
        self,
        tipo_falha: str,
        block: dict,
        tentativas: int,
        max_tentativas: int = 2,
        available_providers: list[str] | None = None,
        config: dict | None = None,
    ) -> RetryDecision:
        if tipo_falha not in _TIPOS_FALHA:
            raise RetryError(f"tipo_falha desconhecido: {tipo_falha!r}")

        available_providers = list(available_providers) if available_providers else []

        # 1. max_tentativas atingido -> stop, independente do tipo_falha (I2).
        if tentativas >= max_tentativas:
            return RetryDecision(
                should_retry=False,
                action="stop",
                model=None,
                reason="max_tentativas atingido",
                tipo_falha=tipo_falha,
                bloqueado_por=tipo_falha,
            )

        # 6/7. bloco_invalido -> stop sempre (I3), nao adianta retry.
        if tipo_falha == "bloco_invalido":
            return RetryDecision(
                should_retry=False,
                action="stop",
                model=None,
                reason="bloco invalido, retry nao e aplicavel",
                tipo_falha=tipo_falha,
                bloqueado_por=tipo_falha,
            )

        # 2. teste_falhou -> mesma tentativa com o mesmo modelo.
        if tipo_falha == "teste_falhou":
            return RetryDecision(
                should_retry=True,
                action="same_model",
                model=self._current_model(block, config),
                reason="teste falhou, nova tentativa com o mesmo modelo",
                tipo_falha=tipo_falha,
            )

        # 3. review_reprovado -> escala para modelo superior, ou stop se nao ha.
        if tipo_falha == "review_reprovado":
            model = self.escalate_model(block, config)
            if model is None:
                return RetryDecision(
                    should_retry=False,
                    action="stop",
                    model=None,
                    reason="review reprovado e nao ha modelo de complexidade superior",
                    tipo_falha=tipo_falha,
                    bloqueado_por=tipo_falha,
                )
            return RetryDecision(
                should_retry=True,
                action="escalate_model",
                model=model,
                reason="review reprovado, escalando para modelo superior",
                tipo_falha=tipo_falha,
            )

        # 4. timeout -> nova tentativa, nao escala automaticamente.
        if tipo_falha == "timeout":
            return RetryDecision(
                should_retry=True,
                action="same_model",
                model=self._current_model(block, config),
                reason="timeout, nova tentativa com o mesmo modelo",
                tipo_falha=tipo_falha,
            )

        # 5. provider_error -> aguarda cooldown se ha provider alternativo,
        #    senao para.
        if tipo_falha == "provider_error":
            if available_providers:
                return RetryDecision(
                    should_retry=True,
                    action="wait_cooldown",
                    model=self._current_model(block, config),
                    reason="erro de provider, aguardando cooldown antes de tentar de novo",
                    tipo_falha=tipo_falha,
                )
            return RetryDecision(
                should_retry=False,
                action="stop",
                model=None,
                reason="erro de provider e nenhum provider alternativo disponivel",
                tipo_falha=tipo_falha,
                bloqueado_por=tipo_falha,
            )

        # Inalcancavel: todos os tipos validos foram tratados acima.
        raise RetryError(f"tipo_falha desconhecido: {tipo_falha!r}")  # pragma: no cover

    def escalate_model(self, block: dict, config: dict | None = None) -> str | None:
        """Modelo de complexidade superior, ou None se ja no maximo (C5).

        Avanca pelos niveis C1..C5 ate encontrar um modelo diferente do
        modelo atual do bloco (niveis adjacentes podem compartilhar o mesmo
        modelo, ex: C3 e C4 ambos em 'sonnet'; escalar so tem sentido quando
        o modelo de fato muda).
        """
        complexidade = self._complexidade(block)
        if complexidade is None:
            return None

        models = self._models_table(config)
        current_model = models.get(complexidade)
        idx = LEVELS.index(complexidade)

        for level in LEVELS[idx + 1 :]:
            candidate = models.get(level)
            if candidate is not None and candidate != current_model:
                return candidate
        return None

    @staticmethod
    def _models_table(config: dict | None) -> dict:
        if isinstance(config, dict):
            models = config.get("modelos")
            if isinstance(models, dict):
                return models
        return _MODEL_FALLBACK

    def _current_model(self, block: dict, config: dict | None) -> str | None:
        complexidade = self._complexidade(block)
        if complexidade is None:
            return None
        return self._models_table(config).get(complexidade)

    @staticmethod
    def _complexidade(block) -> str | None:
        if isinstance(block, dict):
            val = block.get("complexidade")
        else:
            val = getattr(block, "complexidade", None)
        if not isinstance(val, str):
            return None
        val = val.strip().upper()
        return val if val in LEVELS else None
