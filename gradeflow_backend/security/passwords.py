from argon2 import PasswordHasher
from argon2.low_level import Type

from gradeflow_backend.config import get_settings

# Configure argon2id
_ph = PasswordHasher(
    time_cost=3,  # iterations
    memory_cost=64 * 1024,  # 64 MB
    parallelism=2,
    hash_len=32,
    salt_len=16,
    type=Type.ID,  # argon2id
)


def hash_password(plaintext: str) -> str:
    cfg = get_settings().security
    if len(plaintext) < cfg.password_min_length:
        raise ValueError(f"Password must be at least {cfg.password_min_length} characters")
    return _ph.hash(plaintext)


def verify_password(plaintext: str, password_hash: str) -> bool:
    try:
        _ph.verify(password_hash, plaintext)
        return True
    except Exception:
        return False


def needs_rehash(password_hash: str) -> bool:
    # Allows rehashing if parameters change
    try:
        return _ph.check_needs_rehash(password_hash)
    except Exception:
        return True
