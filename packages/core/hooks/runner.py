"""
runner.py — Hooks bounded: executa comandos externos em pontos do ciclo de vida
do Maestro com limite de tempo, ambiente sanitizado e spool de falhas.

"Bounded" significa tres limites duros:
  1. tempo   — todo hook tem timeout; ao expirar o processo e morto (kill).
  2. saida   — stdout/stderr sao truncados em MAX_OUTPUT_CHARS.
  3. shell   — nao ha shell. O comando e dividido com shlex e executado direto.

API publica:
  HOOK_EVENTS: frozenset[str]
  HookError(Exception)
  @dataclass HookConfig(event, command, timeout=30, critical=False, env=None)
  @dataclass HookResult(event, command, success, exit_code, stdout, stderr,
                        timed_out, error)
  class HookRunner:
      __init__(hooks=None, spool_path=None, root=None)
      run_event(event: str, context: dict | None = None) -> list[HookResult]
      flush_spool() -> list[HookResult]
      clear_spool() -> int

Spool: .maestro/hooks/spool.jsonl — JSONL append-only, um registro por falha.
Biblioteca pura: so stdlib.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - dependente de plataforma
    import fcntl
except ImportError:  # Windows
    fcntl = None  # type: ignore[assignment]


HOOK_EVENTS = frozenset(
    {
        "pre_run",
        "post_run",
        "pre_review",
        "post_review",
        "on_fail",
        "on_block_complete",
    }
)

#: Limite de caracteres capturados por stream. Alem disso, trunca com marcador.
MAX_OUTPUT_CHARS = 8192

#: Limite de caracteres gravados por stream no spool (registro mais enxuto).
MAX_SPOOL_OUTPUT_CHARS = 4096

#: Timeout padrao de um hook, em segundos.
DEFAULT_TIMEOUT = 30

#: Tempo maximo de espera pelo lock do spool, em segundos.
LOCK_TIMEOUT = 10.0

#: Prefixo de toda variavel derivada do context.
ENV_PREFIX = "MAESTRO_HOOK_"

_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_FORBIDDEN_CHARS = ("\n", "\r", "\0")


class HookError(Exception):
    """Levantada em erro de configuracao de hook ou em falha de hook critico."""

    def __init__(self, message: str, results: "list[HookResult] | None" = None):
        super().__init__(message)
        #: Resultados ja coletados ate o ponto da falha (pode ser vazio).
        self.results: "list[HookResult]" = list(results or [])


@dataclass
class HookConfig:
    """Configuracao de um hook: o que rodar, quando, por quanto tempo."""

    event: str
    command: str
    timeout: int = DEFAULT_TIMEOUT
    critical: bool = False
    env: "dict | None" = None


@dataclass
class HookResult:
    """Resultado da execucao de um hook. ``exit_code`` e None se nao houve saida."""

    event: str
    command: str
    success: bool
    exit_code: "int | None"
    stdout: str
    stderr: str
    timed_out: bool
    error: "str | None"

    def to_dict(self) -> dict:
        return {
            "event": self.event,
            "command": self.command,
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "error": self.error,
        }


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n[...truncado em {limit} caracteres]"


def _scrub(value: object) -> str:
    """Converte para string e remove os caracteres proibidos em env (I3)."""
    text = value if isinstance(value, str) else str(value)
    for char in _FORBIDDEN_CHARS:
        text = text.replace(char, " ")
    return text


def _sanitize_context(context: "dict | None") -> dict:
    """Aplica a regra de sanitizacao do contrato (I3).

    Chaves fora de ``[A-Za-z_][A-Za-z0-9_]*`` sao descartadas em silencio.
    Valores viram string com ``\\n``, ``\\r`` e ``\\0`` trocados por espaco.
    A chave final e ``MAESTRO_HOOK_`` + chave em MAIUSCULA.
    """
    result: dict = {}
    if not isinstance(context, dict):
        return result
    for key, value in context.items():
        if not isinstance(key, str) or not _KEY_RE.match(key):
            continue
        result[ENV_PREFIX + key.upper()] = _scrub(value)
    return result


def _split_command(command: str) -> list:
    """Divide o comando sem shell. Em Windows, preserva as barras invertidas."""
    if not isinstance(command, str) or not command.strip():
        raise ValueError("command vazio")
    raw = command.replace("\\", "\\\\") if os.name == "nt" else command
    argv = shlex.split(raw)
    if not argv:
        raise ValueError("command vazio apos parsing")
    return argv


class HookRunner:
    """Executa hooks configurados por evento, com timeout e spool de falhas."""

    def __init__(
        self,
        hooks: "list | None" = None,
        spool_path: "str | Path | None" = None,
        root: "str | Path | None" = None,
    ):
        self.root = self._resolve_root(root)
        self.hooks: "list[HookConfig]" = self._coerce_hooks(hooks)
        if spool_path is not None:
            self.spool_path = Path(spool_path)
        else:
            self.spool_path = self.root / ".maestro" / "hooks" / "spool.jsonl"

    # ---------------------------------------------------------------- setup

    @staticmethod
    def _resolve_root(root: "str | Path | None") -> Path:
        if root is not None:
            return Path(root)
        try:
            import maestro_runtime  # type: ignore

            resolved = maestro_runtime.get_root()
        except Exception:
            resolved = None
        return resolved if resolved is not None else Path.cwd()

    @staticmethod
    def _coerce_hooks(hooks: "list | None") -> "list[HookConfig]":
        """Aceita HookConfig ou dict. Config invalida falha cedo (fail-closed)."""
        coerced: "list[HookConfig]" = []
        for index, item in enumerate(hooks or []):
            if isinstance(item, HookConfig):
                config = item
            elif isinstance(item, dict):
                if "event" not in item or "command" not in item:
                    raise HookError(
                        f"hook[{index}]: 'event' e 'command' sao obrigatorios"
                    )
                config = HookConfig(
                    event=item["event"],
                    command=item["command"],
                    timeout=item.get("timeout", DEFAULT_TIMEOUT),
                    critical=bool(item.get("critical", False)),
                    env=item.get("env"),
                )
            else:
                raise HookError(
                    f"hook[{index}]: esperado HookConfig ou dict, veio {type(item).__name__}"
                )
            if config.event not in HOOK_EVENTS:
                raise HookError(
                    f"hook[{index}]: evento invalido {config.event!r}. "
                    f"Validos: {sorted(HOOK_EVENTS)}"
                )
            if not isinstance(config.command, str) or not config.command.strip():
                raise HookError(f"hook[{index}]: 'command' vazio")
            try:
                timeout = int(config.timeout)
            except (TypeError, ValueError):
                timeout = DEFAULT_TIMEOUT
            config.timeout = timeout if timeout > 0 else DEFAULT_TIMEOUT
            coerced.append(config)
        return coerced

    # ------------------------------------------------------------ execucao

    def run_event(self, event: str, context: "dict | None" = None) -> "list[HookResult]":
        """Roda todos os hooks do evento, em ordem de configuracao.

        Hook nao-critico que falha e registrado no spool e a execucao segue (I1).
        Hook critico que falha e registrado no spool e levanta ``HookError`` (I2).
        Evento fora de ``HOOK_EVENTS`` levanta ``HookError`` sem rodar nada.
        """
        if not isinstance(event, str) or event not in HOOK_EVENTS:
            raise HookError(
                f"evento invalido {event!r}. Validos: {sorted(HOOK_EVENTS)}"
            )

        context_env = _sanitize_context(context)
        context_env.setdefault(ENV_PREFIX + "EVENT", event)

        results: "list[HookResult]" = []
        for config in self.hooks:
            if config.event != event:
                continue
            result = self._run_one(config, context_env)
            results.append(result)
            if not result.success:
                self._spool(result, critical=config.critical)
                if config.critical:
                    raise HookError(
                        f"hook critico falhou no evento {event!r}: {config.command!r} "
                        f"(exit_code={result.exit_code}, timed_out={result.timed_out})",
                        results=results,
                    )
        return results

    def _build_env(self, config: HookConfig, context_env: dict) -> dict:
        env = dict(os.environ)
        if isinstance(config.env, dict):
            for key, value in config.env.items():
                if not isinstance(key, str) or not _KEY_RE.match(key):
                    continue
                env[key] = _scrub(value)
        env.update(context_env)
        return env

    def _run_one(self, config: HookConfig, context_env: dict) -> HookResult:
        try:
            argv = _split_command(config.command)
        except ValueError as exc:
            return HookResult(
                event=config.event,
                command=config.command,
                success=False,
                exit_code=None,
                stdout="",
                stderr="",
                timed_out=False,
                error=f"comando nao parseavel: {exc}",
            )

        env = self._build_env(config, context_env)
        timed_out = False
        exit_code: "int | None" = None
        error: "str | None" = None
        stdout = ""
        stderr = ""

        try:
            # Arquivos temporarios em vez de PIPE: proc.wait(timeout) com PIPE
            # trava se o hook produzir mais saida que o buffer do SO.
            with tempfile.TemporaryFile() as out_f, tempfile.TemporaryFile() as err_f:
                proc = subprocess.Popen(
                    argv,
                    stdout=out_f,
                    stderr=err_f,
                    stdin=subprocess.DEVNULL,
                    env=env,
                    cwd=str(self.root),
                )
                try:
                    exit_code = proc.wait(timeout=config.timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    proc.kill()
                    try:
                        proc.wait(timeout=5)
                    except Exception:
                        pass
                    exit_code = None
                    error = f"timeout de {config.timeout}s expirado"
                out_f.seek(0)
                stdout = _truncate(
                    out_f.read().decode("utf-8", "replace"), MAX_OUTPUT_CHARS
                )
                err_f.seek(0)
                stderr = _truncate(
                    err_f.read().decode("utf-8", "replace"), MAX_OUTPUT_CHARS
                )
        except FileNotFoundError:
            error = f"executavel nao encontrado: {argv[0]!r}"
        except OSError as exc:
            error = f"falha ao iniciar o processo: {exc}"

        success = (not timed_out) and (error is None) and (exit_code == 0)
        return HookResult(
            event=config.event,
            command=config.command,
            success=success,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            error=error,
        )

    # ---------------------------------------------------------------- spool

    @contextmanager
    def _spool_lock(self):
        """Single writer. Unix usa flock; Windows/fallback usa lockfile 'x'."""
        self.spool_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.spool_path.with_name(self.spool_path.name + ".lock")

        if fcntl is not None:
            with open(lock_path, "a+") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return

        deadline = time.monotonic() + LOCK_TIMEOUT
        handle = None
        while True:
            try:
                handle = open(lock_path, "x")
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise HookError(
                        f"lock do spool ocupado por mais de {LOCK_TIMEOUT}s: {lock_path}"
                    )
                time.sleep(0.05)
        try:
            yield
        finally:
            try:
                handle.close()
            except Exception:
                pass
            try:
                os.remove(lock_path)
            except OSError:
                pass

    def _spool(self, result: HookResult, critical: bool = False) -> None:
        """Grava uma linha JSON no spool. Append-only (I4). Nunca reescreve."""
        record = {
            "schema": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "critical": bool(critical),
            "event": result.event,
            "command": result.command,
            "success": result.success,
            "exit_code": result.exit_code,
            "stdout": _truncate(result.stdout, MAX_SPOOL_OUTPUT_CHARS),
            "stderr": _truncate(result.stderr, MAX_SPOOL_OUTPUT_CHARS),
            "timed_out": result.timed_out,
            "error": result.error,
        }
        line = json.dumps(record, ensure_ascii=False)
        with self._spool_lock():
            with open(self.spool_path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())

    def flush_spool(self) -> "list[HookResult]":
        """Le o spool e devolve as falhas registradas como ``HookResult``.

        Leitura pura: nao apaga nada (I4). Para descartar, use ``clear_spool()``.
        Linha corrompida vira um ``HookResult`` com ``error`` descritivo.
        """
        if not self.spool_path.exists():
            return []
        results: "list[HookResult]" = []
        with self._spool_lock():
            with open(self.spool_path, "r", encoding="utf-8") as handle:
                raw_lines = handle.readlines()
        for number, raw in enumerate(raw_lines, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                results.append(
                    HookResult(
                        event="",
                        command="",
                        success=False,
                        exit_code=None,
                        stdout="",
                        stderr="",
                        timed_out=False,
                        error=f"linha {number} do spool corrompida: {exc}",
                    )
                )
                continue
            results.append(
                HookResult(
                    event=str(record.get("event", "")),
                    command=str(record.get("command", "")),
                    success=bool(record.get("success", False)),
                    exit_code=record.get("exit_code"),
                    stdout=str(record.get("stdout", "")),
                    stderr=str(record.get("stderr", "")),
                    timed_out=bool(record.get("timed_out", False)),
                    error=record.get("error"),
                )
            )
        return results

    def clear_spool(self) -> int:
        """Descarta o spool. Devolve quantos registros foram removidos."""
        if not self.spool_path.exists():
            return 0
        with self._spool_lock():
            with open(self.spool_path, "r", encoding="utf-8") as handle:
                count = sum(1 for line in handle if line.strip())
            os.remove(self.spool_path)
        return count
