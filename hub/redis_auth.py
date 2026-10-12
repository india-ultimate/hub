"""The worker's Redis password, derived from SECRET_KEY on both sides."""

import hashlib
import hmac


def password(secret_key: str) -> str:
    return hmac.new(secret_key.encode(), b"redis", hashlib.sha256).hexdigest()
