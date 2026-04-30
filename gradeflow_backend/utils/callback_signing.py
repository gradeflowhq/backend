import hashlib
import hmac
import json
from typing import Any

from pydantic import BaseModel

CALLBACK_SIGNATURE_HEADER = "X-GradeFlow-Signature"


def dump_callback_payload(payload: BaseModel | dict[str, Any]) -> bytes:
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def sign_callback_payload(secret: str, payload: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_callback_signature(secret: str, payload: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    expected = sign_callback_payload(secret, payload)
    return hmac.compare_digest(expected, signature)
