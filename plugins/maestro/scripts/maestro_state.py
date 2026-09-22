"""
maestro_state.py — Schema canonico de estado do Maestro, independente de agente.

Unica porta de leitura/escrita de:
  .maestro/project.yaml   identidade do projeto (versionado)
  .maestro/state.json     estado operacional corrente (derivado/efemero)

API publica:
  state_dir(root)              -> Path
  project_file(root)           -> Path
  state_file(root)             -> Path
  ensure_state_dir(root)       -> Path
  init(root)                   -> dict
  read_project(root)           -> dict          (levanta StateError se invalido)
  write_project(doc, root)     -> Path
  validate_project(doc)        -> (errors, warnings)
  read_state(root)             -> dict          (NUNCA levanta)
  write_state(state, root)     -> Path
  validate_state(doc)          -> (errors, warnings)
  empty_state()                -> dict
  default_project(root)        -> dict

Uso:
  python maestro_state.py --validate
  python maestro_state.py --init
  python maestro_state.py --show [--json]

Sem dependencia externa: somente biblioteca padrao (Python 3.9+).
NAO importa PyYAML por decisao arquitetural (ver plano/specs/F3-02-*.md).
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import maestro_runtime  # noqa: E402

SCHEMA_VERSION = 1
STATE_DIRNAME = ".maestro"
PROJECT_FILENAME = "project.yaml"
STATE_FILENAME = "state.json"

DEFAULT_VERSION = "0.0.0"

PROJECT_REQUIRED = ("id", "name", "version", "root", "maestro_version")
PROJECT_KNOWN = ("schema",) + PROJECT_REQUIRED

STATE_REQUIRED = ("current_block", "phase", "last_updated", "locks")
STATE_KNOWN = ("schema",) + STATE_REQUIRED + ("blocks",)

BLOCK_STATUSES = (
    "planned",
    "ready",
    "running",
    "review",
    "completed",
    "blocked",
    "failed",
    "cancelled",
)

LOCK_REQUIRED = ("id", "owner", "acquired_at")
LOCK_OPTIONAL = ("scope", "expires_at")

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t](.*))?$")
_INT_RE = re.compile(r"^-?\d+$")
_BLOCK_ID_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*)-\w+$")
_WIN_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")


class StateError(Exception):
    """Erro de schema, parsing ou IO em .maestro/. Mensagem sempre descritiva."""


# ---------------------------------------------------------------------------
# Raiz e caminhos
# ---------------------------------------------------------------------------


def _root(root=None) -> Path:
    """Resolve a raiz. Delega a maestro_runtime; cwd como fallback silencioso."""
    if root is not None:
        return Path(root)
    discovered = maestro_runtime.get_root()
    if discovered is None:
        return Path.cwd()
    return discovered


def state_dir(root=None) -> Path:
    return _root(root) / STATE_DIRNAME


def project_file(root=None) -> Path:
    return state_dir(root) / PROJECT_FILENAME


def state_file(root=None) -> Path:
    return state_dir(root) / STATE_FILENAME


def ensure_state_dir(root=None) -> Path:
    """Cria .maestro/ se ausente. Idempotente e nao destrutivo (I1)."""
    d = state_dir(root)
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StateError(f"nao foi possivel criar {d}: {exc}") from exc
    return d


# ---------------------------------------------------------------------------
# YAML: subconjunto restrito (ver spec secao 5.3). Fail-closed.
# ---------------------------------------------------------------------------


def _yaml_scalar(raw: str, lineno: int):
    """Converte um escalar do subconjunto. Levanta StateError fora do subconjunto."""
    s = raw.strip()
    if s == "" or s == "null" or s == "~":
        return None
    if s[0] in "&*":
        return _yaml_reject(lineno, "ancoras e aliases nao sao suportados")
    if s[0] in "[{":
        return _yaml_reject(lineno, "colecoes inline ([] ou {}) nao sao suportadas")
    if s[0] in "|>":
        return _yaml_reject(lineno, "blocos multilinha (| ou >) nao sao suportados")
    if s[0] in "\"'":
        quote = s[0]
        if len(s) < 2 or s[-1] != quote:
            return _yaml_reject(lineno, "aspas nao fechadas")
        inner = s[1:-1]
        if quote in inner or "\\" in inner:
            return _yaml_reject(
                lineno, "aspas internas e escapes nao sao suportados neste subconjunto"
            )
        return inner
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if _INT_RE.match(s):
        return int(s)
    return s


def _yaml_reject(lineno: int, motivo: str):
    raise StateError(f"{PROJECT_FILENAME}: linha {lineno}: {motivo}")


def _strip_comment(raw: str) -> str:
    """Remove comentario inline de um valor nao citado."""
    s = raw.strip()
    if s[:1] in ("\"", "'"):
        return s
    idx = s.find(" #")
    if idx >= 0:
        return s[:idx].strip()
    if s.startswith("#"):
        return ""
    return s


def yaml_subset_load(text: str) -> dict:
    """Parser do subconjunto YAML aceito em project.yaml.

    Aceita: comentarios, chave: valor com indentacao 0 ou 2, escalares
    (string, int, bool, null). Rejeita tudo o mais com numero de linha.
    """
    result: dict = {}
    parent_key = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.rstrip("\r\n")
        if line.strip() == "":
            continue
        stripped = line.lstrip(" ")
        if stripped.startswith("#"):
            continue
        indent = len(line) - len(stripped)
        if "\t" in line[:indent] or stripped.startswith("\t"):
            _yaml_reject(lineno, "tabulacao nao e permitida como indentacao")
        if indent % 2 != 0:
            _yaml_reject(lineno, f"indentacao {indent} nao e multiplo de 2")
        if indent > 2:
            _yaml_reject(lineno, "aninhamento maior que 2 niveis nao e suportado")
        if stripped.startswith("- ") or stripped == "-":
            _yaml_reject(lineno, "listas nao sao suportadas neste subconjunto")
        if stripped.startswith("---") or stripped.startswith("..."):
            _yaml_reject(lineno, "separadores de documento nao sao suportados")
        if stripped[0] in "&*":
            _yaml_reject(lineno, "ancoras e aliases nao sao suportados")

        match = _KEY_RE.match(stripped)
        if not match:
            _yaml_reject(lineno, f"esperado 'chave: valor', encontrado {stripped!r}")
        key = match.group(1)
        raw_value = match.group(2)
        raw_value = "" if raw_value is None else _strip_comment(raw_value)

        if indent == 0:
            if key in result:
                _yaml_reject(lineno, f"chave duplicada no nivel raiz: {key!r}")
            if raw_value == "":
                result[key] = None
                parent_key = key
            else:
                result[key] = _yaml_scalar(raw_value, lineno)
                parent_key = None
        else:
            if parent_key is None:
                _yaml_reject(lineno, "linha indentada sem chave pai")
            if not isinstance(result.get(parent_key), dict):
                result[parent_key] = {}
            if key in result[parent_key]:
                _yaml_reject(lineno, f"chave duplicada em {parent_key!r}: {key!r}")
            result[parent_key][key] = _yaml_scalar(raw_value, lineno)
    return result


def _yaml_quote(value: str) -> str:
    """Cita a string se houver risco de reinterpretacao na releitura."""
    if value == "":
        return '""'
    if value != value.strip():
        return '"{}"'.format(value)
    if value in ("null", "~", "true", "false", "True", "False"):
        return '"{}"'.format(value)
    if _INT_RE.match(value):
        return '"{}"'.format(value)
    if value[0] in "#&*[{|>-\"'" or ": " in value or " #" in value:
        return '"{}"'.format(value)
    return value


def yaml_subset_dump(doc: dict, header: str = "") -> str:
    """Serializa um mapa plano no subconjunto. Nao emite listas nem aninhamento."""
    lines = []
    if header:
        for hline in header.splitlines():
            lines.append("# " + hline if hline else "#")
    for key, value in doc.items():
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif value is None:
            rendered = "null"
        elif isinstance(value, int):
            rendered = str(value)
        elif isinstance(value, str):
            rendered = _yaml_quote(value)
        else:
            raise StateError(
                f"project.yaml: valor de tipo {type(value).__name__} nao e "
                f"serializavel no subconjunto (chave {key!r})"
            )
        lines.append(f"{key}: {rendered}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Escrita atomica (I4)
# ---------------------------------------------------------------------------


def _atomic_write(path: Path, text: str) -> Path:
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    except OSError as exc:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise StateError(f"falha ao escrever {path}: {exc}") from exc
    return path


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# project.yaml
# ---------------------------------------------------------------------------


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", text.lower()).strip("-.")
    return slug or "projeto"


def _detect_maestro_version(root: Path) -> str:
    env = os.environ.get("MAESTRO_VERSION")
    if env and env.strip():
        return env.strip()
    manifest = root / ".claude-plugin" / "plugin.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        version = data.get("version")
        if isinstance(version, str) and version.strip():
            return version.strip()
    except (OSError, ValueError, AttributeError):
        pass
    return DEFAULT_VERSION


def default_project(root=None) -> dict:
    """project.yaml canonico inferido do ambiente. Nenhum valor inventado."""
    r = _root(root)
    name = r.name or str(r)
    return {
        "schema": SCHEMA_VERSION,
        "id": _slug(name),
        "name": name,
        "version": DEFAULT_VERSION,
        "root": r.as_posix(),
        "maestro_version": _detect_maestro_version(r),
    }


def normalize_project(doc: dict) -> dict:
    """Normaliza a forma aninhada do documento-mestre para a forma plana canonica."""
    if not isinstance(doc, dict):
        return {}
    if not (isinstance(doc.get("project"), dict) or isinstance(doc.get("maestro"), dict)):
        return dict(doc)
    flat = {k: v for k, v in doc.items() if k not in ("project", "maestro")}
    project = doc.get("project") or {}
    maestro = doc.get("maestro") or {}
    for key in ("id", "name", "version", "root"):
        if key in project and key not in flat:
            flat[key] = project[key]
    if "version" in maestro and "maestro_version" not in flat:
        flat["maestro_version"] = maestro["version"]
    return flat


def _is_absolute_pathlike(value: str) -> bool:
    return (
        Path(value).is_absolute()
        or value.startswith("/")
        or bool(_WIN_ABS_RE.match(value))
    )


def validate_project(doc, root=None):
    """Valida project.yaml. Retorna (errors, warnings). NUNCA levanta."""
    errors = []
    warnings = []

    if not isinstance(doc, dict):
        return (
            ["project.yaml: documento raiz deve ser um mapa 'chave: valor'"],
            warnings,
        )

    schema = doc.get("schema", SCHEMA_VERSION)
    if not isinstance(schema, int) or isinstance(schema, bool):
        errors.append("project.yaml: campo 'schema' deve ser inteiro")
    elif schema != SCHEMA_VERSION:
        errors.append(
            f"project.yaml: schema desconhecido {schema!r}; "
            f"esta versao do Maestro le somente schema {SCHEMA_VERSION}"
        )

    for field in PROJECT_REQUIRED:
        if field not in doc:
            errors.append(f"project.yaml: campo obrigatorio ausente: '{field}'")
            continue
        value = doc[field]
        if not isinstance(value, str) or value.strip() == "":
            errors.append(
                f"project.yaml: campo '{field}' deve ser string nao vazia "
                f"(recebido: {value!r})"
            )

    if isinstance(doc.get("id"), str) and doc["id"].strip():
        if not _ID_RE.match(doc["id"]):
            errors.append(
                f"project.yaml: campo 'id' invalido: {doc['id']!r}; "
                "esperado minusculas, digitos, '.', '_' ou '-', "
                "iniciando por letra ou digito, ate 64 caracteres"
            )

    if isinstance(doc.get("name"), str) and doc["name"].strip():
        if len(doc["name"]) > 120:
            errors.append(
                f"project.yaml: campo 'name' excede 120 caracteres "
                f"({len(doc['name'])})"
            )

    for field in ("version", "maestro_version"):
        value = doc.get(field)
        if isinstance(value, str) and value.strip() and value != value.strip():
            errors.append(
                f"project.yaml: campo '{field}' nao pode ter espacos nas bordas: "
                f"{value!r}"
            )

    root_value = doc.get("root")
    if isinstance(root_value, str) and root_value.strip():
        if not _is_absolute_pathlike(root_value):
            errors.append(
                f"project.yaml: campo 'root' deve ser caminho absoluto: {root_value!r}"
            )
        else:
            try:
                current = _root(root).resolve()
                declared = Path(root_value)
                if declared.is_absolute() and declared.resolve() != current:
                    warnings.append(
                        f"project.yaml: 'root' declarado ({root_value}) difere da raiz "
                        f"corrente ({current.as_posix()}); projeto provavelmente movido"
                    )
            except (OSError, ValueError, TypeError):
                # validate_project NUNCA levanta: raiz irresolvivel apenas
                # suprime o aviso de "projeto movido".
                pass

    for key in doc:
        if key not in PROJECT_KNOWN:
            warnings.append(f"project.yaml: campo desconhecido ignorado: '{key}'")

    return errors, warnings


def read_project(root=None) -> dict:
    """Le e valida project.yaml. Levanta StateError se ausente ou invalido (I3)."""
    path = project_file(root)
    if not path.exists():
        raise StateError(
            f"{path} nao existe. Rode 'python scripts/maestro_state.py --init'."
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StateError(f"nao foi possivel ler {path}: {exc}") from exc

    doc = normalize_project(yaml_subset_load(text))
    errors, _warnings = validate_project(doc, root=root)
    if errors:
        raise StateError(
            "project.yaml invalido:\n  - " + "\n  - ".join(errors)
        )
    doc.setdefault("schema", SCHEMA_VERSION)
    return doc


def write_project(doc: dict, root=None) -> Path:
    """Valida e escreve project.yaml na forma plana canonica (I5, I4)."""
    normalized = normalize_project(doc)
    normalized.setdefault("schema", SCHEMA_VERSION)
    errors, _warnings = validate_project(normalized, root=root)
    if errors:
        raise StateError(
            "recusando escrever project.yaml invalido:\n  - " + "\n  - ".join(errors)
        )
    ordered = {k: normalized[k] for k in PROJECT_KNOWN if k in normalized}
    for key, value in normalized.items():
        if key not in ordered:
            ordered[key] = value
    ensure_state_dir(root)
    header = (
        "project.yaml - identidade do projeto Maestro (versionado).\n"
        "Subconjunto YAML restrito: mapa plano, escalares apenas.\n"
        "Ver docs/architecture/state.md."
    )
    return _atomic_write(project_file(root), yaml_subset_dump(ordered, header))


# ---------------------------------------------------------------------------
# state.json
# ---------------------------------------------------------------------------


def empty_state() -> dict:
    """Estado vazio canonico (I2)."""
    return {
        "schema": SCHEMA_VERSION,
        "current_block": None,
        "phase": None,
        "last_updated": None,
        "locks": [],
        "blocks": {},
    }


def validate_state(doc):
    """Valida state.json. Retorna (errors, warnings). NUNCA levanta."""
    errors = []
    warnings = []

    if not isinstance(doc, dict):
        return ["state.json: documento raiz deve ser um objeto JSON"], warnings

    schema = doc.get("schema", SCHEMA_VERSION)
    if not isinstance(schema, int) or isinstance(schema, bool):
        errors.append("state.json: campo 'schema' deve ser inteiro")
    elif schema != SCHEMA_VERSION:
        errors.append(
            f"state.json: schema desconhecido {schema!r}; "
            f"esta versao le somente schema {SCHEMA_VERSION}"
        )

    for field in STATE_REQUIRED:
        if field not in doc:
            errors.append(f"state.json: campo obrigatorio ausente: '{field}'")

    for field in ("current_block", "phase"):
        value = doc.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or value.strip() == "":
            errors.append(
                f"state.json: campo '{field}' deve ser string nao vazia ou null "
                f"(recebido: {value!r})"
            )

    last_updated = doc.get("last_updated")
    if last_updated is not None:
        if not isinstance(last_updated, str) or not _ISO_RE.match(last_updated):
            errors.append(
                "state.json: campo 'last_updated' deve ser ISO-8601 UTC terminando "
                f"em 'Z' (ex.: 2026-01-01T00:00:00Z); recebido: {last_updated!r}"
            )

    locks = doc.get("locks")
    if "locks" in doc:
        if not isinstance(locks, list):
            errors.append(
                f"state.json: campo 'locks' deve ser lista (recebido: "
                f"{type(locks).__name__})"
            )
        else:
            for i, lock in enumerate(locks):
                if not isinstance(lock, dict):
                    errors.append(f"state.json: locks[{i}] deve ser objeto")
                    continue
                for field in LOCK_REQUIRED:
                    value = lock.get(field)
                    if not isinstance(value, str) or value.strip() == "":
                        errors.append(
                            f"state.json: locks[{i}] campo obrigatorio '{field}' "
                            "ausente ou vazio"
                        )
                for field in lock:
                    if field not in LOCK_REQUIRED + LOCK_OPTIONAL:
                        warnings.append(
                            f"state.json: locks[{i}] campo desconhecido: '{field}'"
                        )

    blocks = doc.get("blocks", {})
    if "blocks" in doc and not isinstance(blocks, dict):
        errors.append(
            f"state.json: campo 'blocks' deve ser objeto (recebido: "
            f"{type(blocks).__name__})"
        )
        blocks = {}
    if isinstance(blocks, dict):
        for block_id, entry in blocks.items():
            if not isinstance(entry, dict):
                errors.append(f"state.json: blocks['{block_id}'] deve ser objeto")
                continue
            status = entry.get("status")
            if status not in BLOCK_STATUSES:
                errors.append(
                    f"state.json: blocks['{block_id}'].status invalido: {status!r}; "
                    f"esperado um de {', '.join(BLOCK_STATUSES)}"
                )
            blocked_by = entry.get("blocked_by")
            if blocked_by is not None and not isinstance(blocked_by, list):
                errors.append(
                    f"state.json: blocks['{block_id}'].blocked_by deve ser lista"
                )

    # I8 - coerencia de bloco corrente
    current = doc.get("current_block")
    if isinstance(current, str) and isinstance(blocks, dict) and blocks:
        if current not in blocks:
            errors.append(
                f"state.json: current_block {current!r} nao existe em 'blocks' "
                f"({len(blocks)} bloco(s) registrado(s))"
            )
    phase = doc.get("phase")
    if isinstance(current, str) and isinstance(phase, str):
        match = _BLOCK_ID_RE.match(current)
        if match and match.group(1) != phase:
            warnings.append(
                f"state.json: phase {phase!r} nao corresponde ao prefixo de "
                f"current_block {current!r}"
            )

    for key in doc:
        if key not in STATE_KNOWN:
            warnings.append(f"state.json: campo desconhecido ignorado: '{key}'")

    return errors, warnings


def read_state(root=None) -> dict:
    """Le state.json. NUNCA levanta: retorna estado vazio em qualquer falha (I2)."""
    base = empty_state()
    try:
        path = state_file(root)
        if not path.exists():
            return base
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, StateError):
        return base
    if not isinstance(data, dict):
        return base
    base.update(data)
    if not isinstance(base.get("locks"), list):
        base["locks"] = []
    if not isinstance(base.get("blocks"), dict):
        base["blocks"] = {}
    return base


def write_state(state: dict, root=None) -> Path:
    """Valida, carimba last_updated e escreve state.json atomicamente (I4, I5)."""
    doc = empty_state()
    if isinstance(state, dict):
        doc.update(state)
    doc["schema"] = SCHEMA_VERSION
    doc["last_updated"] = _now_iso()
    errors, _warnings = validate_state(doc)
    if errors:
        raise StateError(
            "recusando escrever state.json invalido:\n  - " + "\n  - ".join(errors)
        )
    ordered = {k: doc[k] for k in STATE_KNOWN if k in doc}
    for key, value in doc.items():
        if key not in ordered:
            ordered[key] = value
    ensure_state_dir(root)
    text = json.dumps(ordered, indent=2, ensure_ascii=False) + "\n"
    return _atomic_write(state_file(root), text)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


def init(root=None) -> dict:
    """Cria .maestro/, project.yaml e state.json ausentes. Nao sobrescreve (I1)."""
    ensure_state_dir(root)
    created = []
    ppath = project_file(root)
    if not ppath.exists():
        write_project(default_project(root), root=root)
        created.append(str(ppath))
    spath = state_file(root)
    if not spath.exists():
        write_state(empty_state(), root=root)
        created.append(str(spath))
    return {
        "root": _root(root).as_posix(),
        "state_dir": state_dir(root).as_posix(),
        "created": created,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _arg_value(argv, flag):
    if flag in argv:
        idx = argv.index(flag)
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return None


def _cmd_validate(root, as_json: bool) -> int:
    errors = []
    warnings = []
    notes = []

    try:
        ensure_state_dir(root)
    except StateError as exc:
        errors.append(str(exc))
        return _report("validate", root, errors, warnings, notes, as_json)

    ppath = project_file(root)
    if not ppath.exists():
        try:
            write_project(default_project(root), root=root)
            notes.append(f"project.yaml ausente; criado com valores padrao em {ppath}")
        except StateError as exc:
            errors.append(str(exc))
            return _report("validate", root, errors, warnings, notes, as_json)

    try:
        doc = normalize_project(yaml_subset_load(ppath.read_text(encoding="utf-8")))
    except StateError as exc:
        errors.append(str(exc))
        doc = None
    except OSError as exc:
        errors.append(f"nao foi possivel ler {ppath}: {exc}")
        doc = None

    if doc is not None:
        perrors, pwarnings = validate_project(doc, root=root)
        errors.extend(perrors)
        warnings.extend(pwarnings)

    spath = state_file(root)
    if not spath.exists():
        notes.append("state.json ausente; leitura retorna estado vazio (esperado)")
    else:
        try:
            raw = json.loads(spath.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"state.json ilegivel ou malformado: {exc}")
            raw = None
        if raw is not None:
            serrors, swarnings = validate_state(raw)
            errors.extend(serrors)
            warnings.extend(swarnings)

    return _report("validate", root, errors, warnings, notes, as_json)


def _report(command, root, errors, warnings, notes, as_json: bool) -> int:
    ok = not errors
    if as_json:
        print(
            json.dumps(
                {
                    "command": command,
                    "root": _root(root).as_posix(),
                    "state_dir": state_dir(root).as_posix(),
                    "ok": ok,
                    "errors": errors,
                    "warnings": warnings,
                    "notes": notes,
                },
                ensure_ascii=False,
            )
        )
        return 0 if ok else 1

    print(f"raiz:      {_root(root).as_posix()}")
    print(f"state_dir: {state_dir(root).as_posix()}")
    for note in notes:
        print(f"  nota:  {note}")
    for warning in warnings:
        print(f"  AVISO: {warning}")
    for error in errors:
        print(f"  ERRO:  {error}")
    if ok:
        print("PASS")
        return 0
    print(f"FAIL ({len(errors)} erro(s))")
    return 1


def _cmd_show(root, as_json: bool) -> int:
    ensure_state_dir(root)
    state = read_state(root)
    try:
        project = read_project(root)
        project_error = None
    except StateError as exc:
        project = None
        project_error = str(exc)

    if as_json:
        print(
            json.dumps(
                {
                    "command": "show",
                    "root": _root(root).as_posix(),
                    "project": project,
                    "project_error": project_error,
                    "state": state,
                },
                ensure_ascii=False,
            )
        )
        return 0 if project_error is None else 2

    print(f"raiz:      {_root(root).as_posix()}")
    print(f"state_dir: {state_dir(root).as_posix()}")
    print(f"harness:   {maestro_runtime.detect_harness()}")
    if project is None:
        print(f"projeto:   INDISPONIVEL — {project_error}")
    else:
        print(f"projeto:   {project['id']} ({project['name']})")
        print(f"versao:    {project['version']}  maestro {project['maestro_version']}")
    print(f"bloco:     {state['current_block'] or '-'}")
    print(f"fase:      {state['phase'] or '-'}")
    print(f"atualizado:{state['last_updated'] or '-'}")
    print(f"locks:     {len(state['locks'])}")
    print(f"blocos:    {len(state['blocks'])}")
    return 0 if project_error is None else 2


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    root = _arg_value(argv, "--root")

    try:
        if "--validate" in argv:
            return _cmd_validate(root, as_json)
        if "--init" in argv:
            result = init(root)
            if as_json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print(f"state_dir: {result['state_dir']}")
                if result["created"]:
                    for path in result["created"]:
                        print(f"  criado: {path}")
                else:
                    print("  nada a criar (ja inicializado)")
            return 0
        if "--show" in argv:
            return _cmd_show(root, as_json)
    except StateError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2

    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
