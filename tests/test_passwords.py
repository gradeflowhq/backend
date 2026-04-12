import pytest

from gradeflow_backend.security.passwords import hash_password, needs_rehash, verify_password


def test_hash_and_verify() -> None:
    h = hash_password("securepassword123")
    assert verify_password("securepassword123", h) is True


def test_verify_wrong_password() -> None:
    h = hash_password("securepassword123")
    assert verify_password("wrongpassword", h) is False


def test_verify_garbage_hash() -> None:
    assert verify_password("anything", "not-a-real-hash") is False


def test_hash_too_short_raises() -> None:
    with pytest.raises(ValueError, match="at least"):
        hash_password("ab")


def test_needs_rehash_fresh() -> None:
    h = hash_password("securepassword123")
    assert needs_rehash(h) is False


def test_needs_rehash_incompatible() -> None:
    assert needs_rehash("$argon2i$v=19$m=1,t=1,p=1$c29tZXNhbHQ$abc") is True
