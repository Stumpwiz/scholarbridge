from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import (
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.auth.permissions import editor_required
from app.main import bp
from app.extensions import db
from app.models import (
    Campaign,
    CampaignCategoryMRPOC,
    Contact,
    Partner,
    Person,
    Solicitation,
)

CANONICAL_PARTNER_TYPE_OPTIONS = (
    "Food and Beverage",
    "Finance",
    "Insurance",
    "Accounting",
    "HR",
    "IT",
    "Security Services",
    "Construction",
    "Renovation",
    "Grounds",
    "Moving",
    "Packing",
    "Medical Service Providers",
    "Personal Service Providers",
    "Cleaning Services and Supplies",
    "Admin",
)
PARTNER_TYPE_NEEDS_REVIEW = "Needs Review"
PARTNER_TYPE_OPTIONS = (PARTNER_TYPE_NEEDS_REVIEW, *CANONICAL_PARTNER_TYPE_OPTIONS)

CAMPAIGN_STATUS_OPTIONS = ("planned", "active", "closed", "archived")
SOLICITATION_TRANCHE_OPTIONS = (1, 2, 3)
SOLICITATION_STATUS_OPTIONS = (
    "not_contacted",
    "contacted",
    "responded",
    "donated",
    "declined",
    "closed",
)


@bp.before_request
def require_authenticated_user():
    if request.endpoint == "main.health":
        return None
    if request.endpoint is None:
        return None
    if current_user.is_authenticated:
        return None
    return redirect(url_for("auth.login", next=request.full_path if request.query_string else request.path))


@bp.get("/")
def index():
    return render_template("index.html", page_title="Home")


@bp.get("/letters")
def letter_list():
    return render_template("letters/list.html", page_title="Letters")


@bp.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "app": current_app.config.get("APP_NAME", "ScholarBridge"),
        }
    )


@bp.before_app_request
def normalize_partner_categories_for_realignment() -> None:
    _normalize_legacy_partner_categories()


@bp.get("/campaigns")
def campaign_list():
    campaigns = db.session.scalars(
        select(Campaign).order_by(Campaign.campaign_year.desc())
    ).all()
    active_count = sum(1 for campaign in campaigns if campaign.status == "active")
    return render_template(
        "campaigns/list.html",
        page_title="Campaigns",
        campaigns=campaigns,
        active_count=active_count,
    )


@bp.route("/campaigns/new", methods=["GET", "POST"])
@editor_required
def campaign_create():
    form_data = _campaign_form_data()

    if request.method == "POST":
        form_data = _campaign_form_data(request.form)
        validation_error = _validate_campaign_form(form_data)
        if validation_error:
            flash(validation_error, "danger")
        else:
            campaign = Campaign(
                campaign_year=form_data["campaign_year"],
                campaign_name=_campaign_name_for_year(form_data["campaign_year"]),
                status=form_data["status"],
                notes=form_data["notes"],
            )
            db.session.add(campaign)
            db.session.commit()
            _flash_active_campaign_convention_notice(campaign.status)
            flash("Campaign created.", "success")
            return redirect(url_for("main.campaign_detail", campaign_id=campaign.id))

    return render_template(
        "campaigns/form.html",
        page_title="Create Campaign",
        mode="create",
        campaign=None,
        form_data=form_data,
        campaign_statuses=CAMPAIGN_STATUS_OPTIONS,
        suggested_name=_campaign_name_for_year(form_data["campaign_year"]),
    )


@bp.get("/campaigns/<int:campaign_id>")
def campaign_detail(campaign_id: int):
    campaign = db.get_or_404(Campaign, campaign_id)
    tranche_solicitations = _campaign_tranche_solicitations(campaign.id)
    available_partners = _available_partners_for_campaign(campaign.id)
    uncategorized_available_count = sum(
        1 for partner in available_partners if _partner_category_is_incomplete(partner.partner_type)
    )
    available_partners = [
        partner for partner in available_partners if not _partner_category_is_incomplete(partner.partner_type)
    ]
    category_mrpoc_map = _campaign_category_mrpoc_map(campaign.id)
    mrpoc_people = _person_options()
    return render_template(
        "campaigns/detail.html",
        page_title=campaign.campaign_name,
        campaign=campaign,
        tranche_solicitations=tranche_solicitations,
        available_partners=available_partners,
        uncategorized_available_count=uncategorized_available_count,
        tranche_options=SOLICITATION_TRANCHE_OPTIONS,
        partner_categories=CANONICAL_PARTNER_TYPE_OPTIONS,
        category_mrpoc_map=category_mrpoc_map,
        mrpoc_people=mrpoc_people,
    )


