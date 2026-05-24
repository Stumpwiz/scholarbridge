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
from sqlalchemy import select

from app.main import bp
from app.extensions import db
from app.models import Contact, Organization

ORGANIZATION_TYPE_OPTIONS = tuple(
    sorted(
        [
            "Construction",
            "Facilities Maintenance",
            "Renovation",
            "Utilities",
            "Landscaping",
            "Environmental Services",
            "Food Services",
            "Resident Services",
            "Management Services",
            "Financial Services",
            "Insurance",
            "Legal Services",
            "Technology Services",
            "Sustainability",
            "Healthcare Services",
            "Other",
        ]
    )
)


@bp.get("/")
def index():
    return render_template("index.html", page_title="Home")


@bp.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "app": current_app.config.get("APP_NAME", "ScholarBridge"),
        }
    )


@bp.get("/organizations")
def organization_list():
    organizations = db.session.scalars(
        select(Organization).order_by(Organization.organization_name.asc())
    ).all()
    return render_template(
        "organizations/list.html",
        page_title="Organizations",
        organizations=organizations,
    )


@bp.route("/organizations/new", methods=["GET", "POST"])
def organization_create():
    form_data = {"is_active": True}
    organization_types, legacy_organization_type = _organization_type_choices()

    if request.method == "POST":
        form_data = _organization_form_data(request.form)
        validation_error = _validate_organization_form(form_data)
        if validation_error:
            flash(validation_error, "danger")
        else:
            organization = Organization(**form_data)
            db.session.add(organization)
            db.session.commit()
            flash("Organization created.", "success")
            return redirect(url_for("main.organization_detail", organization_id=organization.id))

    return render_template(
        "organizations/form.html",
        page_title="Create Organization",
        mode="create",
        organization=None,
        form_data=form_data,
        organization_types=organization_types,
        legacy_organization_type=legacy_organization_type,
    )


@bp.get("/organizations/<int:organization_id>")
def organization_detail(organization_id: int):
    organization = db.get_or_404(Organization, organization_id)
    return _render_organization_detail(
        organization=organization,
        contact_form_data=_contact_form_data(),
        editing_contact=None,
    )


@bp.route("/organizations/<int:organization_id>/edit", methods=["GET", "POST"])
def organization_edit(organization_id: int):
    organization = db.get_or_404(Organization, organization_id)
    form_data = _organization_to_form_data(organization)
    organization_types, legacy_organization_type = _organization_type_choices(
        organization.organization_type
    )

    if request.method == "POST":
        form_data = _organization_form_data(request.form)
        validation_error = _validate_organization_form(
            form_data, legacy_organization_type=legacy_organization_type
        )
        if validation_error:
            flash(validation_error, "danger")
        else:
            for key, value in form_data.items():
                setattr(organization, key, value)
            db.session.commit()
            flash("Organization updated.", "success")
            return redirect(url_for("main.organization_detail", organization_id=organization.id))

    return render_template(
        "organizations/form.html",
        page_title=f"Edit {organization.organization_name}",
        mode="edit",
        organization=organization,
        form_data=form_data,
        organization_types=organization_types,
        legacy_organization_type=legacy_organization_type,
    )


@bp.post("/organizations/<int:organization_id>/contacts/new")
def organization_contact_create(organization_id: int):
    organization = db.get_or_404(Organization, organization_id)
    contact_form_data = _contact_form_data(request.form)
    validation_error = _validate_contact_form(contact_form_data)

    if validation_error:
        flash(validation_error, "danger")
        return _render_organization_detail(
            organization=organization,
            contact_form_data=contact_form_data,
            editing_contact=None,
        )

    if contact_form_data["is_primary"]:
        _unset_other_primary_contacts(organization.id)

    contact = Contact(
        organization_id=organization.id,
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
        url_for("main.organization_detail", organization_id=organization.id, _anchor="contacts")
    )


