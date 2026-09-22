"""Fluent construction of a UCP, with no harness knowledge anywhere.

    packet = (UCPBuilder()
              .for_block("BLOCO-EXEMPLO", spec_text="...", test_command="...")
              .with_conventions({"language": "python"})
              .add_context_file("arquivo.py", "def exemplo(): ...")
              .with_budget(max_turns=20)
              .build())

No method takes an executor name as a parameter and no branch in this module
depends on one. Agent identifiers enter only as data (`producer_agent`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from packages.core.protocol.schema import as_dict, as_text
from packages.core.protocol.ucp import (
    UCP,
    BlockSpec,
    Budget,
    ContextFile,
    HandoffRef,
    MemoryEntry,
)

__all__ = ["UCPBuilder"]


class UCPBuilder:
    """Accumulates the parts of a packet and validates once, at `build()`."""

    def __init__(self) -> None:
        self._block_spec: Optional[BlockSpec] = None
        self._conventions: Dict[str, Any] = {}
        self._context_files: List[ContextFile] = []
        self._memory_entries: List[MemoryEntry] = []
        self._budget: Budget = Budget()
        self._handoff: Optional[HandoffRef] = None
        self._ucp_id: str = ""
        self._run_id: str = ""
        self._producer_agent: str = ""
        self._extensions: Dict[str, Any] = {}

    # -- block ------------------------------------------------------------

    def for_block(
        self,
        block_id: str,
        *,
        title: str = "",
        spec_text: str = "",
        spec_path: str = "",
        complexity: str = "",
        acceptance_criteria: Optional[List[str]] = None,
        allowed_paths: Optional[List[str]] = None,
        forbidden_actions: Optional[List[str]] = None,
        stop_and_ask: Optional[List[str]] = None,
        test_command: str = "",
    ) -> "UCPBuilder":
        """Set the block being executed. Required before `build()`."""
        self._block_spec = BlockSpec(
            block_id=block_id,
            title=title,
            spec_text=spec_text,
            spec_path=spec_path,
            complexity=complexity,
            acceptance_criteria=list(acceptance_criteria or []),
            allowed_paths=list(allowed_paths or []),
            forbidden_actions=list(forbidden_actions or []),
            stop_and_ask=list(stop_and_ask or []),
            test_command=test_command,
        )
        return self

    def with_block_spec(self, block_spec: Any) -> "UCPBuilder":
        """Set the block from an existing BlockSpec or plain dict."""
        self._block_spec = BlockSpec.from_dict(block_spec)
        return self

    # -- conventions ------------------------------------------------------

    def with_conventions(self, conventions: Any) -> "UCPBuilder":
        """Replace the conventions. A bare string becomes {'notes': ...}."""
        if isinstance(conventions, str):
            self._conventions = {"notes": conventions} if conventions else {}
        else:
            self._conventions = dict(as_dict(conventions, "conventions"))
        return self

    def add_convention(self, key: str, value: Any) -> "UCPBuilder":
        self._conventions[as_text(key)] = value
        return self

    # -- context ----------------------------------------------------------

    def add_context_file(
        self,
        path: str,
        content: str = "",
        *,
        priority: int = 0,
        tokens: int = 0,
        truncated: bool = False,
    ) -> "UCPBuilder":
        self._context_files.append(
            ContextFile(
                path=path,
                content=content,
                priority=priority,
                tokens=tokens,
                truncated=truncated,
            )
        )
        return self

    def add_context_files(self, files: Any) -> "UCPBuilder":
        for item in files or []:
            self._context_files.append(ContextFile.from_dict(item))
        return self

    # -- memory -----------------------------------------------------------

    def add_memory_entry(
        self,
        text: str,
        *,
        id: str = "",
        kind: str = "",
        source: str = "",
        score: float = 0.0,
    ) -> "UCPBuilder":
        self._memory_entries.append(
            MemoryEntry(text=text, id=id, kind=kind, source=source, score=score)
        )
        return self

    def add_memory_entries(self, entries: Any) -> "UCPBuilder":
        for item in entries or []:
            self._memory_entries.append(MemoryEntry.from_dict(item))
        return self

    # -- budget -----------------------------------------------------------

    def with_budget(self, budget: Any = None, **limits: Any) -> "UCPBuilder":
        """Set limits from a Budget, a dict, or keyword arguments.

        Keyword arguments win over the positional value, so
        `with_budget(existing, max_turns=5)` overrides a single limit.
        """
        base = Budget.from_dict(budget).to_dict() if budget is not None else self._budget.to_dict()
        base.update(limits)
        self._budget = Budget.from_dict(base)
        return self

    # -- handoff ----------------------------------------------------------

    def with_handoff(self, handoff: Any) -> "UCPBuilder":
        """Attach resume context. Passing None clears it -- handoff is optional."""
        self._handoff = HandoffRef.from_dict(handoff)
        return self

    # -- identity ---------------------------------------------------------

    def with_run(
        self,
        run_id: str = "",
        ucp_id: str = "",
        producer_agent: str = "",
    ) -> "UCPBuilder":
        """Correlation ids. `producer_agent` is data, never a branch."""
        if run_id:
            self._run_id = as_text(run_id)
        if ucp_id:
            self._ucp_id = as_text(ucp_id)
        if producer_agent:
            self._producer_agent = as_text(producer_agent)
        return self

    def add_extension(self, key: str, value: Any) -> "UCPBuilder":
        """Carry a field this version of the protocol does not know about."""
        self._extensions[as_text(key)] = value
        return self

    # -- build ------------------------------------------------------------

    def build(self) -> UCP:
        """Produce a validated packet.

        Raises ValueError when `for_block()` was never called, and
        UCPSecurityError when anything collected would cross the trust
        boundary carrying a secret.
        """
        if self._block_spec is None:
            raise ValueError(
                "UCPBuilder.build() requires a block: call for_block() first"
            )
        return UCP(
            block_spec=self._block_spec,
            conventions=dict(self._conventions),
            context_files=list(self._context_files),
            memory_entries=list(self._memory_entries),
            budget=self._budget,
            handoff=self._handoff,
            ucp_id=self._ucp_id,
            run_id=self._run_id,
            producer_agent=self._producer_agent,
            extensions=dict(self._extensions),
        )
