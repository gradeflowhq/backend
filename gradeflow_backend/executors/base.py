from abc import ABC, abstractmethod

from gradeflow_backend.schemas.grading import GradingJobSpec, JobStatus


class GradingJobExecutor(ABC):
    """
    Backend-agnostic job executor interface.
    Implementations must:
    - Maintain at least two priority queues: preview (higher) and run
    - Enforce a time limit on each grading execution
    """

    @abstractmethod
    def submit(self, spec: GradingJobSpec, callback_url: str) -> str:
        """
        Enqueue the job for execution and return a job_id.
        Preview jobs should be prioritized over run jobs.
        """
        raise NotImplementedError

    @abstractmethod
    def get_status(self, job_id: str) -> JobStatus:
        """Return the status of the job: queued | running | completed | failed."""
        raise NotImplementedError

    @abstractmethod
    def start(self) -> None:
        """Start executor (optional)."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop executor gracefully (optional)."""
        pass
