"""ProposalEngine: detection, approval gate and plan-block derivation.

The one rule this module exists to enforce: **the system proposes, the owner
decides**. Concretely, and with no configuration flag able to waive it:

* ``mark_implemented()`` requires status ``approved``; there is no bypass;
* high-impact targets require a passing ``EvalResult`` before approval;
* nothing here opens, reads or writes ``plano/blocos.json`` -- ``to_block_spec()``
  *returns* the block dict for the operator to insert by hand.

The engine also never *runs* an eval: no subprocess, no model call, no network.
It receives an ``EvalResult`` already computed, which is what keeps evaluation
out of any hook hot path.

No I/O at import time and none in ``__init__``. Stdlib only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from .audit import (
    EVENT_APPROVED,
    EVENT_CREATED,
    EVENT_EVAL_FAILED,
    EVENT_IMPLEMENTED,
    EVENT_REJECTED,
    AuditTrail,
)
from .schema import (
    DEFAULT_THRESHOLD,
    ApprovalPolicy,
    EvalGateError,
    EvalResult,
    Evidence,
    InvalidTransitionError,
    Proposal,
    ProposalExistsError,
    ProposalNotFoundError,
    ProposalStatus,
    TargetType,
    check_transition,
    coerce_evidence,
    generate_proposal_id,
    utc_now,
    validate_id,
    validate_proposal,
)
from .storage import ProposalStorage

#: Default routing for a derived improvement block.
DERIVED_BLOCK_COMPLEXITY = "C2"
DERIVED_BLOCK_MODEL = "claude-sonnet-4-6"
DERIVED_BLOCK_AGENT = "executor"
DERIVED_BLOCK_REVIEWER = "claude-sonnet-4-6"


class ProposalEngine:
    """Create, gate and audit improvement proposals."""

    def __init__(
        self,
        root: Optional[Path] = None,
        policy: Optional[ApprovalPolicy] = None,
    ) -> None:
        self._storage = ProposalStorage(root)
        self._audit = AuditTrail(storage=self._storage)
        self._policy = policy if policy is not None else ApprovalPolicy()

    # -- accessors --------------------------------------------------------

    @property
    def storage(self) -> ProposalStorage:
        return self._storage

    @property
    def audit(self) -> AuditTrail:
        return self._audit

    @property
    def policy(self) -> ApprovalPolicy:
        return self._policy

    # -- creation ---------------------------------------------------------

    def create(
        self,
        *,
        problem: str,
        improvement: str,
        estimated_impact: str,
        evidence: Iterable[Union[Evidence, Dict[str, Any]]],
        block_id_origem: Optional[str] = None,
        target_type: Union[TargetType, str] = TargetType.PLAN,
        target_path: str = "",
        confidence: Optional[float] = None,
        rationale: str = "",
        proposal_id: Optional[str] = None,
    ) -> Proposal:
        """Validate and persist a new proposal with status ``pending``.

        Raises ValueError on schema violation (missing field, empty evidence,
        malformed id) and ProposalExistsError if the id is already taken --
        create() never overwrites.
        """
        pid = validate_id(proposal_id, "id") if proposal_id else generate_proposal_id()

        payload = {
            "id": pid,
            "problem": problem,
            "improvement": improvement,
            "estimated_impact": estimated_impact,
            "evidence": list(evidence) if evidence is not None else None,
            "status": ProposalStatus.PENDING.value,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "block_id_origem": block_id_origem,
            "target_type": target_type,
            "target_path": target_path,
            "confidence": confidence,
            "rationale": rationale,
        }
        proposal = Proposal.from_dict(payload)
        validate_proposal(proposal)

        if self._storage.exists(self._storage.proposal_path(pid)):
            raise ProposalExistsError(f"proposal already exists: {pid}")

        self._persist(proposal)
        self._audit.append(
            EVENT_CREATED,
            pid,
            status=proposal.status.value,
            detail=proposal.problem,
            extra={"block_ids": proposal.block_ids},
        )
        return proposal

    def _persist(self, proposal: Proposal) -> None:
        """Write the canonical JSON, then the derived Markdown sidecar."""
        self._storage.write_json(
            self._storage.proposal_path(proposal.id), proposal.to_dict()
        )
        self._storage.write_text(
            self._storage.sidecar_path(proposal.id), render_sidecar(proposal)
        )

    # -- reading ----------------------------------------------------------

    def get(self, proposal_id: str) -> Proposal:
        """Load a proposal from disk. ProposalNotFoundError when absent."""
        pid = validate_id(proposal_id, "proposal_id")
        data = self._storage.read_json(self._storage.proposal_path(pid))
        if data is None:
            raise ProposalNotFoundError(f"proposal not found: {pid}")
        return Proposal.from_dict(data)

    def list_all(self, status: Optional[ProposalStatus] = None) -> List[Proposal]:
        """Every readable proposal, oldest first. Corrupt files are skipped."""
        found: List[Proposal] = []
        for pid in self._storage.list_proposal_ids():
            data = self._storage.read_json(self._storage.proposal_path(pid))
            if data is None:
                continue
            try:
                proposal = Proposal.from_dict(data)
            except ValueError:
                # A single unreadable record must not break the listing.
                continue
            if status is None or proposal.status == status:
                found.append(proposal)
        found.sort(key=lambda item: (item.created_at, item.id))
        return found

    def list_pending(self) -> List[Proposal]:
        """Proposals awaiting the owner's decision, oldest first."""
        return self.list_all(status=ProposalStatus.PENDING)

    # -- transitions ------------------------------------------------------

    def approve(
        self,
        proposal_id: str,
        approved_by: str,
        eval_result: Optional[Union[EvalResult, Dict[str, Any]]] = None,
    ) -> Proposal:
        """``pending -> approved``, subject to the eval gate.

        Fail-closed: a high-impact target with no eval is refused, and an eval
        that did not pass moves the proposal to ``rejected`` before raising.
        """
        if not isinstance(approved_by, str) or not approved_by.strip():
            raise ValueError("approved_by is required: an audit trail needs an author")

        proposal = self.get(proposal_id)
        # Raises before any write, so a repeated approve() cannot produce a
        # second 'approved' entry in the trail.
        check_transition(proposal.status, ProposalStatus.APPROVED)

        result = EvalResult.from_dict(eval_result) if eval_result is not None else None

        if result is None:
            if self._policy.needs_eval(proposal.target_type):
                raise EvalGateError(
                    f"target_type '{proposal.target_type.value}' is high impact and "
                    "requires an eval_result before approval"
                )
        elif not result.passed:
            # "Se falhar: proposal rejected" -- the rejection is durable on
            # disk before the caller sees the exception.
            proposal.eval_result = result
            proposal.status = ProposalStatus.REJECTED
            proposal.rejected_by = approved_by.strip()
            proposal.rejected_at = utc_now()
            proposal.reject_reason = (
                "eval gate failed: "
                f"score_before={result.score_before}, score_after={result.score_after}"
                + (f" ({result.notes})" if result.notes else "")
            )
            proposal.updated_at = proposal.rejected_at
            self._persist(proposal)
            self._audit.append(
                EVENT_EVAL_FAILED,
                proposal.id,
                actor=approved_by.strip(),
                status=proposal.status.value,
                detail=proposal.reject_reason,
                extra={"eval_result": result.to_dict()},
            )
            self._audit.append(
                EVENT_REJECTED,
                proposal.id,
                actor=approved_by.strip(),
                status=proposal.status.value,
                detail=proposal.reject_reason,
            )
            raise EvalGateError(proposal.reject_reason)

        proposal.eval_result = result
        proposal.status = ProposalStatus.APPROVED
        proposal.approved_by = approved_by.strip()
        proposal.approved_at = utc_now()
        proposal.updated_at = proposal.approved_at
        self._persist(proposal)
        self._audit.append(
            EVENT_APPROVED,
            proposal.id,
            actor=proposal.approved_by,
            status=proposal.status.value,
            extra={"eval_result": result.to_dict() if result else None},
        )
        return proposal

    def reject(
        self, proposal_id: str, rejected_by: str, reason: str = ""
    ) -> Proposal:
        """``pending -> rejected``. Terminal: there is no reopening."""
        if not isinstance(rejected_by, str) or not rejected_by.strip():
            raise ValueError("rejected_by is required: an audit trail needs an author")

        proposal = self.get(proposal_id)
        check_transition(proposal.status, ProposalStatus.REJECTED)

        proposal.status = ProposalStatus.REJECTED
        proposal.rejected_by = rejected_by.strip()
        proposal.rejected_at = utc_now()
        proposal.reject_reason = str(reason or "")
        proposal.updated_at = proposal.rejected_at
        self._persist(proposal)
        self._audit.append(
            EVENT_REJECTED,
            proposal.id,
            actor=proposal.rejected_by,
            status=proposal.status.value,
            detail=proposal.reject_reason,
        )
        return proposal

    def mark_implemented(self, proposal_id: str, ref: str = "") -> Proposal:
        """``approved -> implemented``.

        This is the gate of acceptance criterion 3: a proposal that was never
        explicitly approved cannot be marked as implemented, ever.
        """
        proposal = self.get(proposal_id)
        check_transition(proposal.status, ProposalStatus.IMPLEMENTED)

        proposal.status = ProposalStatus.IMPLEMENTED
        proposal.implemented_at = utc_now()
        proposal.implemented_ref = str(ref or "")
        proposal.updated_at = proposal.implemented_at
        self._persist(proposal)
        self._audit.append(
            EVENT_IMPLEMENTED,
            proposal.id,
            actor=proposal.approved_by or "",
            status=proposal.status.value,
            detail=proposal.implemented_ref,
        )
        return proposal

    # -- detection --------------------------------------------------------

    def detect_patterns(
        self,
        block_history: Iterable[Dict[str, Any]],
        *,
        threshold: int = DEFAULT_THRESHOLD,
        persist: bool = False,
    ) -> List[Proposal]:
        """Find error types recurring across `threshold`+ *distinct* blocks.

        Counting distinct block ids is deliberate: three occurrences inside one
        block is one troubled block, not a systemic pattern.

        Detection does not touch disk unless ``persist=True``. Observing is not
        the same act as putting something in the owner's approval queue.

        Callers: this is the API the automatic end-of-session trigger will use.
        Wiring it to that trigger belongs to a later block.
        """
        if threshold < 1:
            raise ValueError("threshold must be >= 1")

        groups: Dict[str, Dict[str, Evidence]] = {}
        for entry in block_history or []:
            if not isinstance(entry, dict):
                continue
            block_id = str(entry.get("block_id", "") or "").strip()
            error_type = str(entry.get("error_type", "") or "").strip()
            if not block_id or not error_type:
                continue
            bucket = groups.setdefault(error_type, {})
            if block_id not in bucket:
                bucket[block_id] = Evidence(
                    block_id=block_id,
                    error_type=error_type,
                    detail=str(entry.get("detail", "") or ""),
                    occurred_at=str(entry.get("timestamp", "") or ""),
                )

        proposals: List[Proposal] = []
        for error_type in sorted(groups):
            bucket = groups[error_type]
            if len(bucket) < threshold:
                continue
            evidence = [bucket[bid] for bid in sorted(bucket)]
            count = len(evidence)
            fields = dict(
                problem=(
                    f"Falha recorrente do tipo '{error_type}' em {count} blocos "
                    f"distintos: {', '.join(bid for bid in sorted(bucket))}."
                ),
                improvement=(
                    f"Investigar a causa comum de '{error_type}' e tratar na raiz "
                    "(spec, contrato ou ferramenta), em vez de corrigir bloco a bloco."
                ),
                estimated_impact=(
                    f"{count} blocos ja afetados; cada novo bloco sujeito ao mesmo "
                    f"modo de falha ate a causa de '{error_type}' ser tratada."
                ),
                evidence=evidence,
                target_type=TargetType.PLAN,
                # Declared heuristic, not magic: saturates at 2x the threshold.
                confidence=min(1.0, count / float(threshold * 2)),
                rationale=(
                    f"Detectado por ProposalEngine.detect_patterns com threshold="
                    f"{threshold} blocos distintos."
                ),
            )

            if persist:
                proposals.append(self.create(**fields))
            else:
                draft = Proposal.from_dict(
                    {
                        **fields,
                        "id": generate_proposal_id(),
                        "target_type": TargetType.PLAN.value,
                        "evidence": [item.to_dict() for item in evidence],
                        "status": ProposalStatus.PENDING.value,
                        "created_at": utc_now(),
                    }
                )
                proposals.append(validate_proposal(draft))
        return proposals

    # -- plan derivation --------------------------------------------------

    def to_block_spec(self, proposal: Union[Proposal, str]) -> Dict[str, Any]:
        """Derive the plan-block dict for an approved proposal.

        Returns the dict. Does **not** write it anywhere: inserting it into the
        plan is the operator's explicit act (acceptance criteria 4 and 6).
        """
        if isinstance(proposal, str):
            proposal = self.get(proposal)
        if not isinstance(proposal, Proposal):
            raise ValueError("to_block_spec expects a Proposal or a proposal id")
        if proposal.status not in (
            ProposalStatus.APPROVED,
            ProposalStatus.IMPLEMENTED,
        ):
            raise ValueError(
                "to_block_spec requires an approved proposal; "
                f"'{proposal.id}' is {proposal.status.value}"
            )

        suffix = proposal.id.rsplit("-", 1)[-1] or "0000"
        block_id = f"MEL-{suffix}"
        slug = proposal.slug()

        return {
            "id": block_id,
            "titulo": _title_from(proposal),
            "spec": f"plano/specs/{block_id}-{slug}.md",
            "complexidade": DERIVED_BLOCK_COMPLEXITY,
            "modelo": DERIVED_BLOCK_MODEL,
            "agente": DERIVED_BLOCK_AGENT,
            "revisor_modelo": DERIVED_BLOCK_REVIEWER,
            "depende_de": [],
            # Deliberately empty. A heuristic proposal has no basis to decide
            # what a block may touch, and a guessed list would grant false
            # authorization. The operator fills this in before inserting.
            "arquivos_permitidos": [],
            "criterio_aceite": [
                f"O SISTEMA DEVE eliminar a causa do problema: {proposal.problem}",
                f"O SISTEMA DEVE aplicar a melhoria proposta: {proposal.improvement}",
                "O SISTEMA DEVE demonstrar, nos blocos citados como evidencia ("
                + ", ".join(proposal.block_ids)
                + "), que o modo de falha nao se repete.",
            ],
            "estado": "pendente",
            "origem_proposal": proposal.id,
        }


