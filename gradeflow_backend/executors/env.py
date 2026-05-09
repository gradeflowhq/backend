from os import PathLike, fspath
from typing import Final

GRADEFLOW_ENV_PREFIX: Final = "GRADEFLOW_"

ASSESSMENT_ID_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}ASSESSMENT_ID"
JOB_ID_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}JOB_ID"
JOB_TYPE_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}JOB_TYPE"
CALLBACK_URL_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}CALLBACK_URL"
CALLBACK_SECRET_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}CALLBACK_SECRET"
ENGINE_BIN_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}ENGINE_BIN"
WORKDIR_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}WORKDIR"
SUBMISSIONS_PATH_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}SUBMISSIONS_PATH"
QSET_PATH_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}QSET_PATH"
RUBRIC_PATH_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}RUBRIC_PATH"
OUT_PATH_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}OUT_PATH"
TIMEOUT_S_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}TIMEOUT_S"
CALLBACK_TIMEOUT_S_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}CALLBACK_TIMEOUT_S"
POINT_COLUMNS_JSON_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}POINT_COLUMNS_JSON"
REMOVE_ADJUSTMENTS_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}REMOVE_ADJUSTMENTS"
OVERRIDE_RESULTS_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}OVERRIDE_RESULTS"
GRADE_QUESTIONS_WITHOUT_RULE_ENV: Final = f"{GRADEFLOW_ENV_PREFIX}GRADE_QUESTIONS_WITHOUT_RULE"


def build_gradeflow_env(
    *,
    assessment_id: str,
    job_id: str,
    job_type: str,
    callback_url: str,
    callback_secret: str,
    engine_bin: str,
    workdir: str | PathLike[str],
    submissions_path: str | PathLike[str],
    qset_path: str | PathLike[str],
    rubric_path: str | PathLike[str],
    out_path: str | PathLike[str],
    timeout_s: int,
    callback_timeout_s: int,
    point_columns_json: str = "{}",
    remove_adjustments: bool = False,
    override_results: bool = True,
    grade_questions_without_rule: bool = True,
) -> dict[str, str]:
    return {
        ASSESSMENT_ID_ENV: assessment_id,
        JOB_ID_ENV: job_id,
        JOB_TYPE_ENV: job_type,
        CALLBACK_URL_ENV: callback_url,
        CALLBACK_SECRET_ENV: callback_secret,
        ENGINE_BIN_ENV: engine_bin,
        WORKDIR_ENV: fspath(workdir),
        SUBMISSIONS_PATH_ENV: fspath(submissions_path),
        QSET_PATH_ENV: fspath(qset_path),
        RUBRIC_PATH_ENV: fspath(rubric_path),
        OUT_PATH_ENV: fspath(out_path),
        TIMEOUT_S_ENV: str(timeout_s),
        CALLBACK_TIMEOUT_S_ENV: str(callback_timeout_s),
        POINT_COLUMNS_JSON_ENV: point_columns_json,
        REMOVE_ADJUSTMENTS_ENV: str(remove_adjustments).lower(),
        OVERRIDE_RESULTS_ENV: str(override_results).lower(),
        GRADE_QUESTIONS_WITHOUT_RULE_ENV: str(grade_questions_without_rule).lower(),
    }
