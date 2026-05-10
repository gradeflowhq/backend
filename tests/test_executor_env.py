import json
import subprocess
from pathlib import Path

import pytest

from gradeflow_backend.executors import entrypoint
from gradeflow_backend.executors.entrypoint import Config
from gradeflow_backend.executors.env import (
    ASSESSMENT_ID_ENV,
    CALLBACK_SECRET_ENV,
    CALLBACK_TIMEOUT_S_ENV,
    CALLBACK_URL_ENV,
    ENGINE_BIN_ENV,
    GRADE_QUESTIONS_WITHOUT_RULE_ENV,
    JOB_ID_ENV,
    JOB_TYPE_ENV,
    METADATA_JSON_ENV,
    OUT_PATH_ENV,
    OVERRIDE_RESULTS_ENV,
    POINT_COLUMNS_JSON_ENV,
    QSET_PATH_ENV,
    REMOVE_ADJUSTMENTS_ENV,
    RUBRIC_GRADING_PARALLEL_JOBS_ENV,
    RUBRIC_GRADING_PARALLEL_MODE_ENV,
    RUBRIC_PATH_ENV,
    SUBMISSIONS_PATH_ENV,
    TIMEOUT_S_ENV,
    WORKDIR_ENV,
    build_gradeflow_env,
)


def test_build_gradeflow_env_stringifies_contract_values() -> None:
    env = build_gradeflow_env(
        assessment_id="a1",
        job_id="job-a1-preview",
        job_type="preview",
        callback_url="https://example.test/callback",
        callback_secret="secret-1",
        engine_bin="gradeflow-engine",
        workdir=Path("/tmp/work"),
        submissions_path=Path("/tmp/work/submissions.csv"),
        qset_path=Path("/tmp/work/question_set.yaml"),
        rubric_path=Path("/tmp/work/rubric.yaml"),
        out_path=Path("/tmp/work/graded.json"),
        timeout_s=12,
        callback_timeout_s=34,
        point_columns_json='{"Q1":"points"}',
        metadata_json='{"answer_question_ids":["Q1"]}',
        remove_adjustments=True,
        override_results=False,
        grade_questions_without_rule=False,
        rubric_grading_parallel_jobs=4,
        rubric_grading_parallel_mode="threads",
    )

    assert env == {
        ASSESSMENT_ID_ENV: "a1",
        JOB_ID_ENV: "job-a1-preview",
        JOB_TYPE_ENV: "preview",
        CALLBACK_URL_ENV: "https://example.test/callback",
        CALLBACK_SECRET_ENV: "secret-1",
        ENGINE_BIN_ENV: "gradeflow-engine",
        WORKDIR_ENV: "/tmp/work",
        SUBMISSIONS_PATH_ENV: "/tmp/work/submissions.csv",
        QSET_PATH_ENV: "/tmp/work/question_set.yaml",
        RUBRIC_PATH_ENV: "/tmp/work/rubric.yaml",
        OUT_PATH_ENV: "/tmp/work/graded.json",
        TIMEOUT_S_ENV: "12",
        CALLBACK_TIMEOUT_S_ENV: "34",
        POINT_COLUMNS_JSON_ENV: '{"Q1":"points"}',
        METADATA_JSON_ENV: '{"answer_question_ids":["Q1"]}',
        REMOVE_ADJUSTMENTS_ENV: "true",
        OVERRIDE_RESULTS_ENV: "false",
        GRADE_QUESTIONS_WITHOUT_RULE_ENV: "false",
        RUBRIC_GRADING_PARALLEL_JOBS_ENV: "4",
        RUBRIC_GRADING_PARALLEL_MODE_ENV: "threads",
    }