@bp.post("/campaigns/<int:campaign_id>/assign-partner")
@editor_required
def campaign_assign_partner(campaign_id: int):
    campaign = db.get_or_404(Campaign, campaign_id)
    tranche = _safe_int(request.form.get("tranche"))
    partner_id = _safe_int(request.form.get("partner_id"))

    if campaign.status == "closed":
        flash("Cannot assign partners to a closed campaign.", "danger")
        return redirect(url_for("main.campaign_detail", campaign_id=campaign.id))

    if tranche not in SOLICITATION_TRANCHE_OPTIONS:
        flash("Please select a valid tranche.", "danger")
        return redirect(url_for("main.campaign_detail", campaign_id=campaign.id))

    if partner_id is None:
        flash("Please select a partner to assign.", "danger")
        return redirect(url_for("main.campaign_detail", campaign_id=campaign.id))

    partner = db.session.get(Partner, partner_id)
    if partner is None:
        flash("Please select a valid partner.", "danger")
        return redirect(url_for("main.campaign_detail", campaign_id=campaign.id))

    existing_solicitation = db.session.scalar(
        select(Solicitation).where(
            Solicitation.campaign_id == campaign.id,
            Solicitation.partner_id == partner.id,
        )
    )
    if existing_solicitation is not None:
        flash("This partner is already assigned to the campaign.", "warning")
        return redirect(
            url_for(
                "main.solicitation_edit",
                solicitation_id=existing_solicitation.id,
                return_to="campaign",
            )
        )

    if _partner_category_is_incomplete(partner.partner_type):
        flash(
            "Partner must be categorized before assignment. Update the partner category and try again.",
            "danger",
        )
        return redirect(url_for("main.campaign_detail", campaign_id=campaign.id))

    solicitation = Solicitation(
        campaign_id=campaign.id,
        partner_id=partner.id,
        tranche=tranche,
        mrpoc_person_id=_campaign_mrpoc_person_id_for_partner_category(campaign.id, partner.partner_type),
        status="not_contacted",
    )
    db.session.add(solicitation)
    db.session.commit()

    flash("Partner assigned. Complete solicitation details and assign a solicitor.", "success")
    return redirect(
        url_for("main.solicitation_edit", solicitation_id=solicitation.id, return_to="campaign")
    )


@bp.post("/campaigns/<int:campaign_id>/mrpoc-mappings")
@editor_required
def campaign_set_mrpoc_mapping(campaign_id: int):
    campaign = db.get_or_404(Campaign, campaign_id)
    partner_category = (request.form.get("partner_category") or "").strip()
    mrpoc_person_id = _safe_int(request.form.get("mrpoc_person_id"))

    if partner_category not in CANONICAL_PARTNER_TYPE_OPTIONS:
        flash("Please select a valid partner category.", "danger")
        return redirect(url_for("main.campaign_detail", campaign_id=campaign.id))

    if mrpoc_person_id is not None and db.session.get(Person, mrpoc_person_id) is None:
        flash("Please select a valid MRPOC person.", "danger")
        return redirect(url_for("main.campaign_detail", campaign_id=campaign.id))

    mapping = db.session.scalar(
        select(CampaignCategoryMRPOC).where(
            CampaignCategoryMRPOC.campaign_id == campaign.id,
            CampaignCategoryMRPOC.partner_category == partner_category,
        )
    )

    if mrpoc_person_id is None:
        if mapping is not None:
            db.session.delete(mapping)
            db.session.commit()
            flash(f"MRPOC mapping cleared for {partner_category}.", "success")
        else:
            flash(f"No MRPOC mapping found for {partner_category}.", "warning")
        return redirect(url_for("main.campaign_detail", campaign_id=campaign.id))

    if mapping is None:
        mapping = CampaignCategoryMRPOC(
            campaign_id=campaign.id,
            partner_category=partner_category,
            mrpoc_person_id=mrpoc_person_id,
        )
        db.session.add(mapping)
    else:
        mapping.mrpoc_person_id = mrpoc_person_id

    db.session.commit()
    flash(f"MRPOC mapping saved for {partner_category}.", "success")
    return redirect(url_for("main.campaign_detail", campaign_id=campaign.id))


@bp.route("/campaigns/<int:campaign_id>/edit", methods=["GET", "POST"])
@editor_required
def campaign_edit(campaign_id: int):
    campaign = db.get_or_404(Campaign, campaign_id)
    form_data = _campaign_to_form_data(campaign)

    if request.method == "POST":
        form_data = _campaign_form_data(request.form)
        validation_error = _validate_campaign_form(form_data, campaign_id=campaign.id)
        if validation_error:
            flash(validation_error, "danger")
        else:
            campaign.campaign_year = form_data["campaign_year"]
            campaign.campaign_name = _campaign_name_for_year(form_data["campaign_year"])
            campaign.status = form_data["status"]
            campaign.notes = form_data["notes"]
            db.session.commit()
            _flash_active_campaign_convention_notice(campaign.status)
            flash("Campaign updated.", "success")
            return redirect(url_for("main.campaign_detail", campaign_id=campaign.id))

    return render_template(
        "campaigns/form.html",
        page_title=f"Edit {campaign.campaign_name}",
        mode="edit",
        campaign=campaign,
        form_data=form_data,
        campaign_statuses=CAMPAIGN_STATUS_OPTIONS,
        suggested_name=_campaign_name_for_year(form_data["campaign_year"]),
    )


