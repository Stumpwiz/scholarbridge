"""legacy sqlite column compatibility

Revision ID: 47ccf6818c1b
Revises: f96fd0b1ba49
Create Date: 2026-06-10 13:31:19.238104

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '47ccf6818c1b'
down_revision = 'f96fd0b1ba49'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "users" in table_names:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        with op.batch_alter_table("users", schema=None) as batch_op:
            if "role" not in user_columns:
                batch_op.add_column(
                    sa.Column(
                        "role",
                        sa.String(length=20),
                        nullable=False,
                        server_default="reader",
                    )
                )
            if "avatar_path" not in user_columns:
                batch_op.add_column(sa.Column("avatar_path", sa.String(length=255), nullable=True))
            if "password_changed_at" not in user_columns:
                batch_op.add_column(sa.Column("password_changed_at", sa.DateTime(), nullable=True))

    if "contacts" in table_names:
        contact_columns = {column["name"] for column in inspector.get_columns("contacts")}
        if "middle_initial" not in contact_columns:
            with op.batch_alter_table("contacts", schema=None) as batch_op:
                batch_op.add_column(sa.Column("middle_initial", sa.String(length=1), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "users" in table_names:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        with op.batch_alter_table("users", schema=None) as batch_op:
            if "password_changed_at" in user_columns:
                batch_op.drop_column("password_changed_at")
            if "avatar_path" in user_columns:
                batch_op.drop_column("avatar_path")
            if "role" in user_columns:
                batch_op.drop_column("role")

    if "contacts" in table_names:
        contact_columns = {column["name"] for column in inspector.get_columns("contacts")}
        if "middle_initial" in contact_columns:
            with op.batch_alter_table("contacts", schema=None) as batch_op:
                batch_op.drop_column("middle_initial")
