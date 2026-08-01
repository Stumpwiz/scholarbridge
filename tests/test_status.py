import unittest
from types import SimpleNamespace

from app.main.status import (
    partner_is_incomplete,
    partner_readiness_summary,
    solicitation_is_incomplete,
    solicitation_is_letter_ready,
    solicitation_is_ready,
    solicitation_readiness_diagnostics,
    select_partner_contact,
)

_MISSING = object()


def _partner(*, partner_type="Insurance", contacts=None):
    return SimpleNamespace(partner_type=partner_type, contacts=contacts or [])


def _contact(
    *, first_name="First", last_name="Last", title="Manager",
    is_primary=False, is_active=True, contact_id=1
):
    return SimpleNamespace(
        first_name=first_name,
        last_name=last_name,
        title=title,
        is_primary=is_primary,
        is_active=is_active,
        id=contact_id,
    )


def _solicitation(
    *,
    partner=None,
    solicitor_person_id=1,
    solicitor=_MISSING,
    mrpoc=_MISSING,
    business_volume=1000,
    amount_requested=500,
):
    default_person = SimpleNamespace(
        first_name="First",
        last_name="Last",
        email="person@example.com",
        phone="4105551212",
        mobile_phone=None,
        other_phone=None,
    )
    return SimpleNamespace(
        partner=partner if partner is not None else _partner(),
        solicitor_person_id=solicitor_person_id,
        solicitor=default_person if solicitor is _MISSING else solicitor,
        mrpoc=default_person if mrpoc is _MISSING else mrpoc,
        business_volume=business_volume,
        amount_requested=amount_requested,
    )


class StatusHelperTests(unittest.TestCase):
    def test_contact_selection_prefers_active_primary(self):
        inactive_primary = _contact(first_name="Inactive", is_primary=True, is_active=False)
        active_regular = _contact(first_name="Regular", is_primary=False)
        active_primary = _contact(first_name="Primary", is_primary=True, contact_id=3)
        partner = _partner(contacts=[inactive_primary, active_regular, active_primary])
        self.assertIs(select_partner_contact(partner), active_primary)

    def test_contact_selection_falls_back_deterministically_by_name_and_id(self):
        later = _contact(first_name="Zed", last_name="Zulu", contact_id=1)
        same_name_later_id = _contact(first_name="Amy", last_name="Able", contact_id=3)
        expected = _contact(first_name="Amy", last_name="Able", contact_id=2)
        partner = _partner(contacts=[later, same_name_later_id, expected])
        self.assertIs(select_partner_contact(partner), expected)

    def test_contact_selection_returns_none_when_all_contacts_are_inactive(self):
        partner = _partner(contacts=[_contact(is_primary=True, is_active=False)])
        self.assertIsNone(select_partner_contact(partner))

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
        self.assertTrue(
            solicitation_is_incomplete(_solicitation(solicitor_person_id=None, solicitor=None))
        )

    def test_solicitation_without_required_solicitor_fields_is_incomplete(self):
        solicitor = SimpleNamespace(
            first_name="First",
            last_name="Last",
            email=None,
            phone="4105551212",
            mobile_phone=None,
            other_phone=None,
        )
        self.assertTrue(solicitation_is_incomplete(_solicitation(solicitor=solicitor)))

    def test_solicitation_without_required_mrpoc_fields_is_incomplete(self):
        mrpoc = SimpleNamespace(
            first_name="First",
            last_name=None,
            email="mr@example.com",
            phone="4105551212",
            mobile_phone=None,
            other_phone=None,
        )
        self.assertTrue(solicitation_is_incomplete(_solicitation(mrpoc=mrpoc)))

    def test_solicitation_zero_business_volume_is_not_incomplete(self):
        self.assertFalse(solicitation_is_incomplete(_solicitation(business_volume=0)))
        self.assertTrue(solicitation_is_letter_ready(_solicitation(business_volume=0)))

    def test_solicitation_missing_business_volume_is_not_incomplete(self):
        self.assertFalse(solicitation_is_incomplete(_solicitation(business_volume=None)))
        self.assertFalse(solicitation_is_incomplete(_solicitation(business_volume="   ")))
        self.assertTrue(solicitation_is_letter_ready(_solicitation(business_volume=None)))

    def test_solicitation_readiness_ignores_business_volume(self):
        self.assertTrue(solicitation_is_ready(_solicitation(business_volume=0)))
        self.assertTrue(solicitation_is_ready(_solicitation(business_volume=None)))

    def test_solicitation_readiness_still_requires_partner_and_amount_requested(self):
        incomplete_partner = _partner(partner_type=None)
        self.assertFalse(
            solicitation_is_ready(_solicitation(partner=incomplete_partner, business_volume=0))
        )
        self.assertFalse(
            solicitation_is_ready(_solicitation(amount_requested=None, business_volume=0))
        )

    def test_solicitation_with_missing_amount_requested_is_not_letter_ready(self):
        self.assertFalse(solicitation_is_letter_ready(_solicitation(amount_requested=None)))
        self.assertFalse(solicitation_is_letter_ready(_solicitation(amount_requested="")))

    def test_solicitation_with_all_required_fields_is_letter_ready(self):
        self.assertTrue(solicitation_is_letter_ready(_solicitation()))


