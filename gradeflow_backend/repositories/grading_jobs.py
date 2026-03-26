from gradeflow_backend.models.grading_job import GradingJobRecord
from gradeflow_backend.schemas.grading import JobType

from .base import BaseRepository


class GradingJobRepository(BaseRepository):
    def create(self, assessment_id: str, type: JobType, job_id: str) -> GradingJobRecord:
        record = GradingJobRecord(job_id=job_id, assessment_id=assessment_id, type=type)
        self.session().add(record)
        self.session().flush()
        return record

    def get_job_id(self, assessment_id: str, type: JobType) -> str | None:
        record = (
            self.session()
            .query(GradingJobRecord)
            .filter_by(assessment_id=assessment_id, type=type)
            .order_by(GradingJobRecord.created_at.desc())
            .first()
        )
        return record.job_id if record else None
