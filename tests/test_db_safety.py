import os
import unittest

from app.config import Config
from app.db_safety import (
    DATA_MUTATION_ENV_FLAG,
    assert_testing_uses_isolated_database,
    is_development_database_uri,
    require_data_mutation_opt_in,
)


class DbSafetyTests(unittest.TestCase):
    def test_config_subclass_database_url_is_respected(self):
        class TestConfig(Config):
            DATABASE_URL = "sqlite:///isolated-test.db"

        resolved = TestConfig.resolve_database_uri("/tmp/sb-instance")
        self.assertTrue(resolved.endswith("/tmp/sb-instance/isolated-test.db"))

    def test_detects_default_development_sqlite_uri(self):
        self.assertTrue(
            is_development_database_uri(
                "sqlite:///scholarbridge.db",
                instance_path="/tmp/sb-instance",
            )
        )

    def test_allows_non_dev_sqlite_uri_for_tests(self):
        self.assertFalse(
            is_development_database_uri(
                "sqlite:///unit-test.db",
                instance_path="/tmp/sb-instance",
            )
        )
        assert_testing_uses_isolated_database(
            "sqlite:///unit-test.db",
            instance_path="/tmp/sb-instance",
        )

    def test_testing_guard_rejects_development_db(self):
        with self.assertRaises(RuntimeError):
            assert_testing_uses_isolated_database(
                "sqlite:///scholarbridge.db",
                instance_path="/tmp/sb-instance",
            )

    def test_postgres_uri_is_not_treated_as_development_sqlite_db(self):
        self.assertFalse(
            is_development_database_uri(
                "postgresql+psycopg://sb:sb@localhost:5432/scholarbridge",
                instance_path="/tmp/sb-instance",
            )
        )

    def test_data_mutation_requires_opt_in(self):
        previous = os.environ.get(DATA_MUTATION_ENV_FLAG)
        try:
            os.environ.pop(DATA_MUTATION_ENV_FLAG, None)
            with self.assertRaises(SystemExit):
                require_data_mutation_opt_in("test mutation")
        finally:
            if previous is not None:
                os.environ[DATA_MUTATION_ENV_FLAG] = previous

    def test_data_mutation_env_flag_allows_operation(self):
        previous = os.environ.get(DATA_MUTATION_ENV_FLAG)
        try:
            os.environ[DATA_MUTATION_ENV_FLAG] = "1"
            require_data_mutation_opt_in("test mutation")
        finally:
            if previous is None:
                os.environ.pop(DATA_MUTATION_ENV_FLAG, None)
            else:
                os.environ[DATA_MUTATION_ENV_FLAG] = previous


if __name__ == "__main__":
    unittest.main()
