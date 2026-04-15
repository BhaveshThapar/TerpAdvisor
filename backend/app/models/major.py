import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Major(Base):
    __tablename__ = "majors"
    __table_args__ = (
        UniqueConstraint("name", "catalog_year", "track", name="uq_majors_name_year_track"),
        Index("ix_majors_name", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    catalog_year: Mapped[str] = mapped_column(String(10), nullable=False)
    track: Mapped[str] = mapped_column(String(50), nullable=False, default="General")
    requirements: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
