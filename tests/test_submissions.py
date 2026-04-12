from gradeflow_backend.schemas.auth import TokenPairResponse
from tests.helpers.api import ApiClient
from tests.helpers.data import QUESTION_SET_YAML, SUBMISSIONS_CSV


def test_submissions_crud(api: ApiClient) -> None:
    created = api.create_assessment("Midterm")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    subs = api.set_submissions_csv(created.id, SUBMISSIONS_CSV)
    assert len(subs.raw_submissions) >= 1

    got = api.get_submissions(created.id)
    assert len(got.raw_submissions) == len(subs.raw_submissions)

    api.delete_submissions(created.id)

    empty = api.get_submissions(created.id)
    assert empty.raw_submissions == []


def test_get_source_data_not_found(api: ApiClient) -> None:
    created = api.create_assessment("No Source")
    r = api.try_get_source_data(created.id)
    assert r.status_code == 404, r.text


def test_get_source_data_success(api: ApiClient) -> None:
    created = api.create_assessment("With Source")
    api.try_upload_source_data(created.id, SUBMISSIONS_CSV)
    r = api.try_get_source_data(created.id)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["student_id_column"] == "student_id"
    assert body["total_rows"] == 2
    assert "student_id" in body["headers"]


def test_save_and_get_import_config(api: ApiClient) -> None:
    created = api.create_assessment("Config Test")
    api.try_upload_source_data(created.id, SUBMISSIONS_CSV)

    config_payload: dict[str, object] = {"answer_columns": ["q1", "q2"]}
    r_save = api.try_save_submission_config(created.id, config_payload)
    assert r_save.status_code == 200, r_save.text
    assert r_save.json()["answer_columns"] == ["q1", "q2"]

    r_get = api.try_get_submission_config(created.id)
    assert r_get.status_code == 200, r_get.text
    assert r_get.json()["answer_columns"] == ["q1", "q2"]


def test_import_config_empty_by_default(api: ApiClient) -> None:
    created = api.create_assessment("Empty Config")
    r = api.try_get_submission_config(created.id)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("answer_columns") is None
    assert body.get("point_columns") is None


def test_submissions_answer_columns_filter(api: ApiClient) -> None:
    """Only the columns listed in answer_columns are included in raw_submissions."""
    created = api.create_assessment("Filtered Columns")
    api.try_upload_source_data(created.id, SUBMISSIONS_CSV)
    # Restrict to q1 only
    api.try_save_submission_config(created.id, {"answer_columns": ["q1"]})
    subs = api.get_submissions(created.id)
    for rs in subs.raw_submissions:
        assert "q1" in rs.raw_answer_map
        assert "q2" not in rs.raw_answer_map


def test_upload_source_data_non_editor_forbidden(api: ApiClient) -> None:
    other = ApiClient(api.client)
    tokens: TokenPairResponse = other.signup("viewer_sub@example.com", "Strong-Pass-12345!")
    other.set_access_token(tokens.access_token)

    created = api.create_assessment("Editor Guard")
    api.add_member(created.id, user_email="viewer_sub@example.com", role="viewer")

    r = other.try_upload_source_data(created.id, SUBMISSIONS_CSV)
    assert r.status_code == 403, r.text
