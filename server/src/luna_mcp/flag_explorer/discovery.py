"""Regex scan of Jakefile.js for flag references."""
import pathlib
import re

_LUNA_JSON_BRACKET_RE = re.compile(r'luna\.json\[?\s*[\'"](\w+)[\'"]')
_LUNA_JSON_DOT_RE = re.compile(r'luna\.json\.(\w+)')
_CONFIG_FLAG_RE = re.compile(r'config\[\s*[\'"](\w+)[\'"]')
_GET_OPTION_RE = re.compile(r'getOption\s*\(\s*[\'"](\w+)[\'"]')

_CONFIG_NOISE = frozenset({"path", "name", "type", "value", "default", "key", "id", "src", "dest"})

_PATTERNS = [
    (_LUNA_JSON_BRACKET_RE, "luna_json"),
    (_LUNA_JSON_DOT_RE, "luna_json_dot"),
    (_CONFIG_FLAG_RE, "config"),
    (_GET_OPTION_RE, "getOption"),
]


def scan_jakefile_flags(jakefile_path: pathlib.Path) -> dict[str, list[str]]:
    """Return {flag_name: [source_locations]} parsed from jakefile."""
    if not jakefile_path.exists():
        return {}
    try:
        text = jakefile_path.read_text(errors="replace")
    except Exception:
        return {}
    flags: dict[str, list[str]] = {}
    for pattern, label in _PATTERNS:
        for m in pattern.finditer(text):
            name = m.group(1)
            if label == "config" and name in _CONFIG_NOISE:
                continue
            line_no = text[: m.start()].count("\n") + 1
            flags.setdefault(name, []).append(f"{label}:line{line_no}")
    return flags
