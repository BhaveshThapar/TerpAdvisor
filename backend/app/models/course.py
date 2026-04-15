from sqlalchemy import Integer, Float, String, JSON
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
