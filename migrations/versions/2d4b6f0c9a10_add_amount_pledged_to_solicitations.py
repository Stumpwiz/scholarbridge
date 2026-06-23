"""add amount pledged to solicitations

Revision ID: 2d4b6f0c9a10
Revises: 47ccf6818c1b
Create Date: 2026-06-23 14:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2d4b6f0c9a10"
down_revision = "47ccf6818c1b"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "solicitations" in table_names:
        solicitation_columns = {column["name"] for column in inspector.get_columns("solicitations")}
        if "amount_pledged" not in solicitation_columns:
            with op.batch_alter_table("solicitations", schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "amount_pledged",
                        sa.Numeric(precision=12, scale=2),
                        nullable=False,
                        server_default="0",
                    )
                )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "solicitations" in table_names:
        solicitation_columns = {column["name"] for column in inspector.get_columns("solicitations")}
        if "amount_pledged" in solicitation_columns:
            with op.batch_alter_table("solicitations", schema=None) as batch_op:
                batch_op.drop_column("amount_pledged")
