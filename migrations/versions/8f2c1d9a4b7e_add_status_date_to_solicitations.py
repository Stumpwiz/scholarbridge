"""add status date to solicitations

Revision ID: 8f2c1d9a4b7e
Revises: 2d4b6f0c9a10
Create Date: 2026-07-18 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8f2c1d9a4b7e"
down_revision = "2d4b6f0c9a10"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "solicitations" in table_names:
        solicitation_columns = {column["name"] for column in inspector.get_columns("solicitations")}
        if "status_date" not in solicitation_columns:
            with op.batch_alter_table("solicitations", schema=None) as batch_op:
                batch_op.add_column(sa.Column("status_date", sa.Date(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "solicitations" in table_names:
        solicitation_columns = {column["name"] for column in inspector.get_columns("solicitations")}
        if "status_date" in solicitation_columns:
            with op.batch_alter_table("solicitations", schema=None) as batch_op:
                batch_op.drop_column("status_date")
