"""Schema constants, frontmatter parser and validation for memory files.

No external dependencies -- stdlib only (Python 3.9+).
No I/O at module level.
"""

import re
from datetime import datetime, timezone, timedelta

# --- Enums ---

VALID_TYPES = ("working", "episodic", "semantic", "procedural")
VALID_AUTHORITIES = ("project", "session", "inferred")

# Authority ordering: higher index = higher authority
AUTHORITY_RANK = {"inferred": 0, "session": 1, "project": 2}

# --- Decay defaults (timedelta from created_at) ---

DECAY_DEFAULTS = {
    "working": timedelta(hours=24),
    "episodic": timedelta(days=30),
    "semantic": None,
    "procedural": None,
}

# --- Field definitions ---

REQUIRED_FIELDS = ("id", "type", "authority", "created_at", "updated_at", "decay_at", "pinned")
OPTIONAL_FIELDS = ("supersedes", "tags", "source_block", "source_agent")
ALL_KNOWN_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ISO8601_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


# --- Frontmatter parser ---

def parse_frontmatter(text: str):
    """Parse a memory Markdown file into (frontmatter_dict, body_str).

    Returns (dict, str) on success.
    Raises ValueError with descriptive message on parse error.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("Frontmatter must start with '---' on line 1")

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("Frontmatter closing '---' not found")

    fm = {}
    for line in lines[1:end_idx]:
        stripped = line.strip()
        if not stripped:
            continue
        colon_pos = stripped.find(":")
        if colon_pos == -1:
            raise ValueError(f"Invalid frontmatter line (no colon): {stripped!r}")
        key = stripped[:colon_pos].strip()
        raw_value = stripped[colon_pos + 1:].strip()
        fm[key] = _parse_scalar(raw_value)

    body = "\n".join(lines[end_idx + 1:])
    # Strip leading newline if present (conventional blank line after ---)
    if body.startswith("\n"):
        body = body[1:]

    return fm, body


def _parse_scalar(value: str):
    """Parse a YAML-like scalar value."""
    if value == "" or value.lower() == "null" or value.lower() == "~":
        return None
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    # Try int
    try:
        return int(value)
    except ValueError:
        pass
    # Try float
    try:
        return float(value)
    except ValueError:
        pass
    # Strip quotes if present
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1]
    return value


# --- Serialization ---

def serialize_frontmatter(fm: dict) -> str:
    """Serialize frontmatter dict to YAML-like string between --- delimiters."""
    lines = ["---"]
    # Write fields in canonical order
    for key in ALL_KNOWN_FIELDS:
        if key in fm:
            lines.append(f"{key}: {_serialize_scalar(fm[key])}")
    # Write any extra fields (unknown but tolerated on write)
    for key in fm:
        if key not in ALL_KNOWN_FIELDS:
            lines.append(f"{key}: {_serialize_scalar(fm[key])}")
    lines.append("---")
    return "\n".join(lines)


def _serialize_scalar(value) -> str:
    """Serialize a scalar value for frontmatter."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


# --- Validation ---

def validate_frontmatter(fm: dict):
    """Validate a frontmatter dict.

    Returns (errors: list[str], warnings: list[str]).
    Does not raise.
    """
    errors = []
    warnings = []

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in fm:
            errors.append(f"Required field '{field}' is missing")

    if errors:
        # Can't validate further without required fields
        return errors, warnings

    # Validate id
    id_val = fm.get("id")
    if id_val is not None:
        if not isinstance(id_val, str) or not UUID4_RE.match(str(id_val)):
            errors.append(f"Field 'id' must be a valid UUID4, got: {id_val!r}")

    # Validate type
    type_val = fm.get("type")
    if type_val not in VALID_TYPES:
        errors.append(
            f"Field 'type' must be one of {VALID_TYPES}, got: {type_val!r}"
        )

    # Validate authority
    auth_val = fm.get("authority")
    if auth_val not in VALID_AUTHORITIES:
        errors.append(
            f"Field 'authority' must be one of {VALID_AUTHORITIES}, got: {auth_val!r}"
        )

    # Validate timestamps
    for ts_field in ("created_at", "updated_at"):
        val = fm.get(ts_field)
        if val is not None and (not isinstance(val, str) or not ISO8601_UTC_RE.match(val)):
            errors.append(f"Field '{ts_field}' must be ISO-8601 UTC ending in Z, got: {val!r}")

    # Validate decay_at (nullable)
    decay_val = fm.get("decay_at")
    if decay_val is not None:
        if not isinstance(decay_val, str) or not ISO8601_UTC_RE.match(decay_val):
            errors.append(f"Field 'decay_at' must be ISO-8601 UTC ending in Z or null, got: {decay_val!r}")

    # Validate pinned
    pinned_val = fm.get("pinned")
    if not isinstance(pinned_val, bool):
        errors.append(f"Field 'pinned' must be true or false, got: {pinned_val!r}")

    # Validate optional fields
    supersedes_val = fm.get("supersedes")
    if supersedes_val is not None:
        if not isinstance(supersedes_val, str) or not UUID4_RE.match(supersedes_val):
            errors.append(f"Field 'supersedes' must be a valid UUID4 or null, got: {supersedes_val!r}")

    tags_val = fm.get("tags")
    if tags_val is not None and not isinstance(tags_val, str):
        errors.append(f"Field 'tags' must be a string, got: {type(tags_val).__name__}")

    for opt_field in ("source_block", "source_agent"):
        val = fm.get(opt_field)
        if val is not None and (not isinstance(val, str) or val == ""):
            errors.append(f"Field '{opt_field}' must be a non-empty string or null, got: {val!r}")

    # Check for unknown fields (warning, not error)
    for key in fm:
        if key not in ALL_KNOWN_FIELDS:
            warnings.append(f"Unknown field '{key}' (will be preserved)")

    return errors, warnings


def now_iso() -> str:
    """Return current UTC time as ISO-8601 string ending in Z."""
    dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str) -> datetime:
    """Parse an ISO-8601 UTC string ending in Z."""
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def extract_title(body: str) -> str:
    """Extract the first # heading from body, or empty string."""
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""
