import uuid
from datetime import time

from sqlalchemy import ForeignKey, Integer, String, Time, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Section(Base):
    __tablename__ = "sections"

    section_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    course_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False
    )
    professor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professors.id", ondelete="SET NULL"), nullable=True
    )
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    days: Mapped[str | None] = mapped_column(String(10), nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    total_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    open_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    waitlist: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    course: Mapped["Course"] = relationship("Course", back_populates="sections")
    professor: Mapped["Professor | None"] = relationship(
        "Professor", back_populates="sections"
    )
