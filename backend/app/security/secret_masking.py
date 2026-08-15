from __future__ import annotations

import re
from collections.abc import Iterable

SENSITIVE_PATTERN = re.compile(
    r"(?i)(password|passwd|pwd|cookie|authorization|csrf|token)\s*[:=]\s*([^\s,;]+)"
)


def mask_secrets(message: str, secrets: Iterable[str] = ()) -> str:
    safe = SENSITIVE_PATTERN.sub(r"\1=***", str(message))
    for secret in secrets:
        if secret:
            safe = safe.replace(secret, "***")
    return safe