@bp.get("/partners")
def partner_list():
    partners = db.session.scalars(select(Partner)).all()
    partners = sorted(
        partners,
        key=lambda partner: (
            not _partner_category_is_incomplete(partner.partner_type),
            _partner_sort_name(partner),
            partner.id,
        ),
    )
    category_review_count = sum(
        1 for partner in partners if _partner_category_is_incomplete(partner.partner_type)
    )
    incomplete_partner_ids = {
        partner.id
        for partner in partners
        if _partner_category_is_incomplete(partner.partner_type)
    }
    return render_template(
        "partners/list.html",
        page_title="Partners",
        partners=partners,
        category_review_count=category_review_count,
        needs_review_value=PARTNER_TYPE_NEEDS_REVIEW,
        incomplete_partner_ids=incomplete_partner_ids,
    )


@bp.get("/people")
def person_list():
    people = db.session.scalars(
        select(Person).order_by(
            Person.is_active.desc(),
            Person.last_name.asc(),
            Person.first_name.asc(),
            Person.id.asc(),
        )
    ).all()
    return render_template(
        "people/list.html",
        page_title="People",
        people=people,
    )


@bp.route("/people/new", methods=["GET", "POST"])
@editor_required
def person_create():
    form_data = _person_form_data()

    if request.method == "POST":
        form_data = _person_form_data(request.form)
        validation_error, clean_data = _validate_person_form(form_data)
        if validation_error:
            flash(validation_error, "danger")
        else:
            person = Person(**clean_data)
            db.session.add(person)
            db.session.commit()
            flash("Person created.", "success")
            return redirect(url_for("main.person_list"))

    return render_template(
        "people/form.html",
        page_title="Create Person",
        mode="create",
        person=None,
        form_data=form_data,
    )


@bp.route("/people/<int:person_id>/edit", methods=["GET", "POST"])
@editor_required
def person_edit(person_id: int):
    person = db.get_or_404(Person, person_id)
    form_data = _person_to_form_data(person)

    if request.method == "POST":
        form_data = _person_form_data(request.form)
        validation_error, clean_data = _validate_person_form(form_data)
        if validation_error:
            flash(validation_error, "danger")
        else:
            for key, value in clean_data.items():
                setattr(person, key, value)
            db.session.commit()
            flash("Person updated.", "success")
            return redirect(url_for("main.person_list"))

    return render_template(
        "people/form.html",
        page_title=f"Edit {person.first_name} {person.last_name}",
        mode="edit",
        person=person,
        form_data=form_data,
    )


@bp.get("/solicitations")
def solicitation_list():
    solicitations = db.session.scalars(
        select(Solicitation)
        .options(
            selectinload(Solicitation.campaign),
            selectinload(Solicitation.partner),
            selectinload(Solicitation.solicitor),
            selectinload(Solicitation.mrpoc),
        )
        .join(Solicitation.campaign)
        .join(Solicitation.partner)
        .order_by(
            Solicitation.tranche.asc(),
            Partner.partner_name.asc(),
            Campaign.campaign_year.desc(),
            Solicitation.id.asc(),
        )
    ).all()
    return render_template(
        "solicitations/list.html",
        page_title="Solicitations",
        solicitations=solicitations,
    )


@bp.route("/solicitations/new", methods=["GET", "POST"])
@editor_required
def solicitation_create():
    form_data = _solicitation_form_data()

    if request.method == "GET":
        campaign_id_from_query = _safe_int(request.args.get("campaign_id"))
        if campaign_id_from_query is not None:
            campaign = db.session.get(Campaign, campaign_id_from_query)
            if campaign and campaign.status != "closed":
                form_data["campaign_id"] = campaign.id
        elif form_data["campaign_id"] is None:
            form_data["campaign_id"] = _default_active_campaign_id()

    if request.method == "POST":
        form_data = _solicitation_form_data(request.form)
        validation_error, clean_data = _validate_solicitation_form(
            form_data, allow_closed_campaign=False
        )
        if validation_error:
            flash(validation_error, "danger")
        else:
            solicitation = Solicitation(**clean_data)
            db.session.add(solicitation)
            db.session.commit()
            flash("Solicitation created.", "success")
            return redirect(
                url_for("main.solicitation_detail", solicitation_id=solicitation.id)
            )

    campaigns, partners = _solicitation_form_options_for_create(
        selected_campaign_id=form_data["campaign_id"]
    )
    solicitors = _person_options()
    if form_data["partner_id"] and all(
        partner.id != form_data["partner_id"] for partner in partners
    ):
        form_data["partner_id"] = None

    return render_template(
        "solicitations/form.html",
        page_title="Create Solicitation",
        mode="create",
        solicitation=None,
        form_data=form_data,
        campaigns=campaigns,
        partners=partners,
        solicitors=solicitors,
        tranche_options=SOLICITATION_TRANCHE_OPTIONS,
        status_options=SOLICITATION_STATUS_OPTIONS,
    )


@bp.get("/solicitations/<int:solicitation_id>")
def solicitation_detail(solicitation_id: int):
    solicitation = db.get_or_404(Solicitation, solicitation_id)
    return_to = _solicitation_return_to_value()
    return render_template(
        "solicitations/detail.html",
        page_title=f"Solicitation #{solicitation.id}",
        solicitation=solicitation,
        return_to=return_to,
    )


