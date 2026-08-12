"""Static JS-contract test: every JS helper called from Python must exist in luna_helpers.js.

Matching heuristic (conservative — prefer false-negatives over false-positives):
  JS side:   extract `name:` keys from the `window.__luna_mcp = { ... }` block.
             Pattern: leading whitespace + identifier + colon, inside the object literal.
  Python side: scan all .py files under src/ for the first string-literal argument to
             call_fn(...)/_call(...) usages.  Only treat it as a JS method name if:
               - matches /^[a-zA-Z][a-zA-Z0-9_]*$/  (normal identifier)
               - does NOT contain double-underscore (__) – those are internal values
               - length >= 3 – single/two-char strings are unlikely to be helpers
               - is NOT a pure lowercase short word (values like "compact", "ui_only"
                 are filtered by requiring either a capital letter or a known snake_case
                 helper that maps to a camelCase method; we conservatively skip
                 all-lowercase strings that contain an underscore OR are ≤8 chars
                 without uppercase — these are arguments, not method names).

  The filter intentionally under-matches; a few argument strings may slip through as
  "called helpers" but they will be present in the JS names set and cause no failure.
  Any new genuine drift (Python calls a helper that has no matching JS definition)
  will still be caught.
"""
import re
from pathlib import Path

import pytest

# Paths
_ROOT = Path(__file__).parent.parent.parent  # repo root
_JS_FILE = _ROOT / "js" / "luna_helpers.js"
_SRC_DIR = _ROOT / "server" / "src" / "luna_mcp"


def _extract_js_names() -> set[str]:
    """Return set of helper names defined in window.__luna_mcp = { ... }."""
    text = _JS_FILE.read_text(encoding="utf-8")
    # Pattern: line starting with optional whitespace, then identifier:
    # Only inside the __luna_mcp object (after line 500 where object starts).
    # We use a simple regex — conservative: requires word char then colon.
    names = set()
    in_block = False
    for line in text.splitlines():
        if "window.__luna_mcp = {" in line:
            in_block = True
        if in_block:
            m = re.match(r"^\s{4,}([a-zA-Z_][a-zA-Z0-9_]*):\s", line)
            if m:
                names.add(m.group(1))
            # Stop at closing of top-level object (line starting with "};")
            if re.match(r"^\s{0,4}\};", line) and not line.strip().startswith("//"):
                if len(names) > 5:  # we've already collected real entries
                    break
    return names


def _is_method_name(s: str) -> bool:
    """Conservative filter: only flag names that look like JS method calls, not value args."""
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*", s):
        return False
    if "__" in s:
        return False  # internal value (e.g. "__fp__")
    if len(s) < 3:
        return False
    # Accept if it has at least one uppercase (camelCase) or is long (>=10 chars)
    # Short all-lowercase like "compact" are argument values, not method names
    has_upper = any(c.isupper() for c in s)
    if has_upper:
        return True
    # snake_case methods: must be >=9 chars to avoid matching short value strings
    return len(s) >= 9


def _extract_python_calls() -> set[str]:
    """Extract JS helper method names called from Python source."""
    # Match call_fn("name"...) or _call("name"...) — first string arg
    pattern = re.compile(r'(?:call_fn|_call)\(\s*["\']([a-zA-Z][a-zA-Z0-9_]*)["\']')
    names = set()
    for py_file in _SRC_DIR.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            name = m.group(1)
            if _is_method_name(name):
                names.add(name)
    return names


def test_js_helpers_file_exists():
    assert _JS_FILE.exists(), f"luna_helpers.js not found at {_JS_FILE}"


def test_js_names_nonempty():
    names = _extract_js_names()
    assert len(names) >= 20, f"Expected >=20 JS helpers, got {len(names)}: {names}"


def test_python_calls_nonempty():
    calls = _extract_python_calls()
    assert len(calls) >= 10, f"Expected >=10 Python->JS calls, got {len(calls)}: {calls}"


def test_all_python_calls_have_js_definition():
    """Every JS helper called from Python must be defined in luna_helpers.js."""
    js_names = _extract_js_names()
    py_calls = _extract_python_calls()
    missing = py_calls - js_names
    assert not missing, (
        "Python calls JS helpers not defined in luna_helpers.js:\n"
        + "\n".join(f"  {n}" for n in sorted(missing))
        + f"\n\nDefined JS helpers: {sorted(js_names)}"
    )


def test_js_version_is_1_6_1():
    text = _JS_FILE.read_text(encoding="utf-8")
    assert "1.6.1" in text, "luna_helpers.js version must be 1.6.1"


# ── M4: diagnoseRendering JS contract ────────────────────────────────────────

def _diag_rendering_body() -> str:
    """Extract the diagnoseRendering function body from luna_helpers.js."""
    text = _JS_FILE.read_text(encoding="utf-8")
    start = text.find("diagnoseRendering: function(")
    assert start != -1, "diagnoseRendering not found in luna_helpers.js"
    # find closing of the function — count braces
    depth = 0
    i = start
    in_fn = False
    while i < len(text):
        if text[i] == '{':
            depth += 1
            in_fn = True
        elif text[i] == '}':
            depth -= 1
            if in_fn and depth == 0:
                return text[start:i+1]
        i += 1
    return text[start:]


_DIAG_BODY = _diag_rendering_body()

_NEW_FIELDS = ["ambientIntensity", "fog", "pixelLightCount", "shadowDistance", "vSyncCount"]


@pytest.mark.parametrize("field_name", _NEW_FIELDS)
def test_diag_rendering_field_present(field_name):
    """Each new rendering field appears in diagnoseRendering body."""
    assert field_name in _DIAG_BODY, f"{field_name!r} not found in diagnoseRendering"


@pytest.mark.parametrize("field_name", _NEW_FIELDS)
def test_diag_rendering_field_has_na_fallback(field_name):
    """Each new rendering field has a try/catch emitting 'n/a'."""
    # check that n/a appears near the field name (within 200 chars)
    idx = _DIAG_BODY.find(field_name)
    assert idx != -1
    window = _DIAG_BODY[idx:idx+200]
    assert "n/a" in window, f"'n/a' fallback not found near {field_name!r}"


def test_diag_rendering_light_budget_threshold():
    """Light budget heuristic compares > 4 and emits 'light budget'."""
    assert "> _LIGHT_BUDGET" in _DIAG_BODY or "> 4" in _DIAG_BODY, \
        "Light budget threshold (> 4) not found in diagnoseRendering"
    assert "light budget" in _DIAG_BODY, "'light budget' string not found in diagnoseRendering"


def test_diag_rendering_lightcount_field_present():
    """lightCount field appears in diagnoseRendering body."""
    assert "lightCount" in _DIAG_BODY, "lightCount not found in diagnoseRendering"
