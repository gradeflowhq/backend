from gradeflow_engine.questions.models import ChoiceQuestion

from tests.helpers.api import ApiClient
from tests.helpers.data import QUESTION_SET_YAML, SUBMISSIONS_CSV


def test_question_set_crud(api: ApiClient) -> None:
    created = api.create_assessment("Midterm")

    # Set via YAML (serializer-based upload)
    set_resp = api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    assert set_resp.question_set is not None

    # Get
    got = api.get_question_set(created.id)
    assert got.question_set is not None

    # Optional: parse submissions after importing sample CSV
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)
    parsed = api.parse_submissions(created.id)
    assert len(parsed.submissions) >= 1

    # Delete
    api.delete_question_set(created.id)

    # Getting now should 404
    resp = api.try_get_question_set(created.id)
    assert resp.status_code == 404, resp.text


def test_question_crud(api: ApiClient) -> None:
    created = api.create_assessment("Question CRUD")

    created_questions = api.create_question(
        created.id,
        "q1",
        {"type": "TEXT", "description": "Name?", "max_points": 1.0},
    )
    assert list(created_questions.question_set.question_map) == ["q1"]
    assert created_questions.question_set.question_map["q1"].type == "TEXT"

    api.create_question(
        created.id,
        "q2",
        {"type": "NUMERIC", "description": "Score?", "max_points": 2.0},
    )

    duplicate = api.try_create_question(
        created.id,
        "q2",
        {"type": "TEXT", "description": "Duplicate"},
    )
    assert duplicate.status_code == 400, duplicate.text
    assert duplicate.json()["code"] == "BAD_REQUEST"

    got = api.try_get_question(created.id, "q2")
    assert got.status_code == 200, got.text
    assert got.json()["type"] == "NUMERIC"

    updated = api.update_question(
        created.id,
        "q2",
        {"type": "NUMERIC", "description": "Adjusted score", "max_points": 3.0},
    )
    assert list(updated.question_set.question_map) == ["q1", "q2"]
    assert updated.question_set.question_map["q2"].max_points == 3.0
    assert updated.question_set.question_map["q2"].description == "Adjusted score"

    api.delete_question(created.id, "q1")
    remaining = api.get_question_set(created.id).question_set.question_map
    assert list(remaining) == ["q2"]

    missing = api.try_get_question(created.id, "q1")
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == "NOT_FOUND"


def test_question_set_import_examplify_adapter(api: ApiClient) -> None:
    created = api.create_assessment("QSet Import via Adapter")

    # Minimal Examplify-like CSV: one Choice question (Seq=1) with options A,B
    examplify_qset_csv = (
        "Seq,Type,Item Text,Original Answer,Adjusted Answer,ThrowOut\n"
        "1,Choice,Pick letters,A,B,FALSE\n"
    )

    resp = api.import_question_set(
        created.id,
        data=examplify_qset_csv,
        adapter={"name": "examplify"},
    )
    qset = resp.question_set

    # Basic assertions: question_map has Q-prefixed ID and a Choice question
    assert isinstance(qset.question_map, dict)
    assert "Q1" in qset.question_map
    q1 = qset.question_map["Q1"]
    assert getattr(q1, "type", None) == "CHOICE"


def test_question_set_status_clears_after_resave(api: ApiClient) -> None:
    created = api.create_assessment("Question Set Status Refresh")

    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    stale = api.get_question_set(created.id)
    assert stale.status.is_stale is True

    refreshed = api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    assert refreshed.status.is_stale is False


def test_acknowledge_question_set_staleness_requires_existing_question_set(
    api: ApiClient,
) -> None:
    created = api.create_assessment("Question Set Acknowledge Missing")

    failed = api.try_acknowledge_question_set_staleness(created.id)

    assert failed.status_code == 404, failed.text
    assert failed.json()["code"] == "NOT_FOUND"


def test_acknowledge_question_set_staleness_clears_stale_status(api: ApiClient) -> None:
    created = api.create_assessment("Question Set Acknowledge")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    stale = api.get_question_set(created.id)
    assert stale.status.is_stale is True

    refreshed = api.acknowledge_question_set_staleness(created.id)

    assert refreshed.status.is_stale is False
    assert refreshed.question_set.question_map == stale.question_set.question_map


def test_question_set_export(api: ApiClient) -> None:
    created = api.create_assessment("Question Set Export")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    exported = api.export_question_set(created.id)

    assert exported.extension == "yaml"
    assert exported.media_type
    assert exported.filename == "question-set-export-questions.yaml"
    assert b"question_map:" in exported.data


def test_question_set_status_reports_drift_and_sync_clears_it(api: ApiClient) -> None:
    created = api.create_assessment("Question Set Sync")
    api.set_question_set_yaml(
        created.id,
        """
question_map:
  q1:
    type: TEXT
    description: "Keep this prompt"
    max_points: 2.0
  q2:
    type: CHOICE
    max_points: 3.0
    options:
      - A
    allow_multiple: false
    config:
      delimiter: ","
      trim_whitespace: true
      normalize_case: false
  q3:
    type: TEXT
""",
    )
    api.set_submissions_csv(
        created.id,
        'student_id,q1,q2,q4\ns1,Alice,"A, B",10\ns2,Bob,C,12\n',
    )

    status = api.get_question_set_status(created.id)

    assert status.status.is_stale is True
    assert status.drift.has_drift is True
    assert status.drift.missing_question_ids == ["q4"]
    assert status.drift.extra_question_ids == ["q3"]
    assert len(status.drift.choice_option_drifts) == 1
    choice_drift = status.drift.choice_option_drifts[0]
    assert choice_drift.question_id == "q2"
    assert choice_drift.missing_options == ["B", "C"]

    synced = api.sync_question_set(created.id)

    question_map = synced.question_set.question_map
    assert list(question_map) == ["q1", "q2", "q4"]
    assert question_map["q1"].description == "Keep this prompt"
    assert question_map["q1"].max_points == 2.0

    q2 = question_map["q2"]
    assert isinstance(q2, ChoiceQuestion)
    assert q2.options == {"A", "B", "C"}
    assert q2.allow_multiple is False
    assert q2.max_points == 3.0
    assert synced.status.is_stale is False

    refreshed_status = api.get_question_set_status(created.id)
    assert refreshed_status.status.is_stale is False
    assert refreshed_status.drift.has_drift is False
