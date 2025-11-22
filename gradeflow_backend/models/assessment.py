from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text, func
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
    submissions_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    graded_submissions_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Association object links
    user_links: Mapped[list[UserAssessment]] = relationship(
        "UserAssessment",
        back_populates="assessment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Association proxy to users (collection proxy, not a mapped column)
    users: AssociationProxy[list[User]] = association_proxy("user_links", "user")