@bp.route("/solicitations/<int:solicitation_id>/edit", methods=["GET", "POST"])
@editor_required
def solicitation_edit(solicitation_id: int):
    solicitation = db.get_or_404(Solicitation, solicitation_id)
    form_data = _solicitation_to_form_data(solicitation)
    campaigns, partners = _solicitation_form_options()
    solicitors = _person_options()
    return_to = _solicitation_return_to_value()

    if request.method == "POST":
        form_data = _solicitation_form_data(request.form)
        validation_error, clean_data = _validate_solicitation_form(
            form_data, solicitation_id=solicitation.id, allow_closed_campaign=True
        )
        if validation_error:
            flash(validation_error, "danger")
        else:
            for key, value in clean_data.items():
                setattr(solicitation, key, value)
            db.session.commit()
            flash("Solicitation updated.", "success")
            redirect_kwargs = {"solicitation_id": solicitation.id}
            if return_to == "campaign":
                redirect_kwargs["return_to"] = "campaign"
            return redirect(url_for("main.solicitation_detail", **redirect_kwargs))

    return render_template(
        "solicitations/form.html",
        page_title=f"Edit Solicitation #{solicitation.id}",
        mode="edit",
        solicitation=solicitation,
        form_data=form_data,
        campaigns=campaigns,
        partners=partners,
        solicitors=solicitors,
        return_to=return_to,
        tranche_options=SOLICITATION_TRANCHE_OPTIONS,
        status_options=SOLICITATION_STATUS_OPTIONS,
    )


@bp.route("/partners/new", methods=["GET", "POST"])
@editor_required
def partner_create():
    form_data = {"is_active": True}
    partner_types = _partner_type_choices()

    if request.method == "POST":
        form_data = _partner_form_data(request.form)
        validation_error = _validate_partner_form(form_data)
        if validation_error:
            flash(validation_error, "danger")
        else:
            partner = Partner(**form_data)
            db.session.add(partner)
            db.session.commit()
            flash("Partner created.", "success")
            return redirect(url_for("main.partner_detail", partner_id=partner.id))

    return render_template(
        "partners/form.html",
        page_title="Create Partner",
        mode="create",
        partner=None,
        form_data=form_data,
        partner_types=partner_types,
    )


@bp.get("/partners/<int:partner_id>")
def partner_detail(partner_id: int):
    partner = db.get_or_404(Partner, partner_id)
    return _render_partner_detail(
        partner=partner,
        contact_form_data=_contact_form_data(),
        editing_contact=None,
    )


@bp.route("/partners/<int:partner_id>/edit", methods=["GET", "POST"])
@editor_required
def partner_edit(partner_id: int):
    partner = db.get_or_404(Partner, partner_id)
    form_data = _partner_to_form_data(partner)
    partner_types = _partner_type_choices()

    if request.method == "POST":
        form_data = _partner_form_data(request.form)
        validation_error = _validate_partner_form(form_data)
        if validation_error:
            flash(validation_error, "danger")
        else:
            for key, value in form_data.items():
                setattr(partner, key, value)
            db.session.commit()
            flash("Partner updated.", "success")
            return redirect(url_for("main.partner_detail", partner_id=partner.id))

    return render_template(
        "partners/form.html",
        page_title=f"Edit {partner.partner_name}",
        mode="edit",
        partner=partner,
        form_data=form_data,
        partner_types=partner_types,
    )


@bp.post("/partners/<int:partner_id>/contacts/new")
@editor_required
def partner_contact_create(partner_id: int):
    partner = db.get_or_404(Partner, partner_id)
    contact_form_data = _contact_form_data(request.form)
    validation_error = _validate_contact_form(contact_form_data)

    if validation_error:
        flash(validation_error, "danger")
        return _render_partner_detail(
            partner=partner,
            contact_form_data=contact_form_data,
            editing_contact=None,
        )

    if contact_form_data["is_primary"]:
        _unset_other_primary_contacts(partner.id)

    contact = Contact(
        partner_id=partner.id,
        first_name=contact_form_data["first_name"],
        last_name=contact_form_data["last_name"],
        title=contact_form_data["title"],
        email=contact_form_data["email"],
        phone=contact_form_data["phone"],
        notes=contact_form_data["notes"],
        is_primary=contact_form_data["is_primary"],
        is_active=contact_form_data["is_active"],
    )
    db.session.add(contact)

    db.session.commit()
    flash("Contact added.", "success")
    return redirect(
        url_for("main.partner_detail", partner_id=partner.id, _anchor="contacts")
    )


