from tests.helpers.api import ApiClient


def test_health(api: ApiClient) -> None:
    resp = api.try_get_health()
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
