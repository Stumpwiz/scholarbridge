"""
Unit tests for app/services/dashboard_stats.py.

Uses an in-memory SQLite database so no external DB is required.
"""

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Campaign, Partner, Person, Solicitation
from app.models.contact import Contact
from app.models.user import User
from app.services.dashboard_stats import (
    campaign_detail_stats,
    campaign_stats,
    dashboard_highlights,
    partner_stats,
    people_stats,
    solicitation_stats,
)


def _make_app():
    tmp_dir = Path(tempfile.mkdtemp(prefix="sb_stats_test_"))

    class TestConfig(Config):
        SECRET_KEY = "test-secret"
        TESTING = True
        DATABASE_URL = f"sqlite:///{tmp_dir / 'test.db'}"

    return create_app(TestConfig)


class DashboardStatsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = _make_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _partner(self, name="Acme", is_active=True, partner_type="Insurance"):
        p = Partner(partner_name=name, is_active=is_active, partner_type=partner_type)
        db.session.add(p)
        db.session.flush()
        return p

    def _campaign(self, year=2024, status="active"):
        c = Campaign(
            campaign_year=year,
            campaign_name=f"Campaign {year}",
            status=status,
        )
        db.session.add(c)
        db.session.flush()
        return c

    def _person(self, first="Alice", last="Smith", is_active=True):
        p = Person(first_name=first, last_name=last, is_active=is_active)
        db.session.add(p)
        db.session.flush()
        return p

    def _user(self, person, role=User.ROLE_READER):
        u = User(
            username=f"user_{person.id}",
            email=f"user_{person.id}@example.com",
            role=role,
            person_id=person.id,
        )
        u.set_password("password")
        db.session.add(u)
        db.session.flush()
        return u

    def _solicitation(
        self,
        partner,
        campaign,
        status="not_contacted",
        tranche=1,
        business_volume=None,
        amount_requested=None,
        amount_received=None,
        mrpoc=None,
    ):
        s = Solicitation(
            partner_id=partner.id,
            campaign_id=campaign.id,
            status=status,
            tranche=tranche,
            business_volume=business_volume,
            amount_requested=amount_requested,
            amount_received=amount_received,
            mrpoc_person_id=mrpoc.id if mrpoc else None,
        )
        db.session.add(s)
        db.session.flush()
        return s

    # ------------------------------------------------------------------
    # partner_stats
    # ------------------------------------------------------------------

    def test_partner_stats_empty(self):
        db.session.commit()
        stats = partner_stats()
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["active"], 0)
        self.assertEqual(stats["donated"], 0)
        self.assertEqual(stats["missing_primary_contact"], 0)

    def test_partner_stats_counts(self):
        p1 = self._partner("A", is_active=True)
        p2 = self._partner("B", is_active=False)
        campaign = self._campaign()
        self._solicitation(p1, campaign, status="donated")
        db.session.commit()

        stats = partner_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["active"], 1)
        self.assertEqual(stats["inactive"], 1)
        self.assertEqual(stats["donated"], 1)

    def test_partner_stats_missing_primary_contact(self):
        p1 = self._partner("A")
        p2 = self._partner("B")
        # Give p1 a primary contact
        c = Contact(
            partner_id=p1.id,
            first_name="Joe",
            last_name="Doe",
            title="Manager",
            is_primary=True,
        )
        db.session.add(c)
        db.session.commit()

        stats = partner_stats()
        self.assertEqual(stats["missing_primary_contact"], 1)

    # ------------------------------------------------------------------
    # people_stats
    # ------------------------------------------------------------------

    def test_people_stats_empty(self):
        db.session.commit()
        stats = people_stats()
        self.assertEqual(stats["total_people"], 0)
        self.assertEqual(stats["total_users"], 0)

    def test_people_stats_role_counts(self):
        p1 = self._person("Alice", "A")
        p2 = self._person("Bob", "B")
        p3 = self._person("Carol", "C")
        self._user(p1, role=User.ROLE_ADMIN)
        self._user(p2, role=User.ROLE_EDITOR)
        self._user(p3, role=User.ROLE_READER)
        db.session.commit()

        stats = people_stats()
        self.assertEqual(stats["total_people"], 3)
        self.assertEqual(stats["total_users"], 3)
        self.assertEqual(stats["admin_users"], 1)
        self.assertEqual(stats["editor_users"], 1)
        self.assertEqual(stats["reader_users"], 1)

    def test_people_stats_mrpoc_count(self):
        p1 = self._person("Alice", "A")
        p2 = self._person("Bob", "B")
        partner = self._partner()
        campaign = self._campaign()
        self._solicitation(partner, campaign, mrpoc=p1)
        db.session.commit()

        stats = people_stats()
        self.assertEqual(stats["mrpoc_count"], 1)

    # ------------------------------------------------------------------
    # campaign_stats
    # ------------------------------------------------------------------

    def test_campaign_stats_empty(self):
        db.session.commit()
        stats = campaign_stats()
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["active"], 0)
        self.assertEqual(stats["total_solicitations"], 0)

    def test_campaign_stats_totals(self):
        c1 = self._campaign(2024, "active")
        c2 = self._campaign(2023, "closed")
        p = self._partner()
        self._solicitation(p, c1, business_volume=Decimal("1000"), amount_requested=Decimal("500"), amount_received=Decimal("300"))
        self._solicitation(p, c2, business_volume=None)
        db.session.commit()

        stats = campaign_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["active"], 1)
        self.assertEqual(stats["total_solicitations"], 2)
        self.assertEqual(stats["not_ready_solicitations"], 1)
        self.assertEqual(stats["total_business_volume"], Decimal("1000"))
        self.assertEqual(stats["total_requested"], Decimal("500"))
        self.assertEqual(stats["total_received"], Decimal("300"))

    # ------------------------------------------------------------------
    # campaign_detail_stats
    # ------------------------------------------------------------------

    def test_campaign_detail_stats(self):
        c = self._campaign(2024, "active")
        p1 = self._partner("A")
        p2 = self._partner("B")
        self._solicitation(p1, c, tranche=1, business_volume=Decimal("500"), amount_requested=Decimal("200"), amount_received=Decimal("100"), status="donated")
        self._solicitation(p2, c, tranche=2, business_volume=None, status="not_contacted")
        db.session.commit()

        stats = campaign_detail_stats(c.id)
        self.assertEqual(stats["sol_count"], 2)
        self.assertEqual(stats["not_ready"], 1)
        self.assertEqual(stats["total_bv"], Decimal("500"))
        self.assertEqual(stats["total_req"], Decimal("200"))
        self.assertEqual(stats["total_rec"], Decimal("100"))
        self.assertEqual(stats["tranche_counts"][1], 1)
        self.assertEqual(stats["tranche_counts"][2], 1)
        self.assertEqual(stats["status_counts"]["donated"], 1)

    # ------------------------------------------------------------------
    # solicitation_stats
    # ------------------------------------------------------------------

    def test_solicitation_stats_empty(self):
        db.session.commit()
        stats = solicitation_stats()
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["ready"], 0)
        self.assertEqual(stats["not_ready"], 0)

    def test_solicitation_stats_by_status_and_tranche(self):
        c = self._campaign()
        p1 = self._partner("A")
        p2 = self._partner("B")
        self._solicitation(p1, c, status="donated", tranche=1, business_volume=Decimal("1000"), amount_requested=Decimal("400"), amount_received=Decimal("200"))
        self._solicitation(p2, c, status="not_contacted", tranche=2, business_volume=None)
        db.session.commit()

        stats = solicitation_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["ready"], 1)
        self.assertEqual(stats["not_ready"], 1)
        self.assertEqual(stats["by_status"]["donated"], 1)
        self.assertEqual(stats["by_tranche"][1], 1)
        self.assertEqual(stats["by_tranche"][2], 1)
        self.assertEqual(stats["total_requested"], Decimal("400"))
        self.assertEqual(stats["total_received"], Decimal("200"))

    # ------------------------------------------------------------------
    # dashboard_highlights
    # ------------------------------------------------------------------

    def test_dashboard_highlights_empty(self):
        db.session.commit()
        h = dashboard_highlights()
        self.assertEqual(h["active_partners"], 0)
        self.assertEqual(h["total_solicitations"], 0)
        self.assertIsNone(h["completion_pct"])
        self.assertIsNone(h["active_campaign_name"])

    def test_dashboard_highlights_with_data(self):
        c = self._campaign(2024, "active")
        p = self._partner()
        self._solicitation(p, c, status="donated", business_volume=Decimal("1000"), amount_received=Decimal("500"))
        db.session.commit()

        h = dashboard_highlights()
        self.assertEqual(h["active_partners"], 1)
        self.assertEqual(h["total_solicitations"], 1)
        self.assertEqual(h["completion_pct"], 0)
        self.assertEqual(h["donated_count"], 1)
        self.assertEqual(h["total_received"], Decimal("500"))
        self.assertIsNotNone(h["active_campaign_name"])


if __name__ == "__main__":
    unittest.main()