@bp.route(
    "/partners/<int:partner_id>/contacts/<int:contact_id>/edit",
    methods=["GET", "POST"],
)
@editor_required
def partner_contact_edit(partner_id: int, contact_id: int):
    partner = db.get_or_404(Partner, partner_id)
    contact = db.get_or_404(Contact, contact_id)

    if contact.partner_id != partner.id:
        abort(404)

    if request.method == "POST":
        contact_form_data = _contact_form_data(request.form)
        validation_error = _validate_contact_form(contact_form_data)

        if validation_error:
            flash(validation_error, "danger")
            return _render_partner_detail(
                partner=partner,
                contact_form_data=_contact_form_data(),
                editing_contact=contact,
                edit_form_data=contact_form_data,
            )

        for key in ("first_name", "last_name", "title", "email", "phone", "notes"):
            setattr(contact, key, contact_form_data[key])
        contact.is_primary = contact_form_data["is_primary"]
        contact.is_active = contact_form_data["is_active"]

        if contact.is_primary:
            _unset_other_primary_contacts(partner.id, except_contact_id=contact.id)

        db.session.commit()
        flash("Contact updated.", "success")
        return redirect(
            url_for("main.partner_detail", partner_id=partner.id, _anchor="contacts")
        )

    return _render_partner_detail(
        partner=partner,
        contact_form_data=_contact_form_data(),
        editing_contact=contact,
        edit_form_data=_contact_to_form_data(contact),
    )


@bp.post("/partners/<int:partner_id>/contacts/<int:contact_id>/delete")
@editor_required
def partner_contact_delete(partner_id: int, contact_id: int):
    partner = db.get_or_404(Partner, partner_id)
    contact = db.get_or_404(Contact, contact_id)
    if contact.partner_id != partner.id:
        abort(404)

    db.session.delete(contact)
    db.session.commit()
    flash("Contact deleted.", "success")
    return redirect(
        url_for("main.partner_detail", partner_id=partner.id, _anchor="contacts")
    )


def _render_partner_detail(
    partner: Partner,
    contact_form_data: dict,
    editing_contact: Contact | None,
    edit_form_data: dict | None = None,
):
    contacts = _load_partner_contacts(partner.id)
    return render_template(
        "partners/detail.html",
        page_title=partner.partner_name,
        partner=partner,
        contacts=contacts,
        contact_form_data=contact_form_data,
        editing_contact=editing_contact,
        edit_form_data=edit_form_data or {},
    )


def _load_partner_contacts(partner_id: int) -> list[Contact]:
    return db.session.scalars(
        select(Contact)
        .where(Contact.partner_id == partner_id)
        .order_by(
            Contact.is_primary.desc(),
            Contact.is_active.desc(),
            Contact.last_name.asc(),
            Contact.first_name.asc(),
            Contact.id.asc(),
        )
    ).all()


def _unset_other_primary_contacts(
    partner_id: int, except_contact_id: int | None = None
) -> None:
    contacts = _load_partner_contacts(partner_id)
    for contact in contacts:
        if except_contact_id is not None and contact.id == except_contact_id:
            continue
        contact.is_primary = False


def _partner_form_data(form) -> dict:
    return {
        "partner_name": form.get("partner_name", "").strip(),
        "display_name": _empty_to_none(form.get("display_name")),
        "partner_type": _empty_to_none(form.get("partner_type")),
        "address_1": _empty_to_none(form.get("address_1")),
        "address_2": _empty_to_none(form.get("address_2")),
        "city": _empty_to_none(form.get("city")),
        "state": _empty_to_none(form.get("state")),
        "postal_code": _empty_to_none(form.get("postal_code")),
        "email_main": _empty_to_none(form.get("email_main")),
        "phone_main": _empty_to_none(form.get("phone_main")),
        "website": _empty_to_none(form.get("website")),
        "partner_notes": _empty_to_none(form.get("partner_notes")),
        "is_active": form.get("is_active") == "on",
    }


def _partner_to_form_data(partner: Partner) -> dict:
    return {
        "partner_name": partner.partner_name or "",
        "display_name": partner.display_name or "",
        "partner_type": partner.partner_type or "",
        "address_1": partner.address_1 or "",
        "address_2": partner.address_2 or "",
        "city": partner.city or "",
        "state": partner.state or "",
        "postal_code": partner.postal_code or "",
        "email_main": partner.email_main or "",
        "phone_main": partner.phone_main or "",
        "website": partner.website or "",
        "partner_notes": partner.partner_notes or "",
        "is_active": partner.is_active,
    }


def _validate_partner_form(form_data: dict) -> str | None:
    if not form_data["partner_name"]:
        return "Partner name is required."
    partner_type = form_data["partner_type"]
    if partner_type:
        if partner_type in PARTNER_TYPE_OPTIONS:
            return None
        return "Please select a valid partner category."
    return None


def _partner_category_is_incomplete(partner_type: str | None) -> bool:
    if not partner_type:
        return True
    return partner_type == PARTNER_TYPE_NEEDS_REVIEW


def _partner_sort_name(partner: Partner) -> str:
    sort_name = partner.display_name or partner.partner_name or ""
    return " ".join(sort_name.strip().lower().split())


def _empty_to_none(value):
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _campaign_name_for_year(campaign_year: int | None) -> str:
    if campaign_year is None:
        return "YYYY Scholarship Campaign"
    return f"{campaign_year} Scholarship Campaign"


