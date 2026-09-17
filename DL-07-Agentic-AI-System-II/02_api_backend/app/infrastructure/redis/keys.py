"""The only place Redis key formats are defined (docs/03_data_design.md section 5.2).

Key parts that come from users are always hashed, so no personal data or raw
client input ends up in a key name.
"""

from __future__ import annotations

from app.core.crypto import sha256_hex


class RedisKeys:
    def __init__(self, env: str) -> None:
        self._prefix = f"tsa:{env}:"

    def rate_limit(self, scope: str, subject_hash: str) -> str:
        return f"{self._prefix}rl:{scope}:{subject_hash}"

    def idempotency(self, principal_hash: str, method: str, route: str, key: str) -> str:
        route_hash = sha256_hex(route.encode())[:16]
        key_hash = sha256_hex(key.encode())
        return f"{self._prefix}idem:{principal_hash}:{method.upper()}:{route_hash}:{key_hash}"
