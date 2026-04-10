import uuid

from sqlalchemy import Float, Integer, String, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Professor(Base):
    __tablename__ = "professors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    avg_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    courses_taught: Mapped[list | None] = mapped_column(JSON, nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    reviews: Mapped[list["Review"]] = relationship(
        "Review", back_populates="professor"
    )
    sections: Mapped[list["Section"]] = relationship(
        "Section", back_populates="professor"
    )