@bp.route(
    "/organizations/<int:organization_id>/contacts/<int:contact_id>/edit",
    methods=["GET", "POST"],
)
def organization_contact_edit(organization_id: int, contact_id: int):
    organization = db.get_or_404(Organization, organization_id)
    contact = db.get_or_404(Contact, contact_id)

    if contact.organization_id != organization.id:
        abort(404)

    if request.method == "POST":
        contact_form_data = _contact_form_data(request.form)
        validation_error = _validate_contact_form(contact_form_data)

        if validation_error:
            flash(validation_error, "danger")
            return _render_organization_detail(
                organization=organization,
                contact_form_data=_contact_form_data(),
                editing_contact=contact,
                edit_form_data=contact_form_data,
            )

        for key in ("first_name", "last_name", "title", "email", "phone", "notes"):
            setattr(contact, key, contact_form_data[key])
        contact.is_primary = contact_form_data["is_primary"]
        contact.is_active = contact_form_data["is_active"]

        if contact.is_primary:
            _unset_other_primary_contacts(organization.id, except_contact_id=contact.id)

        db.session.commit()
        flash("Contact updated.", "success")
        return redirect(
            url_for("main.organization_detail", organization_id=organization.id, _anchor="contacts")
        )

    return _render_organization_detail(
        organization=organization,
        contact_form_data=_contact_form_data(),
        editing_contact=contact,
        edit_form_data=_contact_to_form_data(contact),
    )


def _render_organization_detail(
    organization: Organization,
    contact_form_data: dict,
    editing_contact: Contact | None,
    edit_form_data: dict | None = None,
):
    contacts = _load_organization_contacts(organization.id)
    return render_template(
        "organizations/detail.html",
        page_title=organization.organization_name,
        organization=organization,
        contacts=contacts,
        contact_form_data=contact_form_data,
        editing_contact=editing_contact,
        edit_form_data=edit_form_data or {},
    )


def _load_organization_contacts(organization_id: int) -> list[Contact]:
    return db.session.scalars(
        select(Contact)
        .where(Contact.organization_id == organization_id)
        .order_by(
            Contact.is_primary.desc(),
            Contact.is_active.desc(),
            Contact.last_name.asc(),
            Contact.first_name.asc(),
            Contact.id.asc(),
        )
    ).all()


def _unset_other_primary_contacts(
    organization_id: int, except_contact_id: int | None = None
) -> None:
    contacts = _load_organization_contacts(organization_id)
    for contact in contacts:
        if except_contact_id is not None and contact.id == except_contact_id:
            continue
        contact.is_primary = False


def _organization_form_data(form) -> dict:
    return {
        "organization_name": form.get("organization_name", "").strip(),
        "display_name": _empty_to_none(form.get("display_name")),
        "organization_type": _empty_to_none(form.get("organization_type")),
        "email_main": _empty_to_none(form.get("email_main")),
        "phone_main": _empty_to_none(form.get("phone_main")),
        "website": _empty_to_none(form.get("website")),
        "organization_notes": _empty_to_none(form.get("organization_notes")),
        "is_active": form.get("is_active") == "on",
    }


def _organization_to_form_data(organization: Organization) -> dict:
    return {
        "organization_name": organization.organization_name or "",
        "display_name": organization.display_name or "",
        "organization_type": organization.organization_type or "",
        "email_main": organization.email_main or "",
        "phone_main": organization.phone_main or "",
        "website": organization.website or "",
        "organization_notes": organization.organization_notes or "",
        "is_active": organization.is_active,
    }


def _validate_organization_form(
    form_data: dict, legacy_organization_type: str | None = None
) -> str | None:
    if not form_data["organization_name"]:
        return "Organization name is required."
    organization_type = form_data["organization_type"]
    if organization_type:
        if organization_type in ORGANIZATION_TYPE_OPTIONS:
            return None
        if legacy_organization_type and organization_type == legacy_organization_type:
            return None
        return "Please select a valid organization category."
    return None


def _empty_to_none(value):
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


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


def _organization_type_choices(current_value: str | None = None) -> tuple[list[str], str | None]:
    legacy_organization_type = None
    if current_value and current_value not in ORGANIZATION_TYPE_OPTIONS:
        legacy_organization_type = current_value
    return list(ORGANIZATION_TYPE_OPTIONS), legacy_organization_type
