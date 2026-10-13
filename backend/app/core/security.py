import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
_dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        matched = password_hasher.verify(encoded or _dummy_hash, password)
        return bool(matched and encoded)
    except (VerificationError, InvalidHashError):
        return False


def keyed_hash(secret: str, value: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def csrf_token(secret: str, binding: str) -> str:
    return keyed_hash(secret, f"csrf:{binding}")