def _campaign_form_data(form=None) -> dict:
    if form is None:
        return {
            "campaign_year": _current_year(),
            "status": "planned",
            "notes": "",
        }

    return {
        "campaign_year": _safe_int(form.get("campaign_year")),
        "status": (form.get("status") or "planned").strip(),
        "notes": _empty_to_none(form.get("notes")),
    }


def _campaign_to_form_data(campaign: Campaign) -> dict:
    return {
        "campaign_year": campaign.campaign_year,
        "status": campaign.status,
        "notes": campaign.notes or "",
    }


def _validate_campaign_form(form_data: dict, campaign_id: int | None = None) -> str | None:
    campaign_year = form_data["campaign_year"]
    if campaign_year is None:
        return "Campaign year is required."

    if campaign_year < 2000 or campaign_year > 2100:
        return "Campaign year must be between 2000 and 2100."

    if form_data["status"] not in CAMPAIGN_STATUS_OPTIONS:
        return "Please select a valid campaign status."

    existing_campaign = db.session.scalar(
        select(Campaign).where(Campaign.campaign_year == campaign_year)
    )
    if existing_campaign and existing_campaign.id != campaign_id:
        return f"A campaign for {campaign_year} already exists."

    return None


def _flash_active_campaign_convention_notice(current_status: str) -> None:
    if current_status != "active":
        return

    active_campaign_ids = db.session.scalars(
        select(Campaign.id).where(Campaign.status == "active")
    ).all()
    if len(active_campaign_ids) > 1:
        flash(
            "More than one campaign is currently marked active. "
            "Normal operations use one active campaign at a time.",
            "warning",
        )


def _current_year() -> int:
    return current_app.config.get("CURRENT_YEAR_OVERRIDE") or datetime.utcnow().year


def _safe_int(value) -> int | None:
    if value is None:
        return None
    stripped = str(value).strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


def _contact_form_data(form=None) -> dict:
    if form is None:
        return {
            "first_name": "",
            "last_name": "",
            "title": "",
            "email": "",
            "phone": "",
            "notes": "",
            "is_primary": False,
            "is_active": True,
        }

    return {
        "first_name": _empty_to_none(form.get("first_name")),
        "last_name": _empty_to_none(form.get("last_name")),
        "title": _empty_to_none(form.get("title")),
        "email": _empty_to_none(form.get("email")),
        "phone": _empty_to_none(form.get("phone")),
        "notes": _empty_to_none(form.get("notes")),
        "is_primary": form.get("is_primary") == "on",
        "is_active": form.get("is_active") == "on",
    }


def _contact_to_form_data(contact: Contact) -> dict:
    return {
        "first_name": contact.first_name or "",
        "last_name": contact.last_name or "",
        "title": contact.title or "",
        "email": contact.email or "",
        "phone": contact.phone or "",
        "notes": contact.notes or "",
        "is_primary": contact.is_primary,
        "is_active": contact.is_active,
    }


def _validate_contact_form(form_data: dict) -> str | None:
    has_identifying_value = any(
        [
            form_data["first_name"],
            form_data["last_name"],
            form_data["title"],
            form_data["email"],
            form_data["phone"],
        ]
    )
    if not has_identifying_value:
        return "Enter at least a name, title, email, or phone to save a contact."
    return None


def _partner_type_choices() -> list[str]:
    return list(PARTNER_TYPE_OPTIONS)


def _normalize_legacy_partner_categories() -> int:
    invalid_partners = db.session.scalars(
        select(Partner).where(
            Partner.partner_type.is_not(None),
            Partner.partner_type != "",
            Partner.partner_type.notin_(PARTNER_TYPE_OPTIONS),
        )
    ).all()

    for partner in invalid_partners:
        partner.partner_type = PARTNER_TYPE_NEEDS_REVIEW

    if invalid_partners:
        db.session.commit()

    return len(invalid_partners)


def _person_form_data(form=None) -> dict:
    if form is None:
        return {
            "first_name": "",
            "middle_initial": "",
            "last_name": "",
            "preferred_name": "",
            "email": "",
            "mobile_phone": "",
            "other_phone": "",
            "committee_role": "",
            "notes": "",
            "is_active": True,
        }

    return {
        "first_name": (form.get("first_name") or "").strip(),
        "middle_initial": (form.get("middle_initial") or "").strip(),
        "last_name": (form.get("last_name") or "").strip(),
        "preferred_name": (form.get("preferred_name") or "").strip(),
        "email": (form.get("email") or "").strip(),
        "mobile_phone": (form.get("mobile_phone") or "").strip(),
        "other_phone": (form.get("other_phone") or "").strip(),
        "committee_role": (form.get("committee_role") or "").strip(),
        "notes": (form.get("notes") or "").strip(),
        "is_active": form.get("is_active") == "on",
    }


def _person_to_form_data(person: Person) -> dict:
    return {
        "first_name": person.first_name or "",
        "middle_initial": person.middle_initial or "",
        "last_name": person.last_name or "",
        "preferred_name": person.preferred_name or "",
        "email": person.email or "",
        "mobile_phone": person.mobile_phone or person.phone or "",
        "other_phone": person.other_phone or "",
        "committee_role": person.committee_role or "",
        "notes": person.person_notes or "",
        "is_active": person.is_active,
    }


