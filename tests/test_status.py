import unittest
from types import SimpleNamespace

from app.main.status import (
    partner_is_incomplete,
    solicitation_is_incomplete,
    solicitation_is_letter_ready,
)


def _partner(*, partner_type="Insurance", contacts=None):
    return SimpleNamespace(partner_type=partner_type, contacts=contacts or [])


def _contact(*, first_name="First", last_name="Last", title="Manager", is_primary=False):
    return SimpleNamespace(
        first_name=first_name,
        last_name=last_name,
        title=title,
        is_primary=is_primary,
    )


def _solicitation(
    *,
    partner=None,
    solicitor_person_id=1,
    business_volume=1000,
    amount_requested=500,
):
    return SimpleNamespace(
        partner=partner if partner is not None else _partner(),
        solicitor_person_id=solicitor_person_id,
        solicitor=None,
        business_volume=business_volume,
        amount_requested=amount_requested,
    )


class StatusHelperTests(unittest.TestCase):
    def test_partner_missing_partner_type_is_incomplete(self):
        self.assertTrue(partner_is_incomplete(_partner(partner_type=None)))
        self.assertTrue(partner_is_incomplete(_partner(partner_type="")))
        self.assertTrue(partner_is_incomplete(_partner(partner_type="   ")))
        self.assertTrue(partner_is_incomplete(_partner(partner_type="Needs Review")))

    def test_partner_contact_missing_name_or_title_is_incomplete(self):
        self.assertTrue(
            partner_is_incomplete(_partner(contacts=[_contact(first_name="   ")]))
        )
        self.assertTrue(
            partner_is_incomplete(_partner(contacts=[_contact(last_name=None)]))
        )
        self.assertTrue(
            partner_is_incomplete(_partner(contacts=[_contact(title="")]))
        )

    def test_partner_without_contact_is_not_incomplete_due_to_absent_contact(self):
        self.assertFalse(partner_is_incomplete(_partner(contacts=[])))
        self.assertFalse(partner_is_incomplete(_partner(contacts=None)))

    def test_solicitation_with_incomplete_partner_is_incomplete(self):
        incomplete_partner = _partner(partner_type=None)
        self.assertTrue(
            solicitation_is_incomplete(_solicitation(partner=incomplete_partner))
        )

    def test_solicitation_without_solicitor_is_incomplete(self):
        self.assertTrue(solicitation_is_incomplete(_solicitation(solicitor_person_id=None)))

    def test_solicitation_without_business_volume_is_incomplete(self):
        self.assertTrue(solicitation_is_incomplete(_solicitation(business_volume=None)))
        self.assertTrue(solicitation_is_incomplete(_solicitation(business_volume="   ")))

    def test_solicitation_with_missing_amount_requested_is_not_letter_ready(self):
        self.assertFalse(solicitation_is_letter_ready(_solicitation(amount_requested=None)))
        self.assertFalse(solicitation_is_letter_ready(_solicitation(amount_requested="")))

    def test_solicitation_with_all_required_fields_is_letter_ready(self):
        self.assertTrue(solicitation_is_letter_ready(_solicitation()))


if __name__ == "__main__":
    unittest.main()
