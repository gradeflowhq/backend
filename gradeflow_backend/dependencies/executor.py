from functools import lru_cache

from gradeflow_backend.executors.base import GradingJobExecutor
from gradeflow_backend.executors.factory import create_executor_from_settings


@lru_cache(maxsize=1)
def get_executor() -> GradingJobExecutor:
    return create_executor_from_settings()
