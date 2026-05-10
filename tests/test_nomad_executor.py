from types import SimpleNamespace
from typing import Any

import yaml
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.rubrics.model import Rubric
from gradeflow_engine.submissions.models import RawSubmission

from gradeflow_backend.config import get_settings
from gradeflow_backend.executors.nomad import NomadJobExecutor, _build_nomad_job
from gradeflow_backend.schemas.grading import GradingJobSpec


def _make_spec() -> GradingJobSpec:
    qset = QuestionSet.model_validate(
        yaml.safe_load(
            """
question_map:
  q1:
    type: TEXT
    max_points: 1.0
"""
        )
    )
    rubric = Rubric.model_validate(
        yaml.safe_load(
            """
rules:
  - type: TEXT_MATCH
    question_id: q1
    answers: ["Alice"]
    max_points: 1.0
"""
        )
    )
    return GradingJobSpec(
        assessment_id="assessment-1",
        type="run",
        raw_submissions=[RawSubmission(student_id="s1", raw_answer_map={"q1": "Alice"})],
        question_set=qset,
        rubric=rubric,
    )


def test_build_nomad_job_uses_nomad_json_field_names() -> None:
    settings = get_settings().executor
    image = settings.container_image or "gradeflow-engine:latest"
    workdir = settings.container_workdir or "/workspace"
    job = _build_nomad_job(
        "job-1-run",
        _make_spec(),
        submissions_csv="student_id,q1\ns1,Alice\n",
        question_set_yaml="question_map: {}\n",
        rubric_yaml="rules: []\n",
        entrypoint_py="print('ok')\n",
        callback_url="https://example.test/jobs/callback/token",
        callback_secret="secret",
    )

    group = job["Job"]["TaskGroups"][0]
    task = group["Tasks"][0]

    assert group["Name"] == "gradeflow-group"
    assert group["Count"] == 1
    assert "name" not in group
    assert "count" not in group
    assert "tasks" not in group

    assert task["Name"] == "gradeflow"
    assert task["Driver"] == "docker"
    assert task["Config"] == {
        "image": image,
        "entrypoint": ["python", f"{workdir}/entrypoint.py"],
        "work_dir": workdir,
    }
    assert "name" not in task
    assert "driver" not in task
    assert "config" not in task
    assert "env" not in task
    assert "templates" not in task
    assert "resources" not in task
    assert "logs" not in task

    assert task["Resources"] == {"CPU": settings.nomad_cpu, "MemoryMB": settings.nomad_memory_mb}
    assert task["LogConfig"] == {"MaxFiles": 5, "MaxFileSizeMB": 10}

    assert task["RestartPolicy"] == {
        "Attempts": 0,
        "Interval": 30_000_000_000,
        "Delay": 1_000_000_000,
        "Mode": "fail",
    }
    assert "restart_policy" not in task
    assert group["ReschedulePolicy"] == {"Attempts": 0, "Unlimited": False}


def test_nomad_error_uses_latest_terminated_event() -> None:
    allocations: list[dict[str, Any]] = [
        {
            "ClientStatus": "failed",
            "TaskStates": {
                "gradeflow": {
                    "Events": [
                        {
                            "Type": "Terminated",
                            "DisplayMessage": 'Exit Code: 1, Exit Message: "first failure"',
                        },
                        {
                            "Type": "Restarting",
                            "DisplayMessage": "Task restarting in 15s",
                        },
                        {
                            "Type": "Terminated",
                            "DisplayMessage": 'Exit Code: 137, Exit Message: "OOM Killed"',
                        },
                        {
                            "Type": "Not Restarting",
                            "DisplayMessage": (
                                'Exceeded allowed attempts 3 in interval 24h0m0s and mode is "fail"'
                            ),
                        },
                    ],
                },
            },
        },
    ]

    class FakeJob:
        def get_allocations(self, job_id: str) -> list[dict[str, Any]]:
            return allocations

    executor = NomadJobExecutor.__new__(NomadJobExecutor)
    executor._nomad = SimpleNamespace(job=FakeJob())

    assert executor.get_error("job-1-run") == ('Exit Code: 137, Exit Message: "OOM Killed"')
