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
    send_file,
    session,
    url_for,
)
from flask_login import current_user
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.auth.permissions import editor_required
from app.main.letter_service import (
    AcknowledgementLetterError,
    SolicitationLetterError,
    acknowledgement_missing_fields,
    build_acknowledgement_letter_context_for_solicitation,
    build_solicitation_mailing_list_text,
    build_solicitation_letter_context_for_solicitation,
    generate_acknowledgement_pdf_bytes,
    generate_solicitation_pdf_bytes,
)
from app.main.letter_storage import (
    acknowledgement_letter_path,
    list_generated_acknowledgement_letter_files,
    list_generated_mailing_list_files,
    list_generated_solicitation_letter_files,
    mailing_list_path_for_filename,
    save_acknowledgement_letter_pdf,
    save_generated_mailing_list,
    save_solicitation_letter_pdf,
    solicitation_letter_path,
)
from app.main.status import (
    partner_is_incomplete,
    partner_readiness_summary,
    solicitation_is_incomplete,
    solicitation_is_letter_ready,
)
from app.main.solicitation_status import (
    SOLICITATION_STATUS_OPTIONS,
    canonical_solicitation_status,
    solicitation_status_for_storage,
)
from app.main.solicitation_workflow import SolicitationWorkflowService
from app.main import bp
from app.extensions import db
from app.reports.registry import get_report, list_reports
from app.reports.report_service import (
    ReportGenerationError,
    generate_report_pdf,
    report_pdf_exists,
    report_pdf_filename,
    report_pdf_path,
)
from app.services.dashboard_stats import (
    campaign_detail_stats,
    campaign_stats,
    dashboard_highlights,
    partner_stats,
    people_stats,
    solicitation_stats,
)
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
SOLICITATION_REQUESTED_AMOUNT_VALUES = (
    Decimal("500"),
    Decimal("1000"),
    Decimal("2500"),
    Decimal("5000"),
    Decimal("10000"),
)
SOLICITATION_REQUESTED_AMOUNT_OPTIONS = tuple(
    (f"{amount:.2f}", f"${amount:,.0f}")
    for amount in SOLICITATION_REQUESTED_AMOUNT_VALUES
)
PARTNER_ACTIVE_ONLY_SESSION_KEY = "active_partners_only"
REPORT_CAMPAIGN_SESSION_KEY = "active_report_campaign_id"


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
    highlights = dashboard_highlights()
    return render_template("index.html", page_title="Home", highlights=highlights)


@bp.get("/letters")
def letter_list():
    solicitor_filter_people, selected_solicitor_id = _selected_solicitor_filter()
    tranche_filter_options, selected_tranche = _selected_tranche_filter()

    solicitations = _letter_solicitation_options(
        selected_solicitor_id=selected_solicitor_id,
        selected_tranche=selected_tranche,
    )
    incomplete_solicitation_ids = {
        solicitation.id
        for solicitation in solicitations
        if solicitation_is_incomplete(solicitation)
    }
    letter_ready_solicitation_ids = {
        solicitation.id
        for solicitation in solicitations
        if solicitation_is_letter_ready(solicitation)
    }
    letter_editable_solicitation_ids = {
        solicitation.id
        for solicitation in solicitations
        if SolicitationWorkflowService.can_edit_solicitation_letter(solicitation)
    }
    acknowledgement_eligible_solicitation_ids = {
        solicitation.id
        for solicitation in solicitations
        if canonical_solicitation_status(solicitation.status) == "gift_received"
        and not acknowledgement_missing_fields(solicitation)
    }
    acknowledgement_missing_by_solicitation_id = {
        solicitation.id: acknowledgement_missing_fields(solicitation)
        for solicitation in solicitations
        if canonical_solicitation_status(solicitation.status) == "gift_received"
        and acknowledgement_missing_fields(solicitation)
    }
    solicitations = sorted(
        solicitations,
        key=lambda solicitation: solicitation.id not in incomplete_solicitation_ids,
    )

    generated_solicitation_letters = _generated_solicitation_letter_rows(
        selected_solicitor_id=selected_solicitor_id
    )
    generated_acknowledgement_letters = _generated_acknowledgement_letter_rows(
        selected_solicitor_id=selected_solicitor_id
    )
    generated_mailing_lists = _generated_mailing_list_rows()

    return render_template(
        "letters/list.html",
        page_title="Letters",
        solicitations=solicitations,
        incomplete_solicitation_ids=incomplete_solicitation_ids,
        letter_ready_solicitation_ids=letter_ready_solicitation_ids,
        letter_editable_solicitation_ids=letter_editable_solicitation_ids,
        acknowledgement_eligible_solicitation_ids=acknowledgement_eligible_solicitation_ids,
        acknowledgement_missing_by_solicitation_id=acknowledgement_missing_by_solicitation_id,
        generated_solicitation_letters=generated_solicitation_letters,
        generated_acknowledgement_letters=generated_acknowledgement_letters,
        generated_mailing_lists=generated_mailing_lists,
        solicitor_filter_people=solicitor_filter_people,
        selected_solicitor_id=selected_solicitor_id,
        tranche_filter_options=tranche_filter_options,
        selected_tranche=selected_tranche,
    )


