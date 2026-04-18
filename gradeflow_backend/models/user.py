import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .assessment import Assessment
    from .association import UserAssessment
    from .user_identity import UserIdentity


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uuid.uuid4().hex)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Association object links
    assessment_links: Mapped[list["UserAssessment"]] = relationship(
        "UserAssessment",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Identity provider links (Zitadel, Auth0, etc.)
    identities: Mapped[list["UserIdentity"]] = relationship(
        "UserIdentity",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Association proxy to assessments (collection proxy, not a mapped column)
    assessments: AssociationProxy[list["Assessment"]] = association_proxy(
        "assessment_links", "assessment"
    )
