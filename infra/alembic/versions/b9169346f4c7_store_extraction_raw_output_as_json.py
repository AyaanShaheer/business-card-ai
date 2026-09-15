"""store extraction raw output as json

Revision ID: b9169346f4c7
Revises: e596e0b85ab8
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9169346f4c7"
down_revision: Union[str, Sequence[str], None] = "e596e0b85ab8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.alter_column(
            "extractions",
            "raw_output",
            existing_type=sa.Text(),
            type_=sa.JSON(),
            existing_nullable=True,
            postgresql_using="raw_output::json",
        )
    else:
        with op.batch_alter_table("extractions") as batch_op:
            batch_op.alter_column(
                "raw_output",
                existing_type=sa.Text(),
                type_=sa.JSON(),
                existing_nullable=True,
            )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.alter_column(
            "extractions",
            "raw_output",
            existing_type=sa.JSON(),
            type_=sa.Text(),
            existing_nullable=True,
        )
    else:
        with op.batch_alter_table("extractions") as batch_op:
            batch_op.alter_column(
                "raw_output",
                existing_type=sa.JSON(),
                type_=sa.Text(),
                existing_nullable=True,
            )