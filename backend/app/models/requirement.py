import enum
import uuid

from sqlalchemy import Enum, Integer, String, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RequirementType(str, enum.Enum):
    CORE = "CORE"
    ELECTIVE = "ELECTIVE"
    GENED = "GENED"


class DegreeRequirement(Base):
    __tablename__ = "degree_requirements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    major: Mapped[str] = mapped_column(String(100), nullable=False)
    requirement_group: Mapped[str] = mapped_column(String(100), nullable=False)
    requirement_type: Mapped[RequirementType] = mapped_column(
        Enum(RequirementType, name="requirement_type_enum"), nullable=False
    )
    course_options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    credits_needed: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
