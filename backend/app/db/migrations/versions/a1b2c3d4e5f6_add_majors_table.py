"""add majors table, drop legacy degree_requirements

Revision ID: a1b2c3d4e5f6
Revises: c48e17cf7704
Create Date: 2026-04-14 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "c48e17cf7704"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("degree_requirements")
    op.execute("DROP TYPE IF EXISTS requirement_type_enum")

    op.create_table(
        "majors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=True),
        sa.Column("catalog_year", sa.String(length=10), nullable=False),
        sa.Column("track", sa.String(length=50), nullable=False, server_default="General"),
        sa.Column("requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "catalog_year", "track", name="uq_majors_name_year_track"),
    )
    op.create_index("ix_majors_name", "majors", ["name"])


def downgrade() -> None:
    op.drop_index("ix_majors_name", table_name="majors")
    op.drop_table("majors")

    requirement_type_enum = sa.Enum("CORE", "ELECTIVE", "GENED", name="requirement_type_enum")
    requirement_type_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "degree_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("major", sa.String(length=100), nullable=False),
        sa.Column("requirement_group", sa.String(length=100), nullable=False),
        sa.Column("requirement_type", requirement_type_enum, nullable=False),
        sa.Column("course_options", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("credits_needed", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
