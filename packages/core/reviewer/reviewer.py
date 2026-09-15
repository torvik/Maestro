"""Preparo de contexto e interpretacao de veredito do agente revisor.

Nao decide nada sozinho — apenas monta o prompt de revisao e interpreta a
resposta do revisor (LLM) de forma deterministica. O veredito em si (APROVADO
ou REPROVADO) e sempre extraido do texto da resposta, nunca inferido.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_VERDICT_RE = re.compile(r"\b(APROVADO|REPROVADO)\b", re.IGNORECASE)
_FINDING_RE = re.compile(r"^\s*\d+[.)]\s*(.+)$")


class ReviewerError(Exception):
    """Erro ao interpretar a resposta do revisor ou ao validar a promocao."""


@dataclass
class ReviewVerdict:
    verdict: str
    findings: list[str]
    raw: str


class Reviewer:
    def prepare_context(
        self,
        block,
        spec_content,
        diff: str = "",
        test_output: str = "",
        evidence_summary: str = "",
    ) -> str:
        block_id = self._block_id(block)
        parts = [
            f"Revise o bloco {block_id} contra a spec abaixo. Não corrija nada — aponte.",
            "",
            "=== SPEC ===",
            spec_content,
        ]
        if diff:
            parts += ["", "=== DIFF (arquivos alterados) ===", diff]
        if test_output:
            parts += ["", "=== OUTPUT DOS TESTES ===", test_output]
        if evidence_summary:
            parts += ["", "=== EVIDÊNCIA ===", evidence_summary]
        parts += [
            "",
            'Veredito: APROVADO ou REPROVADO. Nunca "aprovado com ressalvas".',
        ]
        return "\n".join(parts)

    def parse_verdict(self, response: str) -> ReviewVerdict:
        matches = {m.group(1).upper() for m in _VERDICT_RE.finditer(response)}
        if "REPROVADO" in matches:
            verdict = "REPROVADO"
        elif "APROVADO" in matches:
            verdict = "APROVADO"
        else:
            raise ReviewerError("veredito não encontrado na resposta")

        findings = []
        for line in response.splitlines():
            m = _FINDING_RE.match(line)
            if m:
                findings.append(m.group(1).strip())

        return ReviewVerdict(verdict=verdict, findings=findings, raw=response)

    def validate_promotion(self, block: dict, verdict: ReviewVerdict) -> None:
        complexidade = self._complexidade(block)
        if complexidade in ("C4", "C5") and verdict.verdict != "APROVADO":
            raise ReviewerError(
                f"bloco {complexidade} requer veredito APROVADO para promoção "
                f"(obtido: {verdict.verdict})"
            )

    def extract_findings_note(self, verdict: ReviewVerdict) -> str | None:
        if not verdict.findings:
            return None
        lines = [f"{i + 1}. {finding}" for i, finding in enumerate(verdict.findings)]
        return "Findings da revisão:\n" + "\n".join(lines)

    def get_reviewer_model(self, block: dict) -> str:
        """Retorna revisor_modelo do bloco. NUNCA retorna o modelo de execucao.

        Fallback: 'claude-sonnet-4-6' se revisor_modelo ausente.
        """
        if isinstance(block, dict):
            model = block.get("revisor_modelo") or block.get("revisor_model")
        else:
            model = getattr(block, "revisor_modelo", None) or getattr(block, "revisor_model", None)
        return model if model else "claude-sonnet-4-6"

    @staticmethod
    def _block_id(block):
        if isinstance(block, dict):
            return block.get("id", block.get("bloco", "?"))
        return getattr(block, "id", str(block))

    @staticmethod
    def _complexidade(block):
        """Retorna complexidade normalizada para maiúscula, ou None se ausente."""
        if isinstance(block, dict):
            val = block.get("complexidade")
        else:
            val = getattr(block, "complexidade", None)
        return val.upper() if val else None
