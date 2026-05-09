from abc import ABC, abstractmethod

from gradeflow_backend.schemas.grading import GradingJobSpec, JobStatus

DEFAULT_JOB_ERROR_MESSAGE = "Job failed unexpectedly."


def format_job_error(error: Exception | str | None) -> str:
    raw_message = str(error).strip() if error is not None else ""
    return raw_message or DEFAULT_JOB_ERROR_MESSAGE


class GradingJobExecutor(ABC):
    """
    Backend-agnostic job executor interface.
    Implementations must:
    - Maintain at least two priority queues: preview (higher) and run
    - Enforce a time limit on each grading execution
    """

    @abstractmethod
    def submit(
        self,
        job_id: str,
        spec: GradingJobSpec,
        callback_url: str,
        callback_secret: str,
    ) -> None:
        """
        Enqueue the job for execution.
        Preview jobs should be prioritized over run jobs.
        """
        raise NotImplementedError

    @abstractmethod
    def get_status(self, job_id: str) -> JobStatus:
        """Return the status of the job: queued | running | completed | failed."""
        raise NotImplementedError

    def get_error(self, job_id: str) -> str | None:  # noqa: B027
        """Return the latest error for a failed job, if available."""
        return None

    def cancel(self, job_id: str) -> None:  # noqa: B027
        """Cancel a queued or running job.

        Raises ``JobNotFoundError`` if the job_id is unknown.
        Implementations should mark the job as failed/cancelled and stop execution
        if possible.  The default implementation is a no-op (suitable for
        executors that cannot cancel, e.g. synchronous).
        """

    @abstractmethod
    def start(self) -> None:
        """Start executor (optional)."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop executor gracefully (optional)."""
        pass