# --------------------------------------------------------------------------
# Sidecar rendering (derived output -- never read back)
# --------------------------------------------------------------------------


def _title_from(proposal: Proposal, max_len: int = 90) -> str:
    text = " ".join((proposal.improvement or proposal.problem).split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "\u2026"


def render_sidecar(proposal: Proposal) -> str:
    """Human-readable Markdown view of a proposal.

    Derived output: if the sidecar and the JSON ever disagree, the JSON wins.
    Nothing in this package reads a sidecar back.
    """
    lines: List[str] = []
    lines.append(f"# Proposal {proposal.id}")
    lines.append("")
    lines.append(f"- **Status**: `{proposal.status.value}`")
    lines.append(f"- **Criada em**: {proposal.created_at}")
    lines.append(f"- **Alvo**: `{proposal.target_type.value}`")
    if proposal.target_path:
        lines.append(f"- **Caminho alvo**: `{proposal.target_path}`")
    if proposal.block_id_origem:
        lines.append(f"- **Bloco de origem**: `{proposal.block_id_origem}`")
    if proposal.confidence is not None:
        lines.append(f"- **Confianca**: {proposal.confidence:.2f}")
    lines.append("")
    lines.append("## Problema detectado")
    lines.append("")
    lines.append(proposal.problem)
    lines.append("")
    lines.append("## Evidencias")
    lines.append("")
    for item in proposal.evidence:
        parts = [f"`{item.block_id}`"]
        if item.error_type:
            parts.append(f"tipo `{item.error_type}`")
        if item.occurred_at:
            parts.append(item.occurred_at)
        line = " - ".join(parts)
        if item.detail:
            line += f" - {item.detail}"
        lines.append(f"- {line}")
    lines.append("")
    lines.append("## Melhoria proposta")
    lines.append("")
    lines.append(proposal.improvement)
    lines.append("")
    lines.append("## Impacto estimado")
    lines.append("")
    lines.append(proposal.estimated_impact)
    if proposal.rationale:
        lines.append("")
        lines.append("## Racional")
        lines.append("")
        lines.append(proposal.rationale)
    if proposal.eval_result is not None:
        result = proposal.eval_result
        lines.append("")
        lines.append("## Eval")
        lines.append("")
        lines.append(f"- score_before: {result.score_before}")
        lines.append(f"- score_after: {result.score_after}")
        lines.append(f"- passed: {result.passed}")
        if result.notes:
            lines.append(f"- notes: {result.notes}")
    lines.append("")
    lines.append("## Decisao")
    lines.append("")
    if proposal.status == ProposalStatus.APPROVED:
        lines.append(f"Aprovada por **{proposal.approved_by}** em {proposal.approved_at}.")
    elif proposal.status == ProposalStatus.REJECTED:
        lines.append(f"Rejeitada por **{proposal.rejected_by}** em {proposal.rejected_at}.")
        if proposal.reject_reason:
            lines.append("")
            lines.append(f"Motivo: {proposal.reject_reason}")
    elif proposal.status == ProposalStatus.IMPLEMENTED:
        lines.append(
            f"Aprovada por **{proposal.approved_by}** em {proposal.approved_at} "
            f"e implementada em {proposal.implemented_at}."
        )
        if proposal.implemented_ref:
            lines.append("")
            lines.append(f"Referencia: `{proposal.implemented_ref}`")
    else:
        lines.append(
            "Pendente de aprovacao explicita do dono. Nenhuma alteracao e aplicada "
            "ao plano sem essa aprovacao."
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "Documento derivado do JSON canonico; em caso de divergencia, o JSON "
        "prevalece. Ao converter esta proposta em bloco do plano, preencha "
        "`arquivos_permitidos` manualmente: o campo sai vazio de proposito."
    )
    lines.append("")
    return "\n".join(lines)
