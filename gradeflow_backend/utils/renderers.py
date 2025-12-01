from __future__ import annotations

import csv
from io import StringIO

import yaml
from natsort import natsorted

from gradeflow_backend.schemas.grading import GradingJobSpec
from gradeflow_backend.utils.engine import model_dump_minimal


def render_submissions_csv(spec: GradingJobSpec) -> str:
    """
    Deterministic CSV for RawSubmission list:
      - Columns: student_id + union of all question IDs (natsorted)
      - Rows: one per RawSubmission, missing answers serialized as empty string
    Mirrors logic used by in-memory executor to ensure consistent ordering.
    """
    qids: set[str] = set()
    for rs in spec.raw_submissions:
        qids.update(rs.raw_answer_map.keys())
    ordered_qids = natsorted(qids)

    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=["student_id", *ordered_qids])
    writer.writeheader()
    for rs in spec.raw_submissions:
        row = {"student_id": rs.student_id}
        for qid in ordered_qids:
            row[qid] = rs.raw_answer_map.get(qid, "")
        writer.writerow(row)
    return buf.getvalue()


def render_question_set_yaml(spec: GradingJobSpec) -> str:
    """
    YAML dump of QuestionSet using model_dump (no internal fields added).
    """
    return yaml.safe_dump(spec.question_set.model_dump(), sort_keys=False)


def render_rubric_yaml_minimal(spec: GradingJobSpec) -> str:
    """
    Minimal YAML dump of Rubric, stripping engine-internal fields via model_dump_minimal.
    Matches how RubricService/JobsService persist rubrics for engine consumption.
    """
    return yaml.safe_dump(model_dump_minimal(spec.rubric), sort_keys=False)
