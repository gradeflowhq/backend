from pathlib import Path

import pytest

from gradeflow_backend.executors.entrypoint import Config
from gradeflow_backend.executors.env import (
    ASSESSMENT_ID_ENV,
    CALLBACK_SECRET_ENV,
    CALLBACK_TIMEOUT_S_ENV,
    CALLBACK_URL_ENV,
    ENGINE_BIN_ENV,
    GRADE_QUESTIONS_WITHOUT_RULE_ENV,
    JOB_TYPE_ENV,
    OUT_PATH_ENV,
    OVERRIDE_RESULTS_ENV,
    POINT_COLUMNS_JSON_ENV,
    QSET_PATH_ENV,
    REMOVE_ADJUSTMENTS_ENV,
    RUBRIC_PATH_ENV,
    SUBMISSIONS_PATH_ENV,
    TIMEOUT_S_ENV,
    WORKDIR_ENV,
    build_gradeflow_env,
)


def test_build_gradeflow_env_stringifies_contract_values() -> None:
    env = build_gradeflow_env(
        assessment_id="a1",
        job_type="preview",
        callback_url="https://example.test/callback",
        callback_secret="secret-1",
        engine_bin="gradeflow-engine",
        workdir=Path("/tmp/work"),
        submissions_path=Path("/tmp/work/submissions.csv"),
        qset_path=Path("/tmp/work/question_set.yaml"),
        rubric_path=Path("/tmp/work/rubric.yaml"),
        out_path=Path("/tmp/work/graded.yaml"),
        timeout_s=12,
        callback_timeout_s=34,
        point_columns_json='{"Q1":"points"}',
        remove_adjustments=True,
        override_results=False,
        grade_questions_without_rule=False,
    )

    assert env == {
        ASSESSMENT_ID_ENV: "a1",
        JOB_TYPE_ENV: "preview",
        CALLBACK_URL_ENV: "https://example.test/callback",
        CALLBACK_SECRET_ENV: "secret-1",
        ENGINE_BIN_ENV: "gradeflow-engine",
        WORKDIR_ENV: "/tmp/work",
        SUBMISSIONS_PATH_ENV: "/tmp/work/submissions.csv",
        QSET_PATH_ENV: "/tmp/work/question_set.yaml",
        RUBRIC_PATH_ENV: "/tmp/work/rubric.yaml",
        OUT_PATH_ENV: "/tmp/work/graded.yaml",
        TIMEOUT_S_ENV: "12",
        CALLBACK_TIMEOUT_S_ENV: "34",
        POINT_COLUMNS_JSON_ENV: '{"Q1":"points"}',
        REMOVE_ADJUSTMENTS_ENV: "true",
        OVERRIDE_RESULTS_ENV: "false",
        GRADE_QUESTIONS_WITHOUT_RULE_ENV: "false",
    }


def test_entrypoint_config_reads_explicit_gradeflow_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = build_gradeflow_env(
        assessment_id="a2",
        job_type="run",
        callback_url="https://example.test/callback",
        callback_secret="secret-2",
        engine_bin="custom-engine",
        workdir="/workspace",
        submissions_path="/workspace/submissions.csv",
        qset_path="/workspace/question_set.yaml",
        rubric_path="/workspace/rubric.yaml",
        out_path="/workspace/graded.yaml",
        timeout_s=300,
        callback_timeout_s=10,
        point_columns_json='{"Q2":"Adjusted"}',
        remove_adjustments=False,
        override_results=True,
        grade_questions_without_rule=True,
    )

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    cfg = Config()  # type: ignore[call-arg]

    assert cfg.assessment_id == "a2"
    assert cfg.job_type == "run"
    assert cfg.callback_url == "https://example.test/callback"
    assert cfg.callback_secret == "secret-2"
    assert cfg.engine_bin == "custom-engine"
    assert cfg.workdir == Path("/workspace")
    assert cfg.point_columns_json == '{"Q2":"Adjusted"}'
    assert cfg.remove_adjustments is False
    assert cfg.override_results is True
    assert cfg.grade_questions_without_rule is True
    assert cfg.resolved_submissions() == Path("/workspace/submissions.csv")
    assert cfg.resolved_qset() == Path("/workspace/question_set.yaml")
    assert cfg.resolved_rubric() == Path("/workspace/rubric.yaml")
    assert cfg.resolved_out() == Path("/workspace/graded.yaml")
