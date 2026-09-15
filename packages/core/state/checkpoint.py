"""
checkpoint.py — Checkpoints e recovery: grava e restaura o estado de um bloco
em execução para permitir retomada após crash ou interrupção de sessão.

API:
  CheckpointError(Exception)
  class Checkpoint:
      __init__(root=None)
      save(block: dict) -> Path
      load(block_id: str) -> dict | None
      exists(block_id: str) -> bool
      clear(block_id: str) -> bool
      has_git_drift(block_id: str) -> bool

Schema de .maestro/snapshots/<block_id>.json:
  {"schema": 1, "block_id": "...", "timestamp": "...", "git_head_sha": "...",
   "block_state": {...}, "tentativas": 0, "notes": []}
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


class CheckpointError(Exception):
    """Levantada quando o checkpoint não pode ser gravado (ex: block sem id)."""


class Checkpoint:
    """Grava e restaura snapshots de estado de blocos em execução."""

    def __init__(self, root: "str | Path | None" = None):
        if root is not None:
            self.root = Path(root)
        else:
            resolved_root = None
            try:
                import maestro_runtime  # type: ignore

                resolved_root = maestro_runtime.get_root()
            except Exception:
                resolved_root = None
            self.root = resolved_root if resolved_root is not None else Path.cwd()

    def _snapshots_dir(self) -> Path:
        return self.root / ".maestro" / "snapshots"

    def _snapshot_path(self, block_id: str) -> Path:
        return self._snapshots_dir() / f"{block_id}.json"

    def _git_head_sha(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.root,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def save(self, block: dict) -> Path:
        block_id = block.get("id") if isinstance(block, dict) else None
        if not block_id:
            raise CheckpointError("block['id'] ausente — não é possível gravar checkpoint")

        snapshots_dir = self._snapshots_dir()
        snapshots_dir.mkdir(parents=True, exist_ok=True)

        checkpoint = {
            "schema": 1,
            "block_id": block_id,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "git_head_sha": self._git_head_sha(),
            "block_state": dict(block),
            "tentativas": block.get("tentativas", 0),
            "notes": block.get("notas", block.get("notes", [])),
        }

        path = self._snapshot_path(block_id)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        return path

    def load(self, block_id: str) -> "dict | None":
        path = self._snapshot_path(block_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def exists(self, block_id: str) -> bool:
        return self._snapshot_path(block_id).exists()

    def clear(self, block_id: str) -> bool:
        path = self._snapshot_path(block_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def has_git_drift(self, block_id: str) -> bool:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.root,
            )
            current_sha = result.stdout.strip()
        except Exception:
            return False

        checkpoint = self.load(block_id)
        if not checkpoint:
            return False
        saved_sha = checkpoint.get("git_head_sha", "")
        return bool(saved_sha) and (current_sha != saved_sha)