def _validate_person_form(form_data: dict) -> tuple[str | None, dict]:
    first_name = form_data["first_name"]
    if not first_name:
        return "First name is required.", {}

    last_name = form_data["last_name"]
    if not last_name:
        return "Last name is required.", {}

    middle_initial = _empty_to_none(form_data["middle_initial"])
    if middle_initial:
        middle_initial = middle_initial[0].upper()

    preferred_name = _empty_to_none(form_data["preferred_name"])
    email = _empty_to_none(form_data["email"])
    mobile_phone = _empty_to_none(form_data["mobile_phone"])
    other_phone = _empty_to_none(form_data["other_phone"])
    committee_role = _empty_to_none(form_data["committee_role"])
    notes = _empty_to_none(form_data["notes"])
    primary_phone = mobile_phone or other_phone

    return (
        None,
        {
            "first_name": first_name,
            "middle_initial": middle_initial,
            "last_name": last_name,
            "preferred_name": preferred_name,
            "email": email,
            "phone": primary_phone,
            "mobile_phone": mobile_phone,
            "other_phone": other_phone,
            "committee_role": committee_role,
            "person_notes": notes,
            "is_active": form_data["is_active"],
        },
    )


def _solicitation_form_options() -> tuple[list[Campaign], list[Partner]]:
    campaigns = db.session.scalars(
        select(Campaign).order_by(Campaign.campaign_year.desc())
    ).all()
    partners = db.session.scalars(
        select(Partner).order_by(Partner.partner_name.asc())
    ).all()
    return campaigns, partners


def _solicitation_form_options_for_create(
    selected_campaign_id: int | None,
) -> tuple[list[Campaign], list[Partner]]:
    campaigns = db.session.scalars(
        select(Campaign)
        .where(Campaign.status != "closed")
        .order_by(Campaign.campaign_year.desc())
    ).all()

    if selected_campaign_id is None:
        partners = db.session.scalars(
            select(Partner).order_by(Partner.partner_name.asc())
        ).all()
        return campaigns, partners

    available_partner_ids = _available_partner_ids_for_campaign(selected_campaign_id)
    partners = db.session.scalars(
        select(Partner)
        .where(Partner.id.in_(available_partner_ids))
        .order_by(Partner.partner_name.asc())
    ).all()
    return campaigns, partners


def _solicitation_form_data(form=None) -> dict:
    if form is None:
        return {
            "campaign_id": None,
            "partner_id": None,
            "solicitor_person_id": None,
            "mrpoc_person_id": None,
            "tranche": 1,
            "business_volume": "",
            "amount_requested": "",
            "amount_received": "",
            "status": "not_contacted",
            "notes": "",
        }

    return {
        "campaign_id": _safe_int(form.get("campaign_id")),
        "partner_id": _safe_int(form.get("partner_id")),
        "solicitor_person_id": _safe_int(form.get("solicitor_person_id")),
        "mrpoc_person_id": _safe_int(form.get("mrpoc_person_id")),
        "tranche": _safe_int(form.get("tranche")),
        "business_volume": (form.get("business_volume") or "").strip(),
        "amount_requested": (form.get("amount_requested") or "").strip(),
        "amount_received": (form.get("amount_received") or "").strip(),
        "status": (form.get("status") or "not_contacted").strip(),
        "notes": _empty_to_none(form.get("notes")),
    }


def _solicitation_to_form_data(solicitation: Solicitation) -> dict:
    return {
        "campaign_id": solicitation.campaign_id,
        "partner_id": solicitation.partner_id,
        "solicitor_person_id": solicitation.solicitor_person_id,
        "mrpoc_person_id": solicitation.mrpoc_person_id,
        "tranche": solicitation.tranche,
        "business_volume": _money_for_form(solicitation.business_volume),
        "amount_requested": _money_for_form(solicitation.amount_requested),
        "amount_received": _money_for_form(solicitation.amount_received),
        "status": solicitation.status,
        "notes": solicitation.notes or "",
    }


