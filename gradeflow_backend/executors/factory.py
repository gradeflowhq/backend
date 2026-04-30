from gradeflow_backend.config import get_settings
from gradeflow_backend.executors.base import GradingJobExecutor
from gradeflow_backend.executors.registry import available, get_creator


def create_executor_from_settings() -> GradingJobExecutor:
    s = get_settings().executor
    # Map to registry names
    executor_name = s.executor.upper()
    try:
        creator = get_creator(executor_name)
    except KeyError as e:
        raise ValueError(
            f"Unsupported JOB_EXECUTOR: {executor_name}. Available: {available()}"
        ) from e
    return creator()
