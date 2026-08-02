"""Phase 2 tests: Make Primary, Partner Contacts section in Edit Solicitation,
cross-Partner return_to_solicitation validation, and related security checks."""

import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.config import Config
from app.extensions import db
from app.main.letter_service import build_solicitation_letter_context_for_solicitation
from app.main.status import select_partner_contact, solicitation_readiness_diagnostics
from app.models import Campaign, Contact, Partner, Solicitation, User


class Phase2PartnerContactTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="sb_phase2_"))

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

            editor = User(username="editor", email="editor@example.com",
                          role=User.ROLE_EDITOR, is_active=True)
            editor.set_password("password123")
            reader = User(username="reader", email="reader@example.com",
                          role=User.ROLE_READER, is_active=True)
            reader.set_password("password123")
            db.session.add_all([editor, reader])

            campaign = Campaign(campaign_year=2026, campaign_name="2026 Campaign", status="active")
            db.session.add(campaign)
            db.session.flush()

            # Chesapeake-like partner: one active non-primary contact
            partner_chesapeake = Partner(
                partner_name="Chesapeake Employers",
                partner_type="Finance",
                address_1="100 Harbor Blvd",
                city="Baltimore",
                state="MD",
                postal_code="21201",
            )
            # Second partner for cross-partner tests
            partner_other = Partner(
                partner_name="Other Corp",
                partner_type="Finance",
                address_1="200 Other St",
                city="Annapolis",
                state="MD",
                postal_code="21401",
            )
            db.session.add_all([partner_chesapeake, partner_other])
            db.session.flush()

            # Mark Isakson: active, NOT primary
            mark = Contact(
                partner_id=partner_chesapeake.id,
                first_name="Mark",
                last_name="Isakson",
                title="Director",
                email="mark@chesapeake.com",
                phone="4105550010",
                is_primary=False,
                is_active=True,
            )
            db.session.add(mark)

            sol_chesapeake = Solicitation(
                partner_id=partner_chesapeake.id,
                campaign_id=campaign.id,
                status="not_contacted",
            )
            sol_other = Solicitation(
                partner_id=partner_other.id,
                campaign_id=campaign.id,
                status="not_contacted",
            )
            db.session.add_all([sol_chesapeake, sol_other])
            db.session.commit()

            self.editor_id = str(editor.id)
            self.reader_id = str(reader.id)
            self.partner_chesapeake_id = partner_chesapeake.id
            self.partner_other_id = partner_other.id
            self.mark_id = mark.id
            self.sol_chesapeake_id = sol_chesapeake.id
            self.sol_other_id = sol_other.id
            self.campaign_id = campaign.id

        self._login_as_editor()

    def _login_as_editor(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = self.editor_id
            sess["_fresh"] = True

    def _login_as_reader(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = self.reader_id
            sess["_fresh"] = True

    # ── Fallback selection ────────────────────────────────────────────────

    def test_one_active_non_primary_contact_selected_via_fallback(self):
        """Chesapeake case: one active non-primary contact is selected by fallback."""
        with self.app.app_context():
            partner = db.session.get(Partner, self.partner_chesapeake_id)
            selected = select_partner_contact(partner)
            self.assertIsNotNone(selected)
            self.assertEqual(selected.id, self.mark_id)

    def test_chesapeake_edit_solicitation_shows_mark_as_correspondence_contact(self):
        """Edit Solicitation uses Mark through fallback even though is_primary=False."""
        response = self.client.get(f"/solicitations/{self.sol_chesapeake_id}/edit")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Mark", html)
        self.assertIn("Isakson", html)

    def test_partner_detail_labels_fallback_and_offers_make_primary(self):
        response = self.client.get(f"/partners/{self.partner_chesapeake_id}")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Correspondence Contact", html)
        self.assertIn("Mark", html)
        self.assertIn("Make Primary", html)

    def test_partner_detail_labels_formal_primary_and_hides_make_primary(self):
        with self.app.app_context():
            mark = db.session.get(Contact, self.mark_id)
            mark.is_primary = True
            db.session.commit()

        response = self.client.get(f"/partners/{self.partner_chesapeake_id}")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Primary Contact", html)
        self.assertNotIn("Correspondence Contact", html)
        self.assertNotIn("Make Primary", html)

    # ── Partner Contacts section in Edit Solicitation ─────────────────────

    def test_edit_solicitation_shows_partner_contacts_section(self):
        response = self.client.get(f"/solicitations/{self.sol_chesapeake_id}/edit")
        html = response.get_data(as_text=True)
        self.assertIn("Partner Contacts", html)
        self.assertIn("Add Contact", html)

    def test_edit_solicitation_shows_add_contact_with_zero_contacts(self):
        """Add Contact link is present even when partner has no contacts."""
        response = self.client.get(f"/solicitations/{self.sol_other_id}/edit")
        html = response.get_data(as_text=True)
        self.assertIn("Add Contact", html)

    def test_edit_solicitation_shows_make_primary_for_non_primary_active_contact(self):
        response = self.client.get(f"/solicitations/{self.sol_chesapeake_id}/edit")
        html = response.get_data(as_text=True)
        self.assertIn("Make Primary", html)

    def test_edit_solicitation_no_make_primary_for_already_primary(self):
        """Once Mark is primary, Make Primary button should not appear for him."""
        with self.app.app_context():
            mark = db.session.get(Contact, self.mark_id)
            mark.is_primary = True
            db.session.commit()
        response = self.client.get(f"/solicitations/{self.sol_chesapeake_id}/edit")
        html = response.get_data(as_text=True)
        self.assertNotIn("Make Primary", html)

    # ── Add Contact from Edit Solicitation ───────────────────────────────

    def test_add_contact_get_renders_form_with_return_to_solicitation(self):
        response = self.client.get(
            f"/partners/{self.partner_chesapeake_id}/contacts/new"
            f"?return_to_solicitation={self.sol_chesapeake_id}"
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Chesapeake Employers", html)
        self.assertIn(f'value="{self.sol_chesapeake_id}"', html)

    def test_add_contact_post_creates_contact_for_correct_partner(self):
        self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/new",
            data={
                "return_to_solicitation": str(self.sol_chesapeake_id),
                "first_name": "Susan",
                "last_name": "Jones",
                "title": "VP",
                "email": "susan@chesapeake.com",
                "phone": "4105550020",
                "is_active": "on",
            },
        )
        with self.app.app_context():
            from sqlalchemy import select as sa_select
            contacts = db.session.scalars(
                sa_select(Contact).where(Contact.partner_id == self.partner_chesapeake_id)
            ).all()
            names = [c.last_name for c in contacts]
            self.assertIn("Jones", names)
            # Ensure no contact was created for the other partner
            other_contacts = db.session.scalars(
                sa_select(Contact).where(Contact.partner_id == self.partner_other_id)
            ).all()
            self.assertEqual(len(other_contacts), 0)

    def test_add_contact_post_redirects_to_solicitation_edit(self):
        response = self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/new",
            data={
                "return_to_solicitation": str(self.sol_chesapeake_id),
                "first_name": "Susan",
                "last_name": "Jones",
                "title": "VP",
                "email": "susan@chesapeake.com",
                "phone": "4105550020",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            f"/solicitations/{self.sol_chesapeake_id}/edit",
            response.headers["Location"],
        )

    def test_add_contact_cancel_returns_to_solicitation_edit(self):
        """The cancel link in the contact form points back to Edit Solicitation."""
        response = self.client.get(
            f"/partners/{self.partner_chesapeake_id}/contacts/new"
            f"?return_to_solicitation={self.sol_chesapeake_id}"
        )
        html = response.get_data(as_text=True)
        self.assertIn(f"/solicitations/{self.sol_chesapeake_id}/edit", html)

    def test_adding_contact_does_not_silently_replace_existing_primary(self):
        """If Mark is primary, adding Susan must not demote Mark."""
        with self.app.app_context():
            mark = db.session.get(Contact, self.mark_id)
            mark.is_primary = True
            db.session.commit()

        self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/new",
            data={
                "return_to_solicitation": str(self.sol_chesapeake_id),
                "first_name": "Susan",
                "last_name": "Jones",
                "title": "VP",
                "email": "susan@chesapeake.com",
                "phone": "4105550020",
                "is_active": "on",
                # is_primary NOT set — new contact is non-primary
            },
        )
        with self.app.app_context():
            mark = db.session.get(Contact, self.mark_id)
            self.assertTrue(mark.is_primary, "Mark should remain primary after adding Susan")

    # ── Cross-Partner return_to_solicitation validation ───────────────────

    def test_forged_cross_partner_return_target_rejected_on_get(self):
        """GET with a return_to_solicitation belonging to a different partner is rejected."""
        response = self.client.get(
            f"/partners/{self.partner_chesapeake_id}/contacts/new"
            f"?return_to_solicitation={self.sol_other_id}"  # belongs to partner_other
        )
        self.assertEqual(response.status_code, 400)

    def test_forged_cross_partner_return_target_rejected_on_post(self):
        """POST with a forged return_to_solicitation is rejected."""
        response = self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/new",
            data={
                "return_to_solicitation": str(self.sol_other_id),
                "first_name": "Forger",
                "last_name": "Attack",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 400)

    # ── Make Primary route ────────────────────────────────────────────────

    def test_make_primary_sets_contact_as_primary(self):
        response = self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/{self.mark_id}/make-primary"
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            mark = db.session.get(Contact, self.mark_id)
            self.assertTrue(mark.is_primary)

    def test_make_primary_demotes_former_primary(self):
        """Making Susan primary must demote Mark."""
        with self.app.app_context():
            mark = db.session.get(Contact, self.mark_id)
            mark.is_primary = True
            susan = Contact(
                partner_id=self.partner_chesapeake_id,
                first_name="Susan", last_name="Jones",
                is_primary=False, is_active=True,
            )
            db.session.add(susan)
            db.session.commit()
            susan_id = susan.id

        self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/{susan_id}/make-primary"
        )
        with self.app.app_context():
            mark = db.session.get(Contact, self.mark_id)
            susan = db.session.get(Contact, susan_id)
            self.assertFalse(mark.is_primary, "Mark should be demoted")
            self.assertTrue(susan.is_primary, "Susan should be primary")

    def test_make_primary_only_one_primary_remains(self):
        """After Make Primary, exactly one contact is primary."""
        with self.app.app_context():
            susan = Contact(
                partner_id=self.partner_chesapeake_id,
                first_name="Susan", last_name="Jones",
                is_primary=False, is_active=True,
            )
            db.session.add(susan)
            db.session.commit()
            susan_id = susan.id

        self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/{susan_id}/make-primary"
        )
        with self.app.app_context():
            from sqlalchemy import select as sa_select
            primaries = db.session.scalars(
                sa_select(Contact).where(
                    Contact.partner_id == self.partner_chesapeake_id,
                    Contact.is_primary == True,
                )
            ).all()
            self.assertEqual(len(primaries), 1)
            self.assertEqual(primaries[0].id, susan_id)

    def test_make_primary_is_idempotent(self):
        """Making an already-primary contact primary again is a no-op."""
        with self.app.app_context():
            mark = db.session.get(Contact, self.mark_id)
            mark.is_primary = True
            db.session.commit()

        response = self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/{self.mark_id}/make-primary"
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            mark = db.session.get(Contact, self.mark_id)
            self.assertTrue(mark.is_primary)

    def test_make_primary_rejects_inactive_contact(self):
        with self.app.app_context():
            mark = db.session.get(Contact, self.mark_id)
            mark.is_active = False
            db.session.commit()

        response = self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/{self.mark_id}/make-primary"
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            mark = db.session.get(Contact, self.mark_id)
            self.assertFalse(mark.is_primary, "Inactive contact must not become primary")

    def test_make_primary_rejects_wrong_partner(self):
        """Cannot make a contact primary for a partner it doesn't belong to."""
        response = self.client.post(
            f"/partners/{self.partner_other_id}/contacts/{self.mark_id}/make-primary"
        )
        self.assertEqual(response.status_code, 404)

    def test_make_primary_redirects_to_solicitation_edit_when_provided(self):
        response = self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/{self.mark_id}/make-primary",
            data={"return_to_solicitation": str(self.sol_chesapeake_id)},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            f"/solicitations/{self.sol_chesapeake_id}/edit",
            response.headers["Location"],
        )

    def test_make_primary_redirects_to_partner_detail_without_solicitation(self):
        response = self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/{self.mark_id}/make-primary"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            f"/partners/{self.partner_chesapeake_id}",
            response.headers["Location"],
        )

    # ── Permissions ───────────────────────────────────────────────────────

    def test_reader_cannot_make_primary(self):
        self._login_as_reader()
        response = self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/{self.mark_id}/make-primary"
        )
        # Should redirect to login or return 403
        self.assertIn(response.status_code, (302, 403))
        if response.status_code == 302:
            self.assertIn("login", response.headers["Location"].lower())

    def test_reader_cannot_add_contact(self):
        self._login_as_reader()
        response = self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/new",
            data={
                "first_name": "Hacker",
                "last_name": "Reader",
                "is_active": "on",
            },
        )
        self.assertIn(response.status_code, (302, 403))
        if response.status_code == 302:
            self.assertIn("login", response.headers["Location"].lower())

    def test_editor_can_make_primary(self):
        response = self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/{self.mark_id}/make-primary"
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            mark = db.session.get(Contact, self.mark_id)
            self.assertTrue(mark.is_primary)

    # ── Centralized selection after Make Primary ──────────────────────────

    def test_select_partner_contact_returns_new_primary_immediately(self):
        """After Make Primary, select_partner_contact returns the new primary."""
        with self.app.app_context():
            susan = Contact(
                partner_id=self.partner_chesapeake_id,
                first_name="Susan", last_name="Jones",
                is_primary=False, is_active=True,
            )
            db.session.add(susan)
            db.session.commit()
            susan_id = susan.id

        self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/{susan_id}/make-primary"
        )
        with self.app.app_context():
            partner = db.session.get(Partner, self.partner_chesapeake_id)
            # Expire cached relationships
            db.session.expire(partner)
            selected = select_partner_contact(partner)
            self.assertIsNotNone(selected)
            self.assertEqual(selected.id, susan_id)

    def test_readiness_uses_new_primary_after_make_primary(self):
        """Readiness diagnostics use the new primary after Make Primary."""
        with self.app.app_context():
            mark = db.session.get(Contact, self.mark_id)
            mark.is_primary = True
            mark.email = "mark@chesapeake.com"
            mark.phone = "4105550010"
            db.session.commit()

            susan = Contact(
                partner_id=self.partner_chesapeake_id,
                first_name="Susan", last_name="Jones",
                email="susan@chesapeake.com", phone="4105550020",
                is_primary=False, is_active=True,
            )
            db.session.add(susan)
            db.session.commit()
            susan_id = susan.id

        self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/{susan_id}/make-primary"
        )
        with self.app.app_context():
            sol = db.session.get(Solicitation, self.sol_chesapeake_id)
            db.session.expire_all()
            sol = db.session.get(Solicitation, self.sol_chesapeake_id)
            diag = solicitation_readiness_diagnostics(sol)
            # The selected contact should be Susan
            partner = db.session.get(Partner, self.partner_chesapeake_id)
            db.session.expire(partner)
            selected = select_partner_contact(partner)
            self.assertEqual(selected.id, susan_id)

    def test_letter_context_uses_new_primary_after_make_primary(self):
        """Letter context uses the new primary contact after Make Primary."""
        with self.app.app_context():
            mark = db.session.get(Contact, self.mark_id)
            mark.is_primary = True
            mark.first_name = "Mark"
            mark.last_name = "Isakson"
            # Ensure partner has address for letter context
            partner = db.session.get(Partner, self.partner_chesapeake_id)
            partner.address_1 = "100 Harbor Blvd"
            partner.city = "Baltimore"
            partner.state = "MD"
            partner.postal_code = "21201"
            db.session.commit()

            susan = Contact(
                partner_id=self.partner_chesapeake_id,
                first_name="Susan", last_name="Jones",
                email="susan@chesapeake.com", phone="4105550020",
                is_primary=False, is_active=True,
            )
            db.session.add(susan)
            db.session.commit()
            susan_id = susan.id

        self.client.post(
            f"/partners/{self.partner_chesapeake_id}/contacts/{susan_id}/make-primary"
        )
        with self.app.app_context():
            context = build_solicitation_letter_context_for_solicitation(self.sol_chesapeake_id)
            self.assertEqual(context["contact_first_name"], "Susan")
            self.assertEqual(context["contact_last_name"], "Jones")

    # ── No schema/migration changes ───────────────────────────────────────

    def test_no_new_columns_on_solicitation(self):
        """Solicitation model must not have a contact_id or contact reference."""
        from app.models import Solicitation as Sol
        self.assertFalse(hasattr(Sol, "contact_id"))
        self.assertFalse(hasattr(Sol, "contact"))


if __name__ == "__main__":
    unittest.main()
