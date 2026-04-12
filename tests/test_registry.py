from tests.helpers.api import ApiClient


def test_registry_question_set_serializers(api: ApiClient) -> None:
    r = api.try_get_registry_serializers("question-sets")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)
    assert len(r.json()) > 0


def test_registry_rubric_serializers(api: ApiClient) -> None:
    r = api.try_get_registry_serializers("rubrics")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_registry_submissions_serializers(api: ApiClient) -> None:
    r = api.try_get_registry_serializers("submissions")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_registry_raw_submissions_adapters(api: ApiClient) -> None:
    r = api.try_get_registry_adapters("raw-submissions")
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    assert "csv" in data


def test_registry_question_set_adapters(api: ApiClient) -> None:
    r = api.try_get_registry_adapters("question-sets")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_registry_rubric_adapters(api: ApiClient) -> None:
    r = api.try_get_registry_adapters("rubrics")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)
