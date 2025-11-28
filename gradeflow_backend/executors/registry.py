from collections.abc import Callable

from gradeflow_backend.executors.base import GradingJobExecutor

# Internal map from executor name -> creator function
_EXECUTOR_CREATORS: dict[str, Callable[[], GradingJobExecutor]] = {}


def register(
    name: str,
) -> Callable[[Callable[[], GradingJobExecutor]], Callable[[], GradingJobExecutor]]:
    """
    Decorator to register an executor creator under a name.
    Usage:
        @register("SYNCHRONOUS")
        def create_executor() -> GradingJobExecutor: ...
    """
    name = name.upper()

    def _wrap(fn: Callable[[], GradingJobExecutor]) -> Callable[[], GradingJobExecutor]:
        if name in _EXECUTOR_CREATORS:
            raise KeyError(f"Executor '{name}' already registered")
        _EXECUTOR_CREATORS[name] = fn
        return fn

    return _wrap


def get_creator(name: str) -> Callable[[], GradingJobExecutor]:
    """
    Retrieve the registered creator by name (case-insensitive).
    """
    name = name.upper()
    try:
        return _EXECUTOR_CREATORS[name]
    except KeyError as e:
        available = ", ".join(sorted(_EXECUTOR_CREATORS.keys())) or "<none>"
        raise KeyError(f"Executor '{name}' not found. Available: {available}") from e


def available() -> list[str]:
    """List available registered executor names."""
    return sorted(_EXECUTOR_CREATORS.keys())
