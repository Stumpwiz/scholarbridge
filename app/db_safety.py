from __future__ import annotations

import os
from pathlib import Path

DATA_MUTATION_ENV_FLAG = "SCHOLARBRIDGE_ALLOW_DATA_MUTATION"


def _resolved_sqlite_path(db_uri: str, instance_path: str | None = None) -> Path | None:
    if db_uri.startswith("sqlite:////"):
        return Path(db_uri.removeprefix("sqlite:///"))

    if db_uri.startswith("sqlite:///"):
        relative_name = db_uri.removeprefix("sqlite:///")
        if relative_name.startswith("instance/"):
            relative_name = relative_name.removeprefix("instance/")
        if instance_path:
            return Path(instance_path) / relative_name
        return Path(relative_name)

    return None


def is_development_database_uri(db_uri: str, instance_path: str | None = None) -> bool:
    sqlite_path = _resolved_sqlite_path(db_uri, instance_path=instance_path)
    if sqlite_path is None:
        return False

    filename = sqlite_path.name.lower()
    return filename == "scholarbridge.db"


def assert_testing_uses_isolated_database(db_uri: str, instance_path: str) -> None:
    if is_development_database_uri(db_uri, instance_path=instance_path):
        raise RuntimeError(
            "Refusing to run in TESTING mode against the development database. "
            "Use an isolated temporary database URI for tests."
        )


def allow_data_mutation(allow_flag: bool = False) -> bool:
    if allow_flag:
        return True
    return os.getenv(DATA_MUTATION_ENV_FLAG) == "1"


def require_data_mutation_opt_in(action: str, allow_flag: bool = False) -> None:
    if allow_data_mutation(allow_flag=allow_flag):
        return
    raise SystemExit(
        f"Refusing to {action}. "
        f"Set {DATA_MUTATION_ENV_FLAG}=1 or pass the explicit allow flag."
    )
