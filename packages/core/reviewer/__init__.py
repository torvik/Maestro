"""Reviewer do Maestro: prepara o contexto de revisao e interpreta o veredito.

Nao roda o LLM revisor nem decide aprovacao — apenas monta o prompt
(``prepare_context``) e interpreta a resposta (``parse_verdict``) de forma
deterministica. ``validate_promotion`` aplica a regra de bloqueio C4/C5.

    from packages.core.reviewer import Reviewer
    reviewer = Reviewer()
    contexto = reviewer.prepare_context(block, spec_content)
    veredito = reviewer.parse_verdict(resposta_do_revisor)
    reviewer.validate_promotion(block, veredito)
"""

from .reviewer import Reviewer, ReviewerError, ReviewVerdict

__all__ = ["Reviewer", "ReviewVerdict", "ReviewerError"]
