from __future__ import annotations

import argparse
import os
from typing import Iterable

import sqlalchemy as sa
from sqlalchemy.engine import URL, Engine, make_url

from app.db_safety import require_data_mutation_opt_in

TABLE_COPY_ORDER: tuple[str, ...] = (
    "campaigns",
    "partners",
    "persons",
    "contacts",
    "users",
    "campaign_category_mrpoc",
    "solicitations",
)


def _load_url(url_text: str, label: str) -> URL:
    try:
        return make_url(url_text)
    except Exception as exc:  # pragma: no cover - defensive parsing guard
        raise SystemExit(f"Invalid {label}: {url_text!r}") from exc


def _assert_sqlite_source(url: URL) -> None:
    if not url.drivername.startswith("sqlite"):
        raise SystemExit(
            f"Source URL must be SQLite. Got driver {url.drivername!r}."
        )


def _assert_postgres_target(url: URL) -> None:
    if not url.drivername.startswith("postgresql"):
        raise SystemExit(
            f"Target URL must be PostgreSQL. Got driver {url.drivername!r}."
        )


def _reflect_tables(engine: Engine, table_names: Iterable[str]) -> sa.MetaData:
    metadata = sa.MetaData()
    metadata.reflect(bind=engine, only=list(table_names))
    return metadata


def _truncate_target_tables(connection: sa.Connection, table_names: list[str]) -> None:
    if not table_names:
        return
    quoted = ", ".join(f'"{table_name}"' for table_name in table_names)
    connection.execute(sa.text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))


def _copy_table_rows(
    source_connection: sa.Connection,
    target_connection: sa.Connection,
    source_table: sa.Table,
    target_table: sa.Table,
) -> int:
    rows = source_connection.execute(sa.select(source_table)).mappings().all()
    if not rows:
        return 0

    payload = [dict(row) for row in rows]
    target_connection.execute(sa.insert(target_table), payload)
    return len(payload)


def _copy_alembic_version(
    source_connection: sa.Connection,
    target_connection: sa.Connection,
    source_metadata: sa.MetaData,
    target_metadata: sa.MetaData,
) -> bool:
    source_table = source_metadata.tables.get("alembic_version")
    target_table = target_metadata.tables.get("alembic_version")
    if source_table is None or target_table is None:
        return False

    version_rows = source_connection.execute(sa.select(source_table)).mappings().all()
    if not version_rows:
        return False

    target_connection.execute(sa.delete(target_table))
    target_connection.execute(sa.insert(target_table), [dict(row) for row in version_rows])
    return True


def _sync_id_sequence(target_connection: sa.Connection, target_table: sa.Table) -> None:
    if "id" not in target_table.c:
        return
    id_column = target_table.c.id
    if not isinstance(id_column.type, sa.Integer):
        return

    sequence_name = target_connection.execute(
        sa.text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
        {"table_name": target_table.name},
    ).scalar_one_or_none()
    if not sequence_name:
        return

    max_id = target_connection.execute(
        sa.select(sa.func.max(target_table.c.id))
    ).scalar_one()
    if max_id is None:
        target_connection.execute(
            sa.text(f"SELECT setval('{sequence_name}', 1, false)")
        )
        return

    target_connection.execute(
        sa.text(f"SELECT setval('{sequence_name}', :max_id, true)"),
        {"max_id": int(max_id)},
    )


def migrate_sqlite_to_postgres(
    source_sqlite_url: str,
    target_postgres_url: str,
    truncate_target: bool,
    copy_alembic_version: bool,
) -> None:
    source_url = _load_url(source_sqlite_url, "source SQLite URL")
    target_url = _load_url(target_postgres_url, "target PostgreSQL URL")
    _assert_sqlite_source(source_url)
    _assert_postgres_target(target_url)

    source_engine = sa.create_engine(source_sqlite_url)
    target_engine = sa.create_engine(target_postgres_url)

    source_metadata = _reflect_tables(source_engine, [*TABLE_COPY_ORDER, "alembic_version"])
    target_metadata = _reflect_tables(target_engine, [*TABLE_COPY_ORDER, "alembic_version"])

    missing_source = [name for name in TABLE_COPY_ORDER if name not in source_metadata.tables]
    missing_target = [name for name in TABLE_COPY_ORDER if name not in target_metadata.tables]
    if missing_source:
        raise SystemExit(f"Missing source tables: {', '.join(missing_source)}")
    if missing_target:
        raise SystemExit(
            "Target schema is incomplete. Run migrations first. Missing tables: "
            + ", ".join(missing_target)
        )

    with source_engine.connect() as source_connection, target_engine.begin() as target_connection:
        existing_target_tables = [
            name for name in reversed(TABLE_COPY_ORDER) if name in target_metadata.tables
        ]
        if truncate_target:
            _truncate_target_tables(target_connection, existing_target_tables)

        for table_name in TABLE_COPY_ORDER:
            source_table = source_metadata.tables[table_name]
            target_table = target_metadata.tables[table_name]
            copied = _copy_table_rows(
                source_connection,
                target_connection,
                source_table,
                target_table,
            )
            print(f"{table_name}: copied {copied} row(s)")

        if copy_alembic_version:
            copied_revision = _copy_alembic_version(
                source_connection,
                target_connection,
                source_metadata,
                target_metadata,
            )
            if copied_revision:
                print("alembic_version: copied revision marker")
            else:
                print("alembic_version: skipped (not present)")

        for table_name in TABLE_COPY_ORDER:
            _sync_id_sequence(target_connection, target_metadata.tables[table_name])

    print("SQLite to PostgreSQL migration complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy ScholarBridge data from SQLite to PostgreSQL."
    )
    parser.add_argument(
        "--source-sqlite-url",
        default=os.getenv("SQLITE_DATABASE_URL", "sqlite:///instance/scholarbridge.db"),
        help="Source SQLite SQLAlchemy URL.",
    )
    parser.add_argument(
        "--target-postgres-url",
        default=os.getenv("DATABASE_URL", ""),
        help="Target PostgreSQL SQLAlchemy URL.",
    )
    parser.add_argument(
        "--truncate-target",
        action="store_true",
        help="Truncate target tables before copy (recommended for clean migration).",
    )
    parser.add_argument(
        "--skip-alembic-version",
        action="store_true",
        help="Skip copying alembic_version.",
    )
    parser.add_argument(
        "--allow-data-mutation",
        action="store_true",
        help="Explicitly allow data mutation for this operation.",
    )
    args = parser.parse_args()

    if not args.target_postgres_url:
        raise SystemExit(
            "Missing --target-postgres-url (or DATABASE_URL env var)."
        )

    require_data_mutation_opt_in(
        "migrate SQLite data to PostgreSQL",
        allow_flag=args.allow_data_mutation,
    )

    migrate_sqlite_to_postgres(
        source_sqlite_url=args.source_sqlite_url,
        target_postgres_url=args.target_postgres_url,
        truncate_target=args.truncate_target,
        copy_alembic_version=not args.skip_alembic_version,
    )


if __name__ == "__main__":
    main()
