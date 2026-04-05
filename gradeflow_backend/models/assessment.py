from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .association import UserAssessment
    from .user import User


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    question_set_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    rubric_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_data: Mapped[str | None] = mapped_column(
        Text().with_variant(MEDIUMTEXT, "mysql", "mariadb"), nullable=True
    )
    source_student_id_column: Mapped[str | None] = mapped_column(Text, nullable=True)
    submissions_config_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    question_set_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rubric_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    results_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user_links: Mapped[list["UserAssessment"]] = relationship(
        "UserAssessment",
        back_populates="assessment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    users: AssociationProxy[list["User"]] = association_proxy("user_links", "user")