class PartnerReadinessSummaryTests(unittest.TestCase):
    def test_none_partner_is_not_complete(self):
        result = partner_readiness_summary(None)
        self.assertFalse(result["is_complete"])
        self.assertTrue(len(result["missing"]) > 0)

    def test_complete_partner_no_contacts(self):
        result = partner_readiness_summary(_partner(partner_type="Insurance", contacts=[]))
        self.assertTrue(result["is_complete"])
        self.assertEqual(result["missing"], [])

    def test_missing_category_is_incomplete(self):
        result = partner_readiness_summary(_partner(partner_type=None))
        self.assertFalse(result["is_complete"])
        self.assertIn("Partner category is missing.", result["missing"])

    def test_needs_review_category_is_incomplete(self):
        result = partner_readiness_summary(_partner(partner_type="Needs Review"))
        self.assertFalse(result["is_complete"])
        self.assertTrue(any("Needs Review" in m for m in result["missing"]))

    def test_contact_missing_first_name_is_incomplete(self):
        result = partner_readiness_summary(_partner(contacts=[_contact(first_name=None)]))
        self.assertFalse(result["is_complete"])
        self.assertTrue(any("first name" in m for m in result["missing"]))

    def test_contact_missing_last_name_is_incomplete(self):
        result = partner_readiness_summary(_partner(contacts=[_contact(last_name="")]))
        self.assertFalse(result["is_complete"])
        self.assertTrue(any("last name" in m for m in result["missing"]))

    def test_contact_missing_title_is_incomplete(self):
        result = partner_readiness_summary(_partner(contacts=[_contact(title=None)]))
        self.assertFalse(result["is_complete"])
        self.assertTrue(any("title" in m for m in result["missing"]))

    def test_complete_partner_with_full_contact(self):
        result = partner_readiness_summary(_partner(contacts=[_contact()]))
        self.assertTrue(result["is_complete"])
        self.assertEqual(result["missing"], [])


class SolicitationReadinessDiagnosticsTests(unittest.TestCase):
    def test_fully_ready_solicitation(self):
        result = solicitation_readiness_diagnostics(_solicitation())
        self.assertEqual(
            result,
            {"is_ready": True, "partner_issues": [], "solicitation_issues": []},
        )

    def test_missing_partner_category(self):
        result = solicitation_readiness_diagnostics(
            _solicitation(partner=_partner(partner_type=None))
        )
        self.assertIn("Partner category is missing.", result["partner_issues"])

    def test_partially_populated_contact_missing_title(self):
        result = solicitation_readiness_diagnostics(
            _solicitation(partner=_partner(contacts=[_contact(title=None)]))
        )
        self.assertIn("Primary contact title is missing.", result["partner_issues"])

    def test_contact_missing_first_name(self):
        result = solicitation_readiness_diagnostics(
            _solicitation(partner=_partner(contacts=[_contact(first_name="")]))
        )
        self.assertIn("Primary contact first name is missing.", result["partner_issues"])

    def test_contact_missing_last_name(self):
        result = solicitation_readiness_diagnostics(
            _solicitation(partner=_partner(contacts=[_contact(last_name=None)]))
        )
        self.assertIn("Primary contact last name is missing.", result["partner_issues"])

    def test_missing_requested_amount(self):
        result = solicitation_readiness_diagnostics(_solicitation(amount_requested=None))
        self.assertIn("Requested amount is missing.", result["solicitation_issues"])

    def test_simultaneous_partner_and_solicitation_issues(self):
        solicitation = _solicitation(
            partner=_partner(partner_type=None), amount_requested=None
        )
        result = solicitation_readiness_diagnostics(solicitation)
        self.assertFalse(result["is_ready"])
        self.assertTrue(result["partner_issues"])
        self.assertTrue(result["solicitation_issues"])

    def test_business_volume_is_never_reported(self):
        result = solicitation_readiness_diagnostics(_solicitation(business_volume=None))
        all_issues = result["partner_issues"] + result["solicitation_issues"]
        self.assertTrue(result["is_ready"])
        self.assertFalse(any("business volume" in issue.lower() for issue in all_issues))

    def test_diagnostics_and_boolean_readiness_are_consistent(self):
        solicitations = [
            _solicitation(),
            _solicitation(amount_requested=None),
            _solicitation(partner=_partner(partner_type=None)),
            _solicitation(solicitor_person_id=None, solicitor=None),
        ]
        for solicitation in solicitations:
            with self.subTest(solicitation=solicitation):
                self.assertEqual(
                    solicitation_readiness_diagnostics(solicitation)["is_ready"],
                    solicitation_is_ready(solicitation),
                )

    def test_letter_diagnostics_include_existing_person_requirements(self):
        solicitor = SimpleNamespace(
            first_name="First",
            last_name=None,
            email=None,
            phone=None,
            mobile_phone=None,
            other_phone=None,
        )
        solicitation = _solicitation(solicitor=solicitor, mrpoc=None)
        result = solicitation_readiness_diagnostics(solicitation, for_letter=True)
        self.assertIn("Solicitor last name is missing.", result["solicitation_issues"])
        self.assertIn("Solicitor email is missing.", result["solicitation_issues"])
        self.assertIn("Solicitor phone is missing.", result["solicitation_issues"])
        self.assertIn("MRPOC is missing.", result["solicitation_issues"])
        self.assertEqual(result["is_ready"], solicitation_is_letter_ready(solicitation))

    def test_primary_contact_preferred_over_first(self):
        non_primary = _contact(first_name=None, is_primary=False)
        primary = _contact(first_name="Alice", is_primary=True)
        result = partner_readiness_summary(_partner(contacts=[non_primary, primary]))
        self.assertTrue(result["is_complete"])


if __name__ == "__main__":
    unittest.main()
