#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import httpx
import yaml
from gradeflow_engine.submissions.models import Submission
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GF_",
        case_sensitive=False,
    )

    # Required identity/callback
    assessment_id: str = Field(..., description="Assessment ID")
    job_type: str = Field(..., description="Job type: run | preview")
    callback_url: str = Field(..., description="Callback URL to POST results")

    # Execution
    engine_bin: str = Field(default="gradeflow-engine", description="Engine CLI binary")
    workdir: Path = Field(default=Path("/workspace"), description="Working directory")

    # Paths (optional; resolved against workdir if missing)
    submissions_path: Path | None = Field(default=None, description="Path to submissions.csv")
    qset_path: Path | None = Field(default=None, description="Path to question_set.yaml")
    rubric_path: Path | None = Field(default=None, description="Path to rubric.yaml")
    out_path: Path | None = Field(default=None, description="Path to graded.yaml")

    # Timeouts
    timeout_s: int = Field(default=300, ge=1, description="Engine CLI timeout (seconds)")
    callback_timeout_s: int = Field(default=10, description="Callback POST timeout (seconds)")
    point_columns_json: str = Field(
        default="{}", description="JSON-encoded {qid: col} passthrough point column mapping"
    )

    def resolved_submissions(self) -> Path:
        return self.submissions_path or (self.workdir / "submissions.csv")

    def resolved_qset(self) -> Path:
        return self.qset_path or (self.workdir / "question_set.yaml")

    def resolved_rubric(self) -> Path:
        return self.rubric_path or (self.workdir / "rubric.yaml")

    def resolved_out(self) -> Path:
        return self.out_path or (self.workdir / "graded.yaml")


class Payload(BaseModel):
    assessment_id: str
    type: str
    submissions: list[Submission]


def _run_engine_cli(
    engine_bin: str,
    submissions_csv: Path,
    qset_yaml: Path,
    rubric_yaml: Path,
    out_yaml: Path,
    timeout_s: int,
    point_columns: dict[str, str] | None = None,
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
        "yaml",
        "--out",
        str(out_yaml),
    ]
    for qid, col in (point_columns or {}).items():
        cmd += ["--point-column", f"{qid}={col}"]
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
    out_yaml = cfg.resolved_out()

    _run_engine_cli(
        engine_bin=cfg.engine_bin,
        submissions_csv=submissions_csv,
        qset_yaml=qset_yaml,
        rubric_yaml=rubric_yaml,
        out_yaml=out_yaml,
        timeout_s=cfg.timeout_s,
        point_columns=json.loads(cfg.point_columns_json),
    )

    try:
        items: list[Submission] = yaml.safe_load(out_yaml.read_text(encoding="utf-8"))
    except Exception as e:
        sys.stderr.write(f"[entrypoint] Failed to read graded output: {e}\n")
        return 1

    payload = Payload(
        assessment_id=cfg.assessment_id,
        type=cfg.job_type,
        submissions=items,
    )

    try:
        resp = httpx.post(
            cfg.callback_url, json=payload.model_dump(mode="json"), timeout=cfg.callback_timeout_s
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