@bp.get("/letters/solicitation.pdf")
def letter_solicitation_pdf():
    solicitation_id = _safe_int(request.args.get("solicitation_id"))
    selected_solicitor_id = _safe_int(request.args.get("solicitor_id"))
    if solicitation_id is None:
        flash("Please select a solicitation to generate a letter.", "danger")
        return redirect(url_for("main.letter_list", solicitor_id=selected_solicitor_id))

    solicitation = db.session.scalar(
        select(Solicitation)
        .options(
            selectinload(Solicitation.partner),
            selectinload(Solicitation.solicitor),
            selectinload(Solicitation.mrpoc),
            selectinload(Solicitation.campaign),
        )
        .where(Solicitation.id == solicitation_id)
    )
    if solicitation is None:
        flash("Solicitation not found.", "danger")
        return redirect(url_for("main.letter_list", solicitor_id=selected_solicitor_id))

    if not solicitation_is_letter_ready(solicitation):
        flash("Solicitation is incomplete. Update solicitation details before generating a letter.", "warning")
        edit_kwargs = {"solicitation_id": solicitation.id}
        if selected_solicitor_id is not None:
            edit_kwargs["solicitor_id"] = selected_solicitor_id
        return redirect(url_for("main.solicitation_edit", **edit_kwargs))

    if not SolicitationWorkflowService.can_edit_solicitation_letter(solicitation):
        flash("Solicitation letter is archived and cannot be regenerated.", "warning")
        return redirect(
            url_for(
                "main.letter_list",
                solicitor_id=selected_solicitor_id
                if selected_solicitor_id is not None
                else solicitation.solicitor_person_id,
            )
        )

    try:
        context = build_solicitation_letter_context_for_solicitation(solicitation_id)
        pdf_bytes = generate_solicitation_pdf_bytes(context)
        output_path = save_solicitation_letter_pdf(solicitation.id, pdf_bytes)
    except SolicitationLetterError as exc:
        current_app.logger.exception("Solicitation letter generation failed: %s", exc)
        flash("Unable to generate solicitation PDF. Check partner/contact data and try again.", "danger")
        return redirect(url_for("main.letter_list", solicitor_id=solicitation.solicitor_person_id))

    flash(f"Generated {output_path.name}.", "success")
    return redirect(
        url_for(
            "main.letter_list",
            solicitor_id=selected_solicitor_id if selected_solicitor_id is not None else solicitation.solicitor_person_id,
        )
    )


@bp.get("/letters/generated/solicitation/<int:solicitation_id>.pdf")
def letter_generated_solicitation_pdf(solicitation_id: int):
    output_path = solicitation_letter_path(solicitation_id)
    if not output_path.exists():
        flash("Generated solicitation letter not found.", "warning")
        return redirect(url_for("main.letter_list"))

    return send_file(
        output_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=output_path.name,
    )


@bp.get("/letters/acknowledgement.pdf")
def letter_acknowledgement_pdf():
    solicitation_id = _safe_int(request.args.get("solicitation_id"))
    selected_solicitor_id = _safe_int(request.args.get("solicitor_id"))
    if solicitation_id is None:
        flash("Please select a solicitation to generate an acknowledgement.", "danger")
        return redirect(url_for("main.letter_list", solicitor_id=selected_solicitor_id))

    solicitation = db.session.scalar(
        select(Solicitation)
        .options(
            selectinload(Solicitation.partner).selectinload(Partner.contacts),
            selectinload(Solicitation.mrpoc),
        )
        .where(Solicitation.id == solicitation_id)
    )
    if solicitation is None:
        flash("Solicitation not found.", "danger")
        return redirect(url_for("main.letter_list", solicitor_id=selected_solicitor_id))
    if canonical_solicitation_status(solicitation.status) != "gift_received":
        flash("Acknowledgements can be generated only for Gift Received solicitations.", "warning")
        return redirect(url_for("main.letter_list", solicitor_id=selected_solicitor_id))

    missing = acknowledgement_missing_fields(solicitation)
    if missing:
        flash(
            "Acknowledgement is incomplete. Add: " + ", ".join(missing) + ".",
            "warning",
        )
        return redirect(url_for("main.letter_list", solicitor_id=selected_solicitor_id))

    try:
        context = build_acknowledgement_letter_context_for_solicitation(solicitation.id)
        pdf_bytes = generate_acknowledgement_pdf_bytes(context)
        output_path = save_acknowledgement_letter_pdf(solicitation.id, pdf_bytes)
    except AcknowledgementLetterError as exc:
        current_app.logger.exception("Acknowledgement generation failed: %s", exc)
        flash("Unable to generate acknowledgement PDF. Check required data and assets.", "danger")
        return redirect(url_for("main.letter_list", solicitor_id=selected_solicitor_id))

    flash(f"Generated {output_path.name}.", "success")
    return redirect(
        url_for(
            "main.letter_list",
            solicitor_id=selected_solicitor_id
            if selected_solicitor_id is not None
            else solicitation.solicitor_person_id,
        )
    )


