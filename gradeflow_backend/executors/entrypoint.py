#!/usr/bin/env python3

import hashlib
import hmac
import json
import subprocess
import sys
from pathlib import Path

import httpx
from gradeflow_engine.rubrics.model import RubricGradingParallelMode
from gradeflow_engine.submissions.models import Submission
from pydantic import BaseModel, Field, JsonValue, TypeAdapter, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Environment variable names (duplicated from gradeflow_backend.executors.env
# because this file runs in a container without the backend package installed)
# ---------------------------------------------------------------------------
_PREFIX = "GRADEFLOW_"
ASSESSMENT_ID_ENV = f"{_PREFIX}ASSESSMENT_ID"
JOB_ID_ENV = f"{_PREFIX}JOB_ID"
JOB_TYPE_ENV = f"{_PREFIX}JOB_TYPE"
CALLBACK_URL_ENV = f"{_PREFIX}CALLBACK_URL"
CALLBACK_SECRET_ENV = f"{_PREFIX}CALLBACK_SECRET"
ENGINE_BIN_ENV = f"{_PREFIX}ENGINE_BIN"
WORKDIR_ENV = f"{_PREFIX}WORKDIR"
SUBMISSIONS_PATH_ENV = f"{_PREFIX}SUBMISSIONS_PATH"
QSET_PATH_ENV = f"{_PREFIX}QSET_PATH"
RUBRIC_PATH_ENV = f"{_PREFIX}RUBRIC_PATH"
OUT_PATH_ENV = f"{_PREFIX}OUT_PATH"
TIMEOUT_S_ENV = f"{_PREFIX}TIMEOUT_S"
CALLBACK_TIMEOUT_S_ENV = f"{_PREFIX}CALLBACK_TIMEOUT_S"
POINT_COLUMNS_JSON_ENV = f"{_PREFIX}POINT_COLUMNS_JSON"
METADATA_JSON_ENV = f"{_PREFIX}METADATA_JSON"
REMOVE_ADJUSTMENTS_ENV = f"{_PREFIX}REMOVE_ADJUSTMENTS"
OVERRIDE_RESULTS_ENV = f"{_PREFIX}OVERRIDE_RESULTS"
GRADE_QUESTIONS_WITHOUT_RULE_ENV = f"{_PREFIX}GRADE_QUESTIONS_WITHOUT_RULE"
RUBRIC_GRADING_PARALLEL_JOBS_ENV = f"{_PREFIX}RUBRIC_GRADING_PARALLEL_JOBS"
RUBRIC_GRADING_PARALLEL_MODE_ENV = f"{_PREFIX}RUBRIC_GRADING_PARALLEL_MODE"

CALLBACK_SIGNATURE_HEADER = "X-GradeFlow-Signature"
_METADATA_ADAPTER = TypeAdapter(dict[str, JsonValue])


# ---------------------------------------------------------------------------
# Callback signing (duplicated from gradeflow_backend.utils.callback_signing)
# ---------------------------------------------------------------------------
def _dump_callback_payload(payload: BaseModel) -> bytes:
    data = payload.model_dump(mode="json")
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def _sign_callback_payload(secret: str, payload: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
class Config(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False)

    assessment_id: str = Field(..., validation_alias=ASSESSMENT_ID_ENV)
    job_id: str = Field(..., validation_alias=JOB_ID_ENV)
    job_type: str = Field(..., validation_alias=JOB_TYPE_ENV)
    callback_url: str = Field(..., validation_alias=CALLBACK_URL_ENV)
    callback_secret: str = Field(..., validation_alias=CALLBACK_SECRET_ENV)

    engine_bin: str = Field(default="gradeflow-engine", validation_alias=ENGINE_BIN_ENV)
    workdir: Path = Field(default=Path("/workspace"), validation_alias=WORKDIR_ENV)

    submissions_path: Path | None = Field(default=None, validation_alias=SUBMISSIONS_PATH_ENV)
    qset_path: Path | None = Field(default=None, validation_alias=QSET_PATH_ENV)
    rubric_path: Path | None = Field(default=None, validation_alias=RUBRIC_PATH_ENV)
    out_path: Path | None = Field(default=None, validation_alias=OUT_PATH_ENV)

    timeout_s: int = Field(default=300, ge=1, validation_alias=TIMEOUT_S_ENV)
    callback_timeout_s: int = Field(default=10, validation_alias=CALLBACK_TIMEOUT_S_ENV)
    point_columns_json: str = Field(default="{}", validation_alias=POINT_COLUMNS_JSON_ENV)
    metadata_json: str = Field(default="{}", validation_alias=METADATA_JSON_ENV)

    remove_adjustments: bool = Field(default=False, validation_alias=REMOVE_ADJUSTMENTS_ENV)
    override_results: bool = Field(default=True, validation_alias=OVERRIDE_RESULTS_ENV)
    grade_questions_without_rule: bool = Field(
        default=True, validation_alias=GRADE_QUESTIONS_WITHOUT_RULE_ENV
    )
    rubric_grading_parallel_jobs: int = Field(
        default=1, validation_alias=RUBRIC_GRADING_PARALLEL_JOBS_ENV
    )
    rubric_grading_parallel_mode: RubricGradingParallelMode = Field(
        default="processes", validation_alias=RUBRIC_GRADING_PARALLEL_MODE_ENV
    )

    def resolved_submissions(self) -> Path:
        return self.submissions_path or (self.workdir / "submissions.csv")

    def resolved_qset(self) -> Path:
        return self.qset_path or (self.workdir / "question_set.yaml")

    def resolved_rubric(self) -> Path:
        return self.rubric_path or (self.workdir / "rubric.yaml")

    def resolved_out(self) -> Path:
        return self.out_path or (self.workdir / "graded.json")


class Payload(BaseModel):
    job_id: str
    assessment_id: str
    type: str
    submissions: list[Submission]
    remove_adjustments: bool = False
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


def _run_engine_cli(
    engine_bin: str,
    submissions_csv: Path,
    qset_yaml: Path,
    rubric_yaml: Path,
    out_json: Path,
    timeout_s: int,
    point_columns: dict[str, str] | None = None,
    override_results: bool = True,
    grade_questions_without_rule: bool = True,
    rubric_grading_parallel_jobs: int = 1,
    rubric_grading_parallel_mode: RubricGradingParallelMode = "processes",
) -> None:
    cmd = [
        engine_bin,
        "grade",
        "--submissions",
        str(submissions_csv),
        "--raw-submissions-adapter",
        "csv",
        "--question-set",
        str(qset_yaml),
        "--question-set-serializer",
        "yaml",
        "--rubric",
        str(rubric_yaml),
        "--rubric-serializer",
        "yaml",
        "--out-serializer",
        "json",
        "--out",
        str(out_json),
        "--rubric-override-results" if override_results else "--no-rubric-override-results",
        "--rubric-grade-questions-without-rule"
        if grade_questions_without_rule
        else "--no-rubric-grade-questions-without-rule",
    ]
    for qid, col in (point_columns or {}).items():
        cmd += ["--point-column", f"{qid}={col}"]
    if rubric_grading_parallel_jobs != 1:
        cmd += ["--rubric-grading-parallel-jobs", str(rubric_grading_parallel_jobs)]
    cmd += ["--rubric-grading-parallel-mode", rubric_grading_parallel_mode]
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    if completed.returncode != 0:
        sys.stderr.write(
            f"[entrypoint] gradeflow-engine CLI failed (exit {completed.returncode})\n"
        )
        sys.stderr.write(f"[stdout]\n{completed.stdout}\n[stderr]\n{completed.stderr}\n")
        raise SystemExit(1)


def _load_metadata(raw: str) -> dict[str, JsonValue]:
    return _METADATA_ADAPTER.validate_json(raw)


def main() -> int:
    try:
        cfg = Config()  # type: ignore[call-arg]
    except ValidationError as e:
        sys.stderr.write("[entrypoint] Invalid environment configuration:\n")
        for err in e.errors():
            loc = ".".join(str(p) for p in err.get("loc", []))
            msg = err.get("msg", "invalid")
            sys.stderr.write(f"  - {loc}: {msg}\n")
        return 2

    submissions_csv = cfg.resolved_submissions()
    qset_yaml = cfg.resolved_qset()
    rubric_yaml = cfg.resolved_rubric()
    out_json = cfg.resolved_out()

    _run_engine_cli(
        engine_bin=cfg.engine_bin,
        submissions_csv=submissions_csv,
        qset_yaml=qset_yaml,
        rubric_yaml=rubric_yaml,
        out_json=out_json,
        timeout_s=cfg.timeout_s,
        point_columns=json.loads(cfg.point_columns_json),
        override_results=cfg.override_results,
        grade_questions_without_rule=cfg.grade_questions_without_rule,
        rubric_grading_parallel_jobs=cfg.rubric_grading_parallel_jobs,
        rubric_grading_parallel_mode=cfg.rubric_grading_parallel_mode,
    )

    try:
        raw_items = json.loads(out_json.read_text(encoding="utf-8"))
        if raw_items is None:
            raw_items = []
        if not isinstance(raw_items, list):
            raise TypeError("graded output must be a list")
        items = [Submission.model_validate(item) for item in raw_items]
    except Exception as e:
        sys.stderr.write(f"[entrypoint] Failed to read graded output: {e}\n")
        return 1

    payload = Payload(
        job_id=cfg.job_id,
        assessment_id=cfg.assessment_id,
        type=cfg.job_type,
        submissions=items,
        remove_adjustments=cfg.remove_adjustments,
        metadata=_load_metadata(cfg.metadata_json),
    )

    payload_bytes = _dump_callback_payload(payload)

    try:
        resp = httpx.post(
            cfg.callback_url,
            content=payload_bytes,
            timeout=cfg.callback_timeout_s,
            headers={
                "Content-Type": "application/json",
                CALLBACK_SIGNATURE_HEADER: _sign_callback_payload(
                    cfg.callback_secret, payload_bytes
                ),
            },
        )
    except Exception as e:
        sys.stderr.write(f"[entrypoint] Callback POST failed: {e}\n")
        return 3

    if resp.status_code >= 400:
        sys.stderr.write(f"[entrypoint] Callback error: {resp.status_code} {resp.text[:1000]}\n")
        return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
