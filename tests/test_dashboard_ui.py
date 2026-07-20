import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import User


class DashboardUiTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="sb_dashboard_ui_"))

        class TestConfig(Config):
            SECRET_KEY = "test-secret"
            TESTING = True
            DATABASE_URL = f"sqlite:///{self._tmp_dir / 'test.db'}"

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

            user = User(
                username="reader",
                email="reader@example.com",
                role=User.ROLE_READER,
                is_active=True,
            )
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            self.user_id = str(user.id)

        with self.client.session_transaction() as session:
            session["_user_id"] = self.user_id
            session["_fresh"] = True

    def test_dashboard_renders_reports_card(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Dashboard", html)
        self.assertIn("Program at a Glance", html)
        self.assertIn("Reports", html)
        self.assertIn("Generate and view campaign reports.", html)
        self.assertIn('class="stretched-link" href="/reports"', html)
        self.assertIn("Open Reports", html)
        self.assertNotIn('btn btn-outline-primary btn-sm mt-auto align-self-start" href="/reports"', html)


if __name__ == "__main__":
    unittest.main()