@bp.get("/letters/generated/acknowledgement/<int:solicitation_id>.pdf")
def letter_generated_acknowledgement_pdf(solicitation_id: int):
    output_path = acknowledgement_letter_path(solicitation_id)
    if not output_path.exists():
        flash("Generated acknowledgement not found.", "warning")
        return redirect(url_for("main.letter_list"))
    return send_file(
        output_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=output_path.name,
    )


@bp.post("/letters/mailing-list")
def letter_generate_mailing_list():
    selected_solicitor_id = _safe_int(request.form.get("solicitor_id"))
    selected_tranche = _safe_int(request.form.get("tranche"))
    visible_solicitations = _letter_solicitation_options(
        selected_solicitor_id=selected_solicitor_id,
        selected_tranche=selected_tranche,
    )
    incomplete_solicitation_ids = {
        solicitation.id
        for solicitation in visible_solicitations
        if solicitation_is_incomplete(solicitation)
    }
    visible_solicitations = sorted(
        visible_solicitations,
        key=lambda solicitation: solicitation.id not in incomplete_solicitation_ids,
    )
    ready_solicitation_ids = [
        solicitation.id
        for solicitation in visible_solicitations
        if solicitation_is_letter_ready(solicitation)
    ]
    if not ready_solicitation_ids:
        flash("No ready solicitations are available for mailing-list generation.", "warning")
        return redirect(url_for("main.letter_list", solicitor_id=selected_solicitor_id, tranche=selected_tranche))

    ready_solicitations = db.session.scalars(
        select(Solicitation)
        .options(selectinload(Solicitation.partner).selectinload(Partner.contacts))
        .where(Solicitation.id.in_(ready_solicitation_ids))
    ).all()
    ready_by_id = {solicitation.id: solicitation for solicitation in ready_solicitations}
    ready_solicitations = [
        ready_by_id[solicitation_id]
        for solicitation_id in ready_solicitation_ids
        if solicitation_id in ready_by_id
    ]
    if not ready_solicitations:
        flash("No ready solicitations are available for mailing-list generation.", "warning")
        return redirect(url_for("main.letter_list", solicitor_id=selected_solicitor_id, tranche=selected_tranche))

    mailing_list_text = build_solicitation_mailing_list_text(ready_solicitations)
    output_path = save_generated_mailing_list(mailing_list_text)
    flash(f"Generated mailing list {output_path.name}.", "success")
    return redirect(url_for("main.letter_list", solicitor_id=selected_solicitor_id, tranche=selected_tranche))


@bp.get("/letters/generated/mailing-lists/<path:filename>")
def letter_generated_mailing_list_view(filename: str):
    output_path = mailing_list_path_for_filename(filename)
    if output_path is None or not output_path.exists():
        flash("Generated mailing list not found.", "warning")
        return redirect(url_for("main.letter_list"))

    return send_file(
        output_path,
        mimetype="text/plain",
        as_attachment=False,
        download_name=output_path.name,
    )


@bp.get("/letters/generated/mailing-lists/<path:filename>/download")
def letter_generated_mailing_list_download(filename: str):
    output_path = mailing_list_path_for_filename(filename)
    if output_path is None or not output_path.exists():
        flash("Generated mailing list not found.", "warning")
        return redirect(url_for("main.letter_list"))

    return send_file(
        output_path,
        mimetype="text/plain",
        as_attachment=True,
        download_name=output_path.name,
    )


