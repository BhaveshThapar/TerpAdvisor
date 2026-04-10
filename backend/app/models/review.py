import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, func, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False
    )
    professor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professors.id", ondelete="SET NULL"), nullable=True
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)

    course: Mapped["Course"] = relationship("Course", back_populates="reviews")
    professor: Mapped["Professor | None"] = relationship(
        "Professor", back_populates="reviews"
    )
