from tests.helpers.api import ApiClient
from tests.helpers.data import QUESTION_SET_YAML, RUBRIC_YAML, SUBMISSIONS_CSV


def test_assessment_crud(api: ApiClient) -> None:
    created = api.create_assessment("Midterm", "Desc")
    assert created.id is not None

    lst = api.list_assessments()
    assert any(item.id == created.id for item in lst.items)

    got = api.get_assessment(created.id)
    assert got.id == created.id

    updated = api.update_assessment(created.id, name="Midterm 2")
    assert updated.name == "Midterm 2"

    api.delete_assessment(created.id)
    lst = api.list_assessments()
    assert not any(item.id == created.id for item in lst.items)


def test_assessment_metadata_crud(api: ApiClient) -> None:
    created = api.create_assessment("Metadata Test")

    empty = api.get_assessment_metadata(created.id)
    assert empty.metadata == {}

    publish_config = {
        "courseId": "123",
        "assignmentGroupId": "456",
        "assignmentId": "789",
        "gradeMode": "points",
        "includeQuestionRemarks": True,
        "rounding": {"enabled": True, "base": 0.5},
    }
    item = api.set_assessment_metadata_value(
        created.id,
        "canvas_publish_config",
        publish_config,
    )
    assert item.key == "canvas_publish_config"
    assert item.value == publish_config

    got_item = api.get_assessment_metadata_value(created.id, "canvas_publish_config")
    assert got_item.value == publish_config

    all_metadata = api.get_assessment_metadata(created.id)
    assert all_metadata.metadata == {"canvas_publish_config": publish_config}

    replaced = api.replace_assessment_metadata(created.id, {"reviewed": True})
    assert replaced.metadata == {"reviewed": True}

    api.delete_assessment_metadata_value(created.id, "reviewed")
    assert api.get_assessment_metadata(created.id).metadata == {}


def test_missing_assessment_metadata_key_returns_404(api: ApiClient) -> None:
    created = api.create_assessment("Missing Metadata")

    r = api.try_get_assessment_metadata_value(created.id, "missing")
    assert r.status_code == 404, r.text


def test_assessment_list_summary_no_data(api: ApiClient) -> None:
    api.create_assessment("Empty Assessment")
    lst = api.list_assessments()
    item = next(a for a in lst.items if a.name == "Empty Assessment")
    assert item.summary is not None
    assert item.summary.submission_count is None
    assert item.summary.question_count is None
    assert item.summary.graded_count == 0
    assert item.summary.coverage is None


def test_assessment_list_summary_with_data(api: ApiClient) -> None:
    created = api.create_assessment("Summary Test")
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)

    lst = api.list_assessments()
    item = next(a for a in lst.items if a.id == created.id)
    assert item.summary is not None
    assert item.summary.submission_count == 2
    assert item.summary.question_count == 4
    assert item.summary.coverage is not None
    assert item.summary.coverage.total == 4
    assert item.summary.coverage.covered == 4


def test_assessment_list_summary_graded_count(api: ApiClient) -> None:
    created = api.create_assessment("Graded Count Test")
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.run_grading(created.id)

    lst = api.list_assessments()
    item = next(a for a in lst.items if a.id == created.id)
    assert item.summary is not None
    assert item.summary.graded_count == 2


def test_assessment_get_non_member_forbidden(api: ApiClient) -> None:
    other = api.create_other_user("stranger@example.com")

    created = api.create_assessment("Private")
    r = other.try_get_assessment(created.id)
    assert r.status_code == 403, r.text


def test_assessment_update_non_owner_forbidden(api: ApiClient) -> None:
    other = api.create_other_user("editor2@example.com")

    created = api.create_assessment("Owner Only")
    api.add_member(created.id, user_email="editor2@example.com", role="editor")

    r = other.try_update_assessment(created.id, name="Hijacked")
    assert r.status_code == 403, r.text


def test_assessment_metadata_write_requires_editor(api: ApiClient) -> None:
    other = api.create_other_user("viewer-metadata@example.com")

    created = api.create_assessment("Metadata Permission")
    api.add_member(created.id, user_email="viewer-metadata@example.com", role="viewer")

    assert other.get_assessment_metadata(created.id).metadata == {}
    r = other.try_set_assessment_metadata_value(created.id, "canvas_publish_config", {})
    assert r.status_code == 403, r.text


def test_assessment_delete_non_owner_forbidden(api: ApiClient) -> None:
    other = api.create_other_user("viewer3@example.com")

    created = api.create_assessment("Owner Delete Only")
    api.add_member(created.id, user_email="viewer3@example.com", role="viewer")

    r = other.try_delete_assessment(created.id)
    assert r.status_code == 403, r.text