@bp.post("/letters/generated/mailing-lists/<path:filename>/delete")
def letter_generated_mailing_list_delete(filename: str):
    output_path = mailing_list_path_for_filename(filename)
    if output_path is None:
        flash("Generated mailing list not found.", "warning")
        return redirect(url_for("main.letter_list"))

    if not output_path.exists() or not output_path.is_file():
        flash("Generated mailing list not found.", "warning")
        return redirect(url_for("main.letter_list"))

    output_path.unlink()
    flash(f"Deleted mailing list {output_path.name}.", "success")
    return redirect(url_for("main.letter_list"))


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
    stats = campaign_stats()
    return render_template(
        "campaigns/list.html",
        page_title="Campaigns",
        campaigns=campaigns,
        active_count=active_count,
        stats=stats,
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
    detail_stats = campaign_detail_stats(campaign.id)
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
        detail_stats=detail_stats,
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
    active_only = _partner_active_only_selection()
    query = select(Partner)
    if active_only:
        query = query.where(Partner.is_active.is_(True))

    partners = db.session.scalars(query).all()
    partners = sorted(
        partners,
        key=lambda partner: (
            not partner_is_incomplete(partner),
            _partner_sort_name(partner),
            partner.id,
        ),
    )
    incomplete_partner_count = sum(1 for partner in partners if partner_is_incomplete(partner))
    incomplete_partner_ids = {
        partner.id
        for partner in partners
        if partner_is_incomplete(partner)
    }
    stats = partner_stats(active_only=active_only)
    return render_template(
        "partners/list.html",
        page_title="Partners",
        partners=partners,
        incomplete_partner_count=incomplete_partner_count,
        incomplete_partner_ids=incomplete_partner_ids,
        stats=stats,
        active_only=active_only,
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
    stats = people_stats()
    return render_template(
        "people/list.html",
        page_title="People",
        people=people,
        stats=stats,
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


@bp.get("/solicitations/clear-filter")
def solicitation_clear_filter():
    session.pop("active_solicitor_id", None)
    session.pop("active_tranche", None)
    return redirect(url_for("main.solicitation_list"))


@bp.get("/letters/clear-filter")
def letter_clear_filter():
    session.pop("active_solicitor_id", None)
    session.pop("active_tranche", None)
    return redirect(url_for("main.letter_list"))


@bp.get("/reports")
def report_list():
    campaigns = _report_campaign_options()
    selected_campaign = _selected_report_campaign(campaigns)
    reports = list_reports()
    report_rows = []

    if selected_campaign is not None:
        report_rows = [
            {
                "definition": report,
                "filename": report_pdf_filename(report, selected_campaign),
                "is_available": report_pdf_exists(report, selected_campaign),
            }
            for report in reports
        ]

    return render_template(
        "reports/list.html",
        page_title="Reports",
        campaigns=campaigns,
        selected_campaign=selected_campaign,
        report_rows=report_rows,
    )


@bp.post("/reports/<report_id>/generate")
def report_generate(report_id: str):
    report = get_report(report_id)
    if report is None:
        abort(404)

    campaign = _selected_report_campaign(_report_campaign_options())
    if campaign is None:
        flash("Please select a campaign before generating a report.", "warning")
        return redirect(url_for("main.report_list"))

    try:
        output_path = generate_report_pdf(report, campaign)
    except ReportGenerationError as exc:
        current_app.logger.exception("Report generation failed: %s", exc)
        flash(f"Unable to generate {report.label}. Check report data and try again.", "danger")
        return redirect(url_for("main.report_list"))

    flash(f"Generated {output_path.name}.", "success")
    return redirect(url_for("main.report_list"))


@bp.get("/reports/<report_id>/pdf")
def report_pdf(report_id: str):
    report = get_report(report_id)
    if report is None:
        abort(404)

    campaign = _selected_report_campaign(_report_campaign_options(), update_session=False)
    if campaign is None:
        flash("Please select a campaign before viewing a report.", "warning")
        return redirect(url_for("main.report_list"))

    output_path = report_pdf_path(report, campaign)
    if not output_path.is_file():
        flash(f"{report.label} has not been generated for the selected campaign.", "warning")
        return redirect(url_for("main.report_list"))

    return send_file(
        output_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=output_path.name,
    )


@bp.get("/solicitations")
def solicitation_list():
    solicitor_filter_people, selected_solicitor_id = _selected_solicitor_filter()
    tranche_filter_options, selected_tranche = _selected_tranche_filter()

    partner_sort_name = func.coalesce(func.nullif(Partner.display_name, ""), Partner.partner_name)
    query = (
        select(Solicitation)
        .options(
            selectinload(Solicitation.campaign),
            selectinload(Solicitation.partner),
            selectinload(Solicitation.solicitor),
            selectinload(Solicitation.mrpoc),
        )
        .join(Solicitation.campaign)
        .join(Solicitation.partner)
    )
    if selected_solicitor_id is not None:
        query = query.where(Solicitation.solicitor_person_id == selected_solicitor_id)
    if selected_tranche is not None:
        query = query.where(Solicitation.tranche == selected_tranche)

    solicitations = db.session.scalars(
        query.order_by(
            Solicitation.tranche.asc(),
            partner_sort_name.asc(),
            Campaign.campaign_year.desc(),
            Solicitation.id.asc(),
        )
    ).all()
    from app.main.status import solicitation_is_ready as _sol_is_ready  # noqa: PLC0415
    from app.main.status import partner_is_incomplete as _partner_incomplete  # noqa: PLC0415
    incomplete_partner_ids = {
        solicitation.id
        for solicitation in solicitations
        if _partner_incomplete(getattr(solicitation, "partner", None))
    }
    incomplete_solicitation_ids = {
        solicitation.id
        for solicitation in solicitations
        if not _sol_is_ready(solicitation)
    }
    letter_ready_solicitation_ids = {
        solicitation.id
        for solicitation in solicitations
        if solicitation_is_letter_ready(solicitation)
    }
    solicitations = sorted(
        solicitations,
        key=lambda solicitation: solicitation.id not in incomplete_solicitation_ids,
    )
    stats = solicitation_stats()
    return render_template(
        "solicitations/list.html",
        page_title="Solicitations",
        solicitations=solicitations,
        incomplete_partner_ids=incomplete_partner_ids,
        incomplete_solicitation_ids=incomplete_solicitation_ids,
        letter_ready_solicitation_ids=letter_ready_solicitation_ids,
        solicitor_filter_people=solicitor_filter_people,
        selected_solicitor_id=selected_solicitor_id,
        tranche_filter_options=tranche_filter_options,
        selected_tranche=selected_tranche,
        stats=stats,
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
        requested_amount_options=SOLICITATION_REQUESTED_AMOUNT_OPTIONS,
        status_options=SOLICITATION_STATUS_OPTIONS,
    )


@bp.get("/solicitations/<int:solicitation_id>")
def solicitation_detail(solicitation_id: int):
    solicitation = db.get_or_404(Solicitation, solicitation_id)
    return_to = _solicitation_return_to_value()
    solicitor_id = _solicitation_filter_solicitor_id()
    primary_contact = _primary_contact_for_solicitation(solicitation)
    return render_template(
        "solicitations/detail.html",
        page_title=f"Solicitation #{solicitation.id}",
        solicitation=solicitation,
        return_to=return_to,
        solicitor_id=solicitor_id,
        primary_contact=primary_contact,
    )


@bp.route("/solicitations/<int:solicitation_id>/edit", methods=["GET", "POST"])
@editor_required
def solicitation_edit(solicitation_id: int):
    solicitation = db.get_or_404(Solicitation, solicitation_id)
    form_data = _solicitation_to_form_data(solicitation)
    campaigns, partners = _solicitation_form_options()
    solicitors = _person_options()
    return_to = _solicitation_return_to_value()
    solicitor_id = _solicitation_filter_solicitor_id()
    primary_contact = _primary_contact_for_solicitation(solicitation)
    contact_form_data = _contact_to_form_data(primary_contact) if primary_contact else _contact_form_data()

    if request.method == "POST":
        form_data = _solicitation_form_data(request.form)
        validation_error, clean_data = _validate_solicitation_form(
            form_data, solicitation_id=solicitation.id, allow_closed_campaign=True
        )
        if validation_error:
            flash(validation_error, "danger")
        else:
            for key, value in clean_data.items():
                if key == "status":
                    continue
                setattr(solicitation, key, value)
            SolicitationWorkflowService.update_status(solicitation, clean_data["status"])
            if primary_contact is not None:
                raw_contact = _contact_form_data(request.form)
                _contact_err, normalized_contact = _validate_contact_form(raw_contact)
                if not _contact_err:
                    for key in ("first_name", "middle_initial", "last_name", "title", "email", "phone"):
                        setattr(primary_contact, key, normalized_contact[key])
            db.session.commit()
            flash("Solicitation updated.", "success")
            redirect_kwargs = {"solicitation_id": solicitation.id}
            if return_to == "campaign":
                redirect_kwargs["return_to"] = "campaign"
            if solicitor_id is not None:
                redirect_kwargs["solicitor_id"] = solicitor_id
            return redirect(url_for("main.solicitation_detail", **redirect_kwargs))
        primary_contact = _primary_contact_for_solicitation(solicitation)
        contact_form_data = _contact_form_data(request.form)

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
        solicitor_id=solicitor_id,
        tranche_options=SOLICITATION_TRANCHE_OPTIONS,
        requested_amount_options=SOLICITATION_REQUESTED_AMOUNT_OPTIONS,
        status_options=SOLICITATION_STATUS_OPTIONS,
        primary_contact=primary_contact,
        contact_form_data=contact_form_data,
    )


@bp.get("/solicitations/<int:solicitation_id>/delete")
@editor_required
def solicitation_delete_confirm(solicitation_id: int):
    solicitation = db.get_or_404(Solicitation, solicitation_id)
    if not solicitation.can_delete:
        flash("This solicitation cannot be deleted.", "warning")
        return redirect(url_for("main.solicitation_edit", solicitation_id=solicitation_id))
    return render_template(
        "solicitations/confirm_delete.html",
        page_title=f"Delete Solicitation #{solicitation.id}",
        solicitation=solicitation,
    )


@bp.post("/solicitations/<int:solicitation_id>/delete")
@editor_required
def solicitation_delete(solicitation_id: int):
    solicitation = db.get_or_404(Solicitation, solicitation_id)
    if not solicitation.can_delete:
        flash("This solicitation cannot be deleted.", "warning")
        return redirect(url_for("main.solicitation_edit", solicitation_id=solicitation_id))
    db.session.delete(solicitation)
    db.session.commit()
    flash("Solicitation deleted.", "success")
    return redirect(url_for("main.solicitation_list"))


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


@bp.route("/partners/<int:partner_id>/contacts/new", methods=["GET", "POST"])
@editor_required
def partner_contact_create(partner_id: int):
    partner = db.get_or_404(Partner, partner_id)
    return_to_solicitation = _safe_int(
        request.args.get("return_to_solicitation") or request.form.get("return_to_solicitation")
    )

    if request.method == "GET":
        form_data = _contact_form_data()
        form_data["is_primary"] = True
        return render_template(
            "partners/contact_form.html",
            page_title=f"Add Contact — {partner.partner_name}",
            partner=partner,
            form_data=form_data,
            return_to_solicitation=return_to_solicitation,
        )

    contact_form_data = _contact_form_data(request.form)
    validation_error, normalized_contact_data = _validate_contact_form(contact_form_data)

    if validation_error:
        flash(validation_error, "danger")
        if return_to_solicitation is not None:
            return render_template(
                "partners/contact_form.html",
                page_title=f"Add Contact — {partner.partner_name}",
                partner=partner,
                form_data=contact_form_data,
                return_to_solicitation=return_to_solicitation,
            )
        return _render_partner_detail(
            partner=partner,
            contact_form_data=contact_form_data,
            editing_contact=None,
        )

    if normalized_contact_data["is_primary"]:
        _unset_other_primary_contacts(partner.id)

    contact = Contact(
        partner_id=partner.id,
        first_name=normalized_contact_data["first_name"],
        middle_initial=normalized_contact_data["middle_initial"],
        last_name=normalized_contact_data["last_name"],
        title=normalized_contact_data["title"],
        email=normalized_contact_data["email"],
        phone=normalized_contact_data["phone"],
        notes=normalized_contact_data["notes"],
        is_primary=normalized_contact_data["is_primary"],
        is_active=normalized_contact_data["is_active"],
    )
    db.session.add(contact)

    db.session.commit()
    flash("Contact added.", "success")
    if return_to_solicitation is not None:
        return redirect(
            url_for("main.solicitation_edit", solicitation_id=return_to_solicitation)
        )
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
        validation_error, normalized_contact_data = _validate_contact_form(contact_form_data)

        if validation_error:
            flash(validation_error, "danger")
            return _render_partner_detail(
                partner=partner,
                contact_form_data=_contact_form_data(),
                editing_contact=contact,
                edit_form_data=contact_form_data,
            )

        for key in (
            "first_name",
            "middle_initial",
            "last_name",
            "title",
            "email",
            "phone",
            "notes",
        ):
            setattr(contact, key, normalized_contact_data[key])
        contact.is_primary = normalized_contact_data["is_primary"]
        contact.is_active = normalized_contact_data["is_active"]

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
    readiness = partner_readiness_summary(partner)
    return render_template(
        "partners/detail.html",
        page_title=partner.partner_name,
        partner=partner,
        contacts=contacts,
        contact_form_data=contact_form_data,
        editing_contact=editing_contact,
        edit_form_data=edit_form_data or {},
        readiness=readiness,
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


def _slugify_filename_part(value: str) -> str:
    cleaned = "".join(character if character.isalnum() else "-" for character in value.lower())
    collapsed = "-".join(part for part in cleaned.split("-") if part)
    return collapsed or "partner"


def _contact_form_data(form=None) -> dict:
    if form is None:
        return {
            "first_name": "",
            "middle_initial": "",
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
        "middle_initial": (form.get("middle_initial") or "").strip(),
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
        "middle_initial": contact.middle_initial or "",
        "last_name": contact.last_name or "",
        "title": contact.title or "",
        "email": contact.email or "",
        "phone": contact.phone or "",
        "notes": contact.notes or "",
        "is_primary": contact.is_primary,
        "is_active": contact.is_active,
    }


def _validate_contact_form(form_data: dict) -> tuple[str | None, dict]:
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
        return "Enter at least a name, title, email, or phone to save a contact.", {}

    middle_initial = _empty_to_none(form_data["middle_initial"])
    if middle_initial:
        middle_initial = middle_initial[0].upper()

    return (
        None,
        {
            "first_name": form_data["first_name"],
            "middle_initial": middle_initial,
            "last_name": form_data["last_name"],
            "title": form_data["title"],
            "email": form_data["email"],
            "phone": form_data["phone"],
            "notes": form_data["notes"],
            "is_primary": form_data["is_primary"],
            "is_active": form_data["is_active"],
        },
    )


def _partner_type_choices() -> list[str]:
    return list(PARTNER_TYPE_OPTIONS)


def _letter_solicitation_options(
    selected_solicitor_id: int | None = None,
    selected_tranche: int | None = None,
) -> list[Solicitation]:
    partner_sort_name = func.coalesce(func.nullif(Partner.display_name, ""), Partner.partner_name)
    query = (
        select(Solicitation)
        .options(
            selectinload(Solicitation.partner).selectinload(Partner.contacts),
            selectinload(Solicitation.solicitor),
            selectinload(Solicitation.mrpoc),
            selectinload(Solicitation.campaign),
        )
        .join(Solicitation.partner)
    )
    if selected_solicitor_id is not None:
        query = query.where(Solicitation.solicitor_person_id == selected_solicitor_id)
    if selected_tranche is not None:
        query = query.where(Solicitation.tranche == selected_tranche)

    return db.session.scalars(
        query.order_by(partner_sort_name.asc(), Solicitation.id.asc())
    ).all()


def _tranche_filter_options() -> list[int]:
    rows = db.session.scalars(
        select(Solicitation.tranche).distinct().order_by(Solicitation.tranche.asc())
    ).all()
    return [t for t in rows if t is not None]


def _generated_solicitation_letter_rows(selected_solicitor_id: int | None = None) -> list[dict]:
    generated_files = list_generated_solicitation_letter_files()
    if not generated_files:
        return []

    solicitation_ids = [item.solicitation_id for item in generated_files]
    solicitation_query = (
        select(Solicitation)
        .options(selectinload(Solicitation.partner))
        .where(Solicitation.id.in_(solicitation_ids))
    )
    if selected_solicitor_id is not None:
        solicitation_query = solicitation_query.where(
            Solicitation.solicitor_person_id == selected_solicitor_id
        )

    solicitations = db.session.scalars(solicitation_query).all()
    solicitation_by_id = {solicitation.id: solicitation for solicitation in solicitations}

    rows = []
    for generated_file in generated_files:
        solicitation = solicitation_by_id.get(generated_file.solicitation_id)
        if selected_solicitor_id is not None and solicitation is None:
            continue
        partner = solicitation.partner if solicitation is not None else None
        rows.append(
            {
                "filename": generated_file.filename,
                "solicitation_id": generated_file.solicitation_id,
                "generated_at": generated_file.generated_at,
                "partner_name": (
                    (partner.display_name or partner.partner_name)
                    if partner is not None
                    else "—"
                ),
            }
        )

    return rows


def _generated_acknowledgement_letter_rows(
    selected_solicitor_id: int | None = None,
) -> list[dict]:
    generated_files = list_generated_acknowledgement_letter_files()
    if not generated_files:
        return []
    solicitation_ids = [item.solicitation_id for item in generated_files]
    query = (
        select(Solicitation)
        .options(selectinload(Solicitation.partner))
        .where(Solicitation.id.in_(solicitation_ids))
    )
    if selected_solicitor_id is not None:
        query = query.where(Solicitation.solicitor_person_id == selected_solicitor_id)
    solicitations = db.session.scalars(query).all()
    solicitation_by_id = {item.id: item for item in solicitations}
    rows = []
    for generated_file in generated_files:
        solicitation = solicitation_by_id.get(generated_file.solicitation_id)
        if selected_solicitor_id is not None and solicitation is None:
            continue
        partner = solicitation.partner if solicitation is not None else None
        rows.append(
            {
                "filename": generated_file.filename,
                "solicitation_id": generated_file.solicitation_id,
                "generated_at": generated_file.generated_at,
                "partner_name": (
                    (partner.display_name or partner.partner_name)
                    if partner is not None
                    else "—"
                ),
            }
        )
    return rows


def _generated_mailing_list_rows() -> list[dict]:
    files = list_generated_mailing_list_files()
    return [
        {
            "filename": item.filename,
            "created_at": item.created_at,
        }
        for item in files
    ]


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
            "amount_pledged": "0.00",
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
        "amount_pledged": (form.get("amount_pledged") or "").strip(),
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
        "amount_pledged": _money_for_form(solicitation.amount_pledged),
        "amount_received": _money_for_form(solicitation.amount_received),
        "status": canonical_solicitation_status(solicitation.status),
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

    status = canonical_solicitation_status(form_data["status"])
    if status not in SOLICITATION_STATUS_OPTIONS:
        return "Please select a valid solicitation status.", {}

    business_volume, error = _parse_money(form_data["business_volume"])
    if error:
        return f"Business volume {error}", {}

    amount_requested, error = _parse_money(form_data["amount_requested"])
    if error:
        return f"Amount requested {error}", {}
    if (
        amount_requested is not None
        and amount_requested not in SOLICITATION_REQUESTED_AMOUNT_VALUES
    ):
        return "Please select a permitted requested amount.", {}

    amount_pledged, error = _parse_money(form_data["amount_pledged"])
    if error:
        return f"Amount pledged {error}", {}

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
            "amount_pledged": amount_pledged if amount_pledged is not None else Decimal("0"),
            "amount_received": amount_received,
            "status": solicitation_status_for_storage(status),
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


def _report_campaign_options() -> list[Campaign]:
    return db.session.scalars(
        select(Campaign).order_by(Campaign.campaign_year.desc(), Campaign.id.desc())
    ).all()


def _selected_report_campaign(
    campaigns: list[Campaign],
    *,
    update_session: bool = True,
) -> Campaign | None:
    campaign_by_id = {campaign.id: campaign for campaign in campaigns}
    selected_campaign_id = _safe_int(request.args.get("campaign_id"))

    if selected_campaign_id is not None and selected_campaign_id in campaign_by_id:
        if update_session:
            session[REPORT_CAMPAIGN_SESSION_KEY] = selected_campaign_id
        return campaign_by_id[selected_campaign_id]

    session_campaign_id = _safe_int(session.get(REPORT_CAMPAIGN_SESSION_KEY))
    if session_campaign_id is not None and session_campaign_id in campaign_by_id:
        return campaign_by_id[session_campaign_id]

    default_campaign_id = _default_active_campaign_id()
    if default_campaign_id is not None and default_campaign_id in campaign_by_id:
        if update_session:
            session[REPORT_CAMPAIGN_SESSION_KEY] = default_campaign_id
        return campaign_by_id[default_campaign_id]

    if campaigns:
        if update_session:
            session[REPORT_CAMPAIGN_SESSION_KEY] = campaigns[0].id
        return campaigns[0]

    if update_session:
        session.pop(REPORT_CAMPAIGN_SESSION_KEY, None)
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


def _assigned_solicitor_filter_options() -> list[Person]:
    return db.session.scalars(
        select(Person)
        .join(Solicitation, Solicitation.solicitor_person_id == Person.id)
        .distinct()
        .order_by(
            Person.is_active.desc(),
            Person.last_name.asc(),
            Person.first_name.asc(),
            Person.id.asc(),
        )
    ).all()


def _selected_solicitor_filter() -> tuple[list[Person], int | None]:
    selected_solicitor_id = _safe_int(request.args.get("solicitor_id"))
    solicitor_filter_people = _assigned_solicitor_filter_options()
    solicitor_filter_ids = {person.id for person in solicitor_filter_people}
    if selected_solicitor_id is not None:
        if selected_solicitor_id not in solicitor_filter_ids:
            selected_solicitor_id = None
        else:
            session["active_solicitor_id"] = selected_solicitor_id
    else:
        session_solicitor_id = _safe_int(session.get("active_solicitor_id"))
        if session_solicitor_id in solicitor_filter_ids:
            selected_solicitor_id = session_solicitor_id

    return solicitor_filter_people, selected_solicitor_id


def _selected_tranche_filter() -> tuple[list[int], int | None]:
    tranche_filter_options = _tranche_filter_options()
    selected_tranche = _safe_int(request.args.get("tranche"))
    if selected_tranche is not None:
        if selected_tranche not in tranche_filter_options:
            selected_tranche = None
        else:
            session["active_tranche"] = selected_tranche
    else:
        session_tranche = _safe_int(session.get("active_tranche"))
        if session_tranche in tranche_filter_options:
            selected_tranche = session_tranche

    return tranche_filter_options, selected_tranche


def _primary_contact_for_solicitation(solicitation: Solicitation) -> "Contact | None":
    if solicitation.partner is None:
        return None
    return db.session.scalar(
        select(Contact)
        .where(Contact.partner_id == solicitation.partner_id, Contact.is_primary == True)  # noqa: E712
    )


def _solicitation_return_to_value() -> str | None:
    value = request.args.get("return_to")
    if value is None:
        value = request.form.get("return_to")

    if value == "campaign":
        return "campaign"
    return None


def _partner_active_only_selection() -> bool:
    if "active_only_applied" in request.args:
        active_only = (request.args.get("active_only") or "").strip().lower() in {
            "1",
            "true",
            "on",
            "yes",
        }
        session[PARTNER_ACTIVE_ONLY_SESSION_KEY] = active_only
        return active_only

    session_value = session.get(PARTNER_ACTIVE_ONLY_SESSION_KEY)
    if isinstance(session_value, bool):
        return session_value

    session[PARTNER_ACTIVE_ONLY_SESSION_KEY] = True
    return True


def _solicitation_filter_solicitor_id() -> int | None:
    value = _safe_int(request.args.get("solicitor_id"))
    if value is None:
        value = _safe_int(request.form.get("solicitor_id"))
    return value


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
