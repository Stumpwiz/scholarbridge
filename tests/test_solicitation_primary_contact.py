import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Campaign, Contact, Partner, Solicitation, User


class SolicitationPrimaryContactTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="sb_sol_contact_"))

        class TestConfig(Config):
            SECRET_KEY = "test-secret"
            TESTING = True
            DATABASE_URL = f"sqlite:///{self._tmp_dir / 'test.db'}"
            GENERATED_LETTERS_DIR = str(self._tmp_dir / "generated_letters")

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

            user = User(
                username="editor",
                email="editor@example.com",
                role=User.ROLE_EDITOR,
                is_active=True,
            )
            user.set_password("password123")
            db.session.add(user)

            campaign = Campaign(
                campaign_year=2026,
                campaign_name="2026 Campaign",
                status="active",
            )
            db.session.add(campaign)
            db.session.flush()

            # Partner with a primary contact
            partner_with = Partner(
                partner_name="Alpha Corp",
                partner_type="Finance",
                address_1="1 Main St",
                city="Baltimore",
                state="MD",
                postal_code="21201",
            )
            # Partner without any contact
            partner_without = Partner(
                partner_name="Beta Corp",
                partner_type="Finance",
                address_1="2 Main St",
                city="Baltimore",
                state="MD",
                postal_code="21201",
            )
            db.session.add_all([partner_with, partner_without])
            db.session.flush()

            primary_contact = Contact(
                partner_id=partner_with.id,
                first_name="Jane",
                middle_initial="A",
                last_name="Doe",
                title="Dr.",
                email="jane@alpha.com",
                phone="4105550001",
                is_primary=True,
                is_active=True,
            )
            db.session.add(primary_contact)

            sol_with = Solicitation(
                partner_id=partner_with.id,
                campaign_id=campaign.id,
                status="not_contacted",
            )
            sol_without = Solicitation(
                partner_id=partner_without.id,
                campaign_id=campaign.id,
                status="not_contacted",
            )
            db.session.add_all([sol_with, sol_without])
            db.session.commit()

            self.user_id = str(user.id)
            self.partner_with_id = partner_with.id
            self.partner_without_id = partner_without.id
            self.primary_contact_id = primary_contact.id
            self.sol_with_id = sol_with.id
            self.sol_without_id = sol_without.id

        with self.client.session_transaction() as sess:
            sess["_user_id"] = self.user_id
            sess["_fresh"] = True

    # --- Detail page ---

    def test_detail_shows_primary_contact_fields(self):
        response = self.client.get(f"/solicitations/{self.sol_with_id}")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Primary Partner Contact", html)
        self.assertIn("Jane", html)
        self.assertIn("Doe", html)
        self.assertIn("Dr.", html)
        self.assertIn("jane@alpha.com", html)
        self.assertIn("4105550001", html)

    def test_detail_shows_warning_when_no_primary_contact(self):
        response = self.client.get(f"/solicitations/{self.sol_without_id}")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Primary Partner Contact", html)
        self.assertIn("No primary contact has been designated", html)

    # --- Edit page ---

    def test_edit_shows_contact_fields_when_primary_exists(self):
        response = self.client.get(f"/solicitations/{self.sol_with_id}/edit")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Primary Partner Contact", html)
        self.assertIn("Jane", html)
        self.assertIn("Doe", html)
        self.assertIn("jane@alpha.com", html)

    def test_edit_shows_warning_and_add_button_when_no_contact(self):
        response = self.client.get(f"/solicitations/{self.sol_without_id}/edit")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("No primary contact has been designated", html)
        self.assertIn("Add Primary Contact", html)
        self.assertIn(f"return_to_solicitation={self.sol_without_id}", html)

    # --- Edit POST updates contact ---

    def test_edit_post_updates_primary_contact(self):
        response = self.client.post(
            f"/solicitations/{self.sol_with_id}/edit",
            data={
                "campaign_id": "1",
                "partner_id": str(self.partner_with_id),
                "tranche": "1",
                "status": "not_contacted",
                "amount_pledged": "0.00",
                "first_name": "Janet",
                "middle_initial": "B",
                "last_name": "Smith",
                "title": "Ms.",
                "email": "janet@alpha.com",
                "phone": "4105559999",
            },
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            contact = db.session.get(Contact, self.primary_contact_id)
            self.assertEqual(contact.first_name, "Janet")
            self.assertEqual(contact.last_name, "Smith")
            self.assertEqual(contact.middle_initial, "B")
            self.assertEqual(contact.title, "Ms.")
            self.assertEqual(contact.email, "janet@alpha.com")
            self.assertEqual(contact.phone, "4105559999")
            # is_primary must remain unchanged
            self.assertTrue(contact.is_primary)

    def test_edit_post_does_not_create_duplicate_contact(self):
        self.client.post(
            f"/solicitations/{self.sol_with_id}/edit",
            data={
                "campaign_id": "1",
                "partner_id": str(self.partner_with_id),
                "tranche": "1",
                "status": "not_contacted",
                "amount_pledged": "0.00",
                "first_name": "Janet",
                "last_name": "Smith",
                "title": "Ms.",
                "email": "janet@alpha.com",
                "phone": "4105559999",
            },
        )
        with self.app.app_context():
            from sqlalchemy import select
            count = db.session.scalar(
                select(db.func.count(Contact.id)).where(Contact.partner_id == self.partner_with_id)
            )
            self.assertEqual(count, 1)

    # --- Add Primary Contact workflow ---

    def test_add_primary_contact_get_renders_form(self):
        response = self.client.get(
            f"/partners/{self.partner_without_id}/contacts/new"
            f"?return_to_solicitation={self.sol_without_id}"
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Add Contact", html)
        self.assertIn("Beta Corp", html)
        self.assertIn(f'value="{self.sol_without_id}"', html)

    def test_add_primary_contact_post_redirects_to_solicitation_edit(self):
        response = self.client.post(
            f"/partners/{self.partner_without_id}/contacts/new",
            data={
                "return_to_solicitation": str(self.sol_without_id),
                "first_name": "Bob",
                "last_name": "Jones",
                "title": "Mr.",
                "email": "bob@beta.com",
                "phone": "4105550002",
                "is_primary": "on",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            f"/solicitations/{self.sol_without_id}/edit",
            response.headers["Location"],
        )

    def test_add_primary_contact_post_creates_contact(self):
        self.client.post(
            f"/partners/{self.partner_without_id}/contacts/new",
            data={
                "return_to_solicitation": str(self.sol_without_id),
                "first_name": "Bob",
                "last_name": "Jones",
                "title": "Mr.",
                "email": "bob@beta.com",
                "phone": "4105550002",
                "is_primary": "on",
                "is_active": "on",
            },
        )
        with self.app.app_context():
            from sqlalchemy import select
            contact = db.session.scalar(
                select(Contact).where(Contact.partner_id == self.partner_without_id)
            )
            self.assertIsNotNone(contact)
            self.assertEqual(contact.first_name, "Bob")
            self.assertTrue(contact.is_primary)

    def test_partner_contact_create_without_return_still_works(self):
        """POST without return_to_solicitation redirects to partner detail as before."""
        response = self.client.post(
            f"/partners/{self.partner_without_id}/contacts/new",
            data={
                "first_name": "Carol",
                "last_name": "White",
                "title": "Mrs.",
                "email": "carol@beta.com",
                "phone": "4105550003",
                "is_primary": "on",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/partners/{self.partner_without_id}", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()
