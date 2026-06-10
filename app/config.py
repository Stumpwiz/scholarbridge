import os
from pathlib import Path


class Config:
    APP_NAME = os.getenv("APP_NAME", "ScholarBridge")
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///scholarbridge.db")

    @staticmethod
    def is_sqlite_uri(db_url: str) -> bool:
        return db_url.startswith("sqlite:")

    @classmethod
    def resolve_database_uri(cls, instance_path: str) -> str:
        """Resolve relative SQLite URIs into the Flask instance directory."""
        db_url = cls.DATABASE_URL

        # Relative sqlite URL (e.g., sqlite:///scholarbridge.db)
        if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
            relative_name = db_url.removeprefix("sqlite:///")
            # Backward compatibility: tolerate legacy values like instance/scholarbridge.db
            if relative_name.startswith("instance/"):
                relative_name = relative_name.removeprefix("instance/")
            db_file = Path(instance_path) / relative_name
            db_file.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{db_file}"

        return db_url

    @classmethod
    def should_use_batch_migrations(cls, db_url: str) -> bool:
        return cls.is_sqlite_uri(db_url)
