"""Mask secrets in transcript text before it leaves the machine.

A deterministic, conservative filter run over the raw transcript before it is
sent to an external reflection provider (architecture section 9: redaction is
the enforcement point). Keeps structure and ordinary prose; replaces secret
spans with ``[REDACTED]``. Pure and unit-tested with synthetic secrets only.
"""

from __future__ import annotations

import re

_REDACTED = "[REDACTED]"

# Order matters: the multi-line private-key block runs first.
_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bgh[posru]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{12,}"),
]

# key = value / "key": "value" for sensitive key names; preserve the key name.
# Group 1 is an optional identifier prefix so a sensitive word that is the
# trailing segment of a larger name (DEEPSEEK_API_KEY) still matches.
_KV = re.compile(
    r"(?i)\b([A-Za-z0-9]*_)?(password|passwd|secret|token|api[_-]?key|apikey"
    r"|authorization|access[_-]?key|client[_-]?secret)(\s*[:=]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^\s,}\)]+)"
)


def _mask_kv(m: re.Match[str]) -> str:
    prefix = m.group(1) or ""
    value = m.group(4)
    quote = value[:1] if value[:1] in "\"'" else ""
    return f"{prefix}{m.group(2)}{m.group(3)}{quote}{_REDACTED}{quote}"


def redact(text: str) -> str:
    """Replace secret-shaped spans in ``text`` with ``[REDACTED]``."""
    for pat in _PATTERNS:
        text = pat.sub(_REDACTED, text)
    return _KV.sub(_mask_kv, text)
