from gradeflow_backend.utils.callback_signing import (
    dump_callback_payload,
    sign_callback_payload,
    verify_callback_signature,
)


def test_verify_callback_signature_accepts_valid_signature() -> None:
    payload = dump_callback_payload({"assessment_id": "a1", "type": "run", "submissions": []})
    signature = sign_callback_payload("secret", payload)

    assert verify_callback_signature("secret", payload, signature) is True


def test_verify_callback_signature_rejects_tampered_payload() -> None:
    payload = dump_callback_payload({"assessment_id": "a1", "type": "run", "submissions": []})
    signature = sign_callback_payload("secret", payload)

    assert verify_callback_signature("secret", b'{"tampered":true}', signature) is False
