import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Float, String, func, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Course(Base):
    __tablename__ = "courses"

    course_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(10), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    avg_gpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    gen_eds: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True
    )
    prerequisites_raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    reviews: Mapped[list["Review"]] = relationship(
        "Review", back_populates="course", cascade="all, delete-orphan"
    )
    sections: Mapped[list["Section"]] = relationship(
        "Section", back_populates="course", cascade="all, delete-orphan"
    )
    completed_by: Mapped[list["CompletedCourse"]] = relationship(
        "CompletedCourse", back_populates="course", cascade="all, delete-orphan"
    )


class CompletedCourse(Base):
    __tablename__ = "completed_courses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False
    )
    semester: Mapped[str | None] = mapped_column(String(20), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(5), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="completed_courses")
    course: Mapped["Course"] = relationship("Course", back_populates="completed_by")
