from datetime import datetime

from pydantic import BaseModel


class SectionStatus(BaseModel):
    updated_at: datetime | None = None
    is_stale: bool = False