def test_entrypoint_config_reads_explicit_gradeflow_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = build_gradeflow_env(
        assessment_id="a2",
        job_id="job-a2-run",
        job_type="run",
        callback_url="https://example.test/callback",
        callback_secret="secret-2",
        engine_bin="custom-engine",
        workdir="/workspace",
        submissions_path="/workspace/submissions.csv",
        qset_path="/workspace/question_set.yaml",
        rubric_path="/workspace/rubric.yaml",
        out_path="/workspace/graded.json",
        timeout_s=300,
        callback_timeout_s=10,
        point_columns_json='{"Q2":"Adjusted"}',
        metadata_json='{"source":"test"}',
        remove_adjustments=False,
        override_results=True,
        grade_questions_without_rule=True,
        rubric_grading_parallel_jobs=2,
        rubric_grading_parallel_mode="processes",
    )

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    cfg = Config()  # type: ignore[call-arg]

    assert cfg.assessment_id == "a2"
    assert cfg.job_id == "job-a2-run"
    assert cfg.job_type == "run"
    assert cfg.callback_url == "https://example.test/callback"
    assert cfg.callback_secret == "secret-2"
    assert cfg.engine_bin == "custom-engine"
    assert cfg.workdir == Path("/workspace")
    assert cfg.point_columns_json == '{"Q2":"Adjusted"}'
    assert cfg.metadata_json == '{"source":"test"}'
    assert cfg.remove_adjustments is False
    assert cfg.override_results is True
    assert cfg.grade_questions_without_rule is True
    assert cfg.rubric_grading_parallel_jobs == 2
    assert cfg.rubric_grading_parallel_mode == "processes"
    assert cfg.resolved_submissions() == Path("/workspace/submissions.csv")
    assert cfg.resolved_qset() == Path("/workspace/question_set.yaml")
    assert cfg.resolved_rubric() == Path("/workspace/rubric.yaml")
    assert cfg.resolved_out() == Path("/workspace/graded.json")


def test_entrypoint_run_engine_cli_forwards_rubric_grading_options(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_cmd: list[str] = []

    def fake_run(
        cmd: list[str],
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        captured_cmd.extend(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(entrypoint.subprocess, "run", fake_run)

    entrypoint._run_engine_cli(
        engine_bin="gradeflow-engine",
        submissions_csv=tmp_path / "submissions.csv",
        qset_yaml=tmp_path / "question_set.yaml",
        rubric_yaml=tmp_path / "rubric.yaml",
        out_json=tmp_path / "graded.json",
        timeout_s=30,
        rubric_grading_parallel_jobs=3,
        rubric_grading_parallel_mode="threads",
    )

    assert "--rubric-grading-parallel-jobs" in captured_cmd
    assert captured_cmd[captured_cmd.index("--rubric-grading-parallel-jobs") + 1] == "3"
    assert "--out-serializer" in captured_cmd
    assert captured_cmd[captured_cmd.index("--out-serializer") + 1] == "json"
    assert "--rubric-grading-parallel-mode" in captured_cmd
    assert captured_cmd[captured_cmd.index("--rubric-grading-parallel-mode") + 1] == "threads"


def test_entrypoint_main_reads_json_output_and_posts_callback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out_json = tmp_path / "graded.json"
    env = build_gradeflow_env(
        assessment_id="a3",
        job_id="job-a3-run",
        job_type="run",
        callback_url="https://example.test/callback",
        callback_secret="secret-3",
        engine_bin="gradeflow-engine",
        workdir=tmp_path,
        submissions_path=tmp_path / "submissions.csv",
        qset_path=tmp_path / "question_set.yaml",
        rubric_path=tmp_path / "rubric.yaml",
        out_path=out_json,
        timeout_s=300,
        callback_timeout_s=10,
        metadata_json='{"answer_question_ids":["q1"]}',
        rubric_grading_parallel_jobs=2,
        rubric_grading_parallel_mode="threads",
    )
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    def fake_run_engine_cli(
        *,
        out_json: Path,
        **_: object,
    ) -> None:
        out_json.write_text(
            json.dumps([{"student_id": "s1", "answer_map": {"q1": "yes"}, "result_map": {}}]),
            encoding="utf-8",
        )

    class Response:
        status_code = 204
        text = ""

    captured: dict[str, object] = {}

    def fake_post(
        url: str,
        *,
        content: bytes,
        timeout: int,
        headers: dict[str, str],
    ) -> Response:
        captured.update({"url": url, "content": content, "timeout": timeout, "headers": headers})
        return Response()

    monkeypatch.setattr(entrypoint, "_run_engine_cli", fake_run_engine_cli)
    monkeypatch.setattr(entrypoint.httpx, "post", fake_post)

    assert entrypoint.main() == 0

    content = captured["content"]
    assert isinstance(content, bytes)
    body = json.loads(content.decode("utf-8"))
    assert captured["url"] == "https://example.test/callback"
    assert body["job_id"] == "job-a3-run"
    assert body["submissions"][0]["student_id"] == "s1"
    assert body["metadata"] == {"answer_question_ids": ["q1"]}
