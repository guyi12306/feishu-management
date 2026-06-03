import base64
from datetime import datetime, timezone
from functools import lru_cache

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from .config import get_settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _signer() -> TimestampSigner:
    return TimestampSigner(get_settings().session_secret, salt="lark-session")


def sign_session(user_id: int) -> str:
    return _signer().sign(str(user_id)).decode("utf-8")


def parse_session(token: str | None) -> int | None:
    if not token:
        return None
    try:
        raw = _signer().unsign(
            token,
            max_age=get_settings().session_max_age_seconds,
        )
        return int(raw.decode("utf-8"))
    except (BadSignature, SignatureExpired, ValueError):
        return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    secret = get_settings().session_secret.encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"lark-secrets-v1",
        iterations=200_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret))
    return Fernet(key)


def encrypt_secret(plain: str) -> bytes:
    return _fernet().encrypt(plain.encode("utf-8"))


def decrypt_secret(token: bytes) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def mask_secret(value: str | None, keep: int = 4) -> str:
    """脱敏显示;sk-...abcd 风格。"""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return value[: max(2, keep // 2)] + "…" + "*" * 6 + value[-keep:]
