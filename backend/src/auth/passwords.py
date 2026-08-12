"""Password hashing utilities using bcrypt directly.

We call ``bcrypt`` directly rather than going through passlib, because
passlib 1.7.x performs a self-test at import time that hashes a >72 byte
fixture string; bcrypt >= 4.1 raises ``ValueError`` for any secret over
72 bytes and that self-test aborts, which breaks every caller. passlib
also hasn't seen a release since 2020, so there's no fix coming.

bcrypt itself truncates at 72 bytes historically, so we pre-truncate
(documented industry practice) to avoid surprising callers who pass
long passphrases.
"""

from __future__ import annotations

import bcrypt

_MAX_BCRYPT_BYTES = 72


def _encode(password: str) -> bytes:
    """Encode to UTF-8 and truncate to bcrypt's 72-byte limit."""
    return password.encode("utf-8")[:_MAX_BCRYPT_BYTES]


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the given plaintext password."""
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if the plaintext password matches the bcrypt hash."""
    try:
        return bcrypt.checkpw(_encode(plain), hashed.encode("utf-8"))
    except ValueError:
        # Malformed hash string — treat as a mismatch rather than crashing.
        return False


__all__ = ["hash_password", "verify_password"]
