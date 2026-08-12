"""Redaction helpers — trim sensitive data before storing to JSONL."""
import hashlib
import re

_EMAIL_RE = re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b')
_JWT_RE = re.compile(r'eyJ[A-Za-z0-9._-]{20,}')
_BEARER_RE = re.compile(r'(?i)bearer\s+\S+')
_KV_RE = re.compile(r'(?i)(token|secret|key|password|auth)=(?!\*\*\*)\S+')
_HEADER_KV_RE = re.compile(r'(?i)(token|secret|key|password|auth|x-api-key):\s*(?!\*\*\*)(\S+)')
_OPENAI_KEY_RE = re.compile(r'\bsk-[A-Za-z0-9]{20,}\b')
_HEX_TOKEN_RE = re.compile(r'(?<=[=:\s])[0-9a-fA-F]{32,}\b')
_SENSITIVE_KEYS = frozenset({"token", "secret", "key", "password", "auth", "credential"})
_IMAGE_TOOLS = frozenset({"screenshot", "screenshot_som", "verify_visual_state"})


def redact_text(s: str, max_len: int = 500) -> str:
    if not s:
        return s
    s = _EMAIL_RE.sub("***@***", s)
    s = _BEARER_RE.sub("Bearer ***", s)
    s = _JWT_RE.sub("***JWT***", s)
    s = _OPENAI_KEY_RE.sub("***", s)
    s = _KV_RE.sub(r'\1=***', s)
    s = _HEADER_KV_RE.sub(r'\1: ***', s)
    s = _HEX_TOKEN_RE.sub("***", s)
    if len(s) > max_len:
        extra = len(s) - max_len
        s = s[:max_len] + f"...[truncated {extra} chars]"
    return s


def redact_args(kw: dict) -> dict:
    """Replace sensitive kwargs with ***."""
    out = {}
    for k, v in kw.items():
        if k.lower() in _SENSITIVE_KEYS:
            out[k] = "***"
        elif isinstance(v, str):
            out[k] = redact_text(v, max_len=200)
        else:
            out[k] = v
    return out


def redact_result(tool: str, raw) -> str:
    """Tool-specific result redaction. Returns text suitable for storage."""
    if not isinstance(raw, str):
        return str(raw)[:500]
    if tool in _IMAGE_TOOLS:
        if raw.startswith("data:") or len(raw) > 5000:
            digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
            return f"<image: sha256={digest} len={len(raw)}>"
    return redact_text(raw, max_len=500)