def _validate_solicitation_form(
    form_data: dict,
    solicitation_id: int | None = None,
    allow_closed_campaign: bool = False,
) -> tuple[str | None, dict]:
    campaign_id = form_data["campaign_id"]
    if campaign_id is None:
        return "Campaign is required.", {}
    campaign = db.session.get(Campaign, campaign_id)
    if campaign is None:
        return "Please select a valid campaign.", {}
    if not allow_closed_campaign and campaign.status == "closed":
        return "Closed campaigns are not available for new solicitations.", {}

    partner_id = form_data["partner_id"]
    if partner_id is None:
        return "Partner is required.", {}
    if db.session.get(Partner, partner_id) is None:
        return "Please select a valid partner.", {}

    solicitor_person_id = form_data["solicitor_person_id"]
    if solicitor_person_id is not None and db.session.get(Person, solicitor_person_id) is None:
        return "Please select a valid solicitor.", {}

    mrpoc_person_id = form_data["mrpoc_person_id"]
    if mrpoc_person_id is not None and db.session.get(Person, mrpoc_person_id) is None:
        return "Please select a valid MRPOC.", {}

    tranche = form_data["tranche"]
    if tranche not in SOLICITATION_TRANCHE_OPTIONS:
        return "Please select a valid tranche.", {}

    status = form_data["status"]
    if status not in SOLICITATION_STATUS_OPTIONS:
        return "Please select a valid solicitation status.", {}

    business_volume, error = _parse_money(form_data["business_volume"])
    if error:
        return f"Business volume {error}", {}

    amount_requested, error = _parse_money(form_data["amount_requested"])
    if error:
        return f"Amount requested {error}", {}

    amount_received, error = _parse_money(form_data["amount_received"])
    if error:
        return f"Amount received {error}", {}

    existing_solicitation = db.session.scalar(
        select(Solicitation).where(
            Solicitation.partner_id == partner_id,
            Solicitation.campaign_id == campaign_id,
        )
    )
    if existing_solicitation and existing_solicitation.id != solicitation_id:
        return "This partner is already assigned to the selected campaign.", {}

    return (
        None,
        {
            "campaign_id": campaign_id,
            "partner_id": partner_id,
            "solicitor_person_id": solicitor_person_id,
            "mrpoc_person_id": mrpoc_person_id,
            "tranche": tranche,
            "business_volume": business_volume,
            "amount_requested": amount_requested,
            "amount_received": amount_received,
            "status": status,
            "notes": form_data["notes"],
        },
    )


def _parse_money(value: str) -> tuple[Decimal | None, str | None]:
    if not value:
        return None, None

    normalized = value.replace(",", "").replace("$", "").strip()
    if not normalized:
        return None, None

    try:
        parsed = Decimal(normalized)
    except InvalidOperation:
        return None, "must be a valid dollar value."

    if parsed < 0:
        return None, "cannot be negative."

    return parsed, None


def _money_for_form(value) -> str:
    if value is None:
        return ""
    return f"{value:.2f}"


def _default_active_campaign_id() -> int | None:
    active_campaigns = db.session.scalars(
        select(Campaign.id).where(Campaign.status == "active")
    ).all()
    if len(active_campaigns) == 1:
        return active_campaigns[0]
    return None


def _person_options() -> list[Person]:
    return db.session.scalars(
        select(Person).order_by(
            Person.is_active.desc(),
            Person.last_name.asc(),
            Person.first_name.asc(),
            Person.id.asc(),
        )
    ).all()


def _solicitation_return_to_value() -> str | None:
    value = request.args.get("return_to")
    if value is None:
        value = request.form.get("return_to")

    if value == "campaign":
        return "campaign"
    return None


def _available_partner_ids_for_campaign(campaign_id: int) -> list[int]:
    assigned_partner_ids = db.session.scalars(
        select(Solicitation.partner_id).where(Solicitation.campaign_id == campaign_id)
    ).all()

    query = select(Partner.id)
    if assigned_partner_ids:
        query = query.where(Partner.id.notin_(assigned_partner_ids))

    return db.session.scalars(query).all()


def _available_partners_for_campaign(campaign_id: int) -> list[Partner]:
    available_partner_ids = _available_partner_ids_for_campaign(campaign_id)
    if not available_partner_ids:
        return []

    return db.session.scalars(
        select(Partner)
        .where(Partner.id.in_(available_partner_ids))
        .order_by(Partner.partner_name.asc())
    ).all()


def _campaign_tranche_solicitations(campaign_id: int) -> dict[int, list[Solicitation]]:
    solicitations = db.session.scalars(
        select(Solicitation)
        .options(
            selectinload(Solicitation.partner),
            selectinload(Solicitation.solicitor),
            selectinload(Solicitation.mrpoc),
        )
        .join(Solicitation.partner)
        .where(Solicitation.campaign_id == campaign_id)
        .order_by(Solicitation.tranche.asc(), Partner.partner_name.asc(), Solicitation.id.asc())
    ).all()

    tranche_map = {1: [], 2: [], 3: []}
    for solicitation in solicitations:
        if solicitation.tranche in tranche_map:
            tranche_map[solicitation.tranche].append(solicitation)
    return tranche_map


def _campaign_category_mrpoc_map(campaign_id: int) -> dict[str, CampaignCategoryMRPOC]:
    mappings = db.session.scalars(
        select(CampaignCategoryMRPOC)
        .options(selectinload(CampaignCategoryMRPOC.mrpoc))
        .where(CampaignCategoryMRPOC.campaign_id == campaign_id)
    ).all()
    return {mapping.partner_category: mapping for mapping in mappings}


def _campaign_mrpoc_person_id_for_partner_category(
    campaign_id: int, partner_category: str | None
) -> int | None:
    if not partner_category:
        return None
    mapping = db.session.scalar(
        select(CampaignCategoryMRPOC.mrpoc_person_id).where(
            CampaignCategoryMRPOC.campaign_id == campaign_id,
            CampaignCategoryMRPOC.partner_category == partner_category,
        )
    )
    return mapping
