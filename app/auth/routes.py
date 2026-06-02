from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

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
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, or_, select
from werkzeug.utils import secure_filename

from app.auth import bp
from app.auth.permissions import admin_required
from app.extensions import db
from app.models import Person, User

AVATAR_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
DEFAULT_AVATAR_STATIC_PATH = "img/avatars/default-avatar.svg"


@bp.get("/status")
def status():
    return jsonify({"auth": "initialized", "workflows": "implemented"})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        identity = (request.form.get("identity") or "").strip()
        password = request.form.get("password") or ""

        if not identity or not password:
            flash("Enter username or email and password.", "danger")
            return render_template("auth/login.html", page_title="Login", identity=identity)

        user = db.session.scalar(
            select(User).where(
                or_(
                    func.lower(User.username) == identity.lower(),
                    func.lower(User.email) == identity.lower(),
                )
            )
        )

        if user is None or not user.check_password(password):
            flash("Invalid credentials.", "danger")
            return render_template("auth/login.html", page_title="Login", identity=identity)

        if not user.is_active:
            flash("Your account is inactive. Contact an administrator.", "danger")
            return render_template("auth/login.html", page_title="Login", identity=identity)

        login_user(user)
        user.last_login_at = datetime.utcnow()
        db.session.commit()
        flash("Welcome back.", "success")
        return redirect(_safe_next_url() or url_for("main.index"))

    return render_template("auth/login.html", page_title="Login", identity="")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        avatar_file = request.files.get("avatar_file")
        if avatar_file and avatar_file.filename:
            avatar_error = _apply_avatar_upload(current_user, avatar_file)
            if avatar_error:
                flash(avatar_error, "danger")
            else:
                db.session.commit()
                flash("Profile updated.", "success")
                return redirect(url_for("auth.profile"))
        else:
            flash("No avatar file selected.", "warning")
    return render_template(
        "auth/profile.html",
        page_title="Profile",
        default_avatar_path=DEFAULT_AVATAR_STATIC_PATH,
    )


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "danger")
        elif len(new_password) < 8:
            flash("New password must be at least 8 characters.", "danger")
        elif new_password != confirm_password:
            flash("New password and confirmation do not match.", "danger")
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash("Password changed.", "success")
            return redirect(url_for("auth.profile"))

    return render_template("auth/change_password.html", page_title="Change Password")


@bp.get("/users")
@admin_required
def user_list():
    users = db.session.scalars(
        select(User)
        .order_by(
            User.is_active.desc(),
            User.role.asc(),
            User.username.asc(),
            User.id.asc(),
        )
    ).all()
    people = _person_options_for_user_forms()
    return render_template(
        "auth/users/list.html",
        page_title="User Management",
        users=users,
        people=people,
        role_choices=User.ROLE_CHOICES,
        default_avatar_path=DEFAULT_AVATAR_STATIC_PATH,
    )


@bp.route("/users/new", methods=["GET", "POST"])
@admin_required
def user_create():
    form_data = _user_form_data()
    people = _person_options_for_user_forms()

    if request.method == "POST":
        form_data = _user_form_data(request.form)
        validation_error = _validate_user_form(form_data)
        if validation_error:
            flash(validation_error, "danger")
        else:
            user = User(
                username=form_data["username"],
                email=form_data["email"],
                role=form_data["role"],
                is_active=form_data["is_active"],
                person_id=form_data["person_id"],
            )
            user.set_password(form_data["password"])

            avatar_file = request.files.get("avatar_file")
            if avatar_file and avatar_file.filename:
                avatar_error = _apply_avatar_upload(user, avatar_file)
                if avatar_error:
                    flash(avatar_error, "danger")
                    return render_template(
                        "auth/users/form.html",
                        page_title="Create User",
                        mode="create",
                        user=None,
                        form_data=form_data,
                        people=people,
                        role_choices=User.ROLE_CHOICES,
                    )

            db.session.add(user)
            db.session.commit()
            flash("User created.", "success")
            return redirect(url_for("auth.user_list"))

    return render_template(
        "auth/users/form.html",
        page_title="Create User",
        mode="create",
        user=None,
        form_data=form_data,
        people=people,
        role_choices=User.ROLE_CHOICES,
    )


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def user_edit(user_id: int):
    user = db.get_or_404(User, user_id)
    form_data = _user_to_form_data(user)
    people = _person_options_for_user_forms()

    if request.method == "POST":
        form_data = _user_form_data(request.form)
        validation_error = _validate_user_form(form_data, user_id=user.id, for_update=True)
        if validation_error:
            flash(validation_error, "danger")
        elif user.id == current_user.id and (
            form_data["role"] != User.ROLE_ADMIN or not form_data["is_active"]
        ):
            flash("You cannot remove your own admin access or disable your account.", "danger")
        else:
            user.username = form_data["username"]
            user.email = form_data["email"]
            user.role = form_data["role"]
            user.is_active = form_data["is_active"]
            user.person_id = form_data["person_id"]

            avatar_file = request.files.get("avatar_file")
            if avatar_file and avatar_file.filename:
                avatar_error = _apply_avatar_upload(user, avatar_file)
                if avatar_error:
                    flash(avatar_error, "danger")
                    return render_template(
                        "auth/users/form.html",
                        page_title=f"Edit User: {user.username}",
                        mode="edit",
                        user=user,
                        form_data=form_data,
                        people=people,
                        role_choices=User.ROLE_CHOICES,
                    )

            db.session.commit()
            flash("User updated.", "success")
            return redirect(url_for("auth.user_list"))

    return render_template(
        "auth/users/form.html",
        page_title=f"Edit User: {user.username}",
        mode="edit",
        user=user,
        form_data=form_data,
        people=people,
        role_choices=User.ROLE_CHOICES,
    )


@bp.route("/users/<int:user_id>/delete", methods=["GET", "POST"])
@admin_required
def user_delete(user_id: int):
    user = db.get_or_404(User, user_id)

    if request.method == "POST":
        guardrail_error = _validate_user_delete_guardrails(user)
        if guardrail_error:
            flash(guardrail_error, "danger")
            return redirect(url_for("auth.user_list"))

        username = user.username
        db.session.delete(user)
        db.session.commit()
        flash(f"User account '{username}' deleted.", "success")
        return redirect(url_for("auth.user_list"))

    guardrail_error = _validate_user_delete_guardrails(user)
    if guardrail_error:
        flash(guardrail_error, "danger")
        return redirect(url_for("auth.user_list"))

    return render_template(
        "auth/users/delete_confirm.html",
        page_title=f"Delete User: {user.display_name}",
        user=user,
    )


@bp.post("/users/<int:user_id>/reset-password")
@admin_required
def user_reset_password(user_id: int):
    user = db.get_or_404(User, user_id)
    new_password = request.form.get("new_password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    if len(new_password) < 8:
        flash("Reset password must be at least 8 characters.", "danger")
    elif new_password != confirm_password:
        flash("Reset password confirmation does not match.", "danger")
    else:
        user.set_password(new_password)
        db.session.commit()
        flash(f"Password reset for {user.username}.", "success")

    return redirect(url_for("auth.user_list"))


def _safe_next_url() -> str | None:
    next_value = request.args.get("next") or request.form.get("next")
    if not next_value:
        return None
    parsed = urlsplit(next_value)
    if parsed.scheme or parsed.netloc:
        return None
    return next_value


def _user_form_data(form=None) -> dict:
    if form is None:
        return {
            "username": "",
            "email": "",
            "role": User.ROLE_READER,
            "is_active": True,
            "person_id": None,
            "password": "",
            "password_confirm": "",
        }

    return {
        "username": (form.get("username") or "").strip(),
        "email": (form.get("email") or "").strip(),
        "role": (form.get("role") or User.ROLE_READER).strip(),
        "is_active": form.get("is_active") == "on",
        "person_id": _safe_int(form.get("person_id")),
        "password": form.get("password") or "",
        "password_confirm": form.get("password_confirm") or "",
    }


def _user_to_form_data(user: User) -> dict:
    return {
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "person_id": user.person_id,
        "password": "",
        "password_confirm": "",
    }


def _validate_user_form(
    form_data: dict,
    user_id: int | None = None,
    for_update: bool = False,
) -> str | None:
    if not form_data["username"]:
        return "Username is required."
    if not form_data["email"]:
        return "Email is required."
    if form_data["role"] not in User.ROLE_CHOICES:
        return "Select a valid role."

    existing_username = db.session.scalar(
        select(User).where(func.lower(User.username) == form_data["username"].lower())
    )
    if existing_username and existing_username.id != user_id:
        return "Username is already in use."

    existing_email = db.session.scalar(
        select(User).where(func.lower(User.email) == form_data["email"].lower())
    )
    if existing_email and existing_email.id != user_id:
        return "Email is already in use."

    if form_data["person_id"] is not None:
        person = db.session.get(Person, form_data["person_id"])
        if person is None:
            return "Select a valid linked person."
        person_user = db.session.scalar(select(User).where(User.person_id == person.id))
        if person_user and person_user.id != user_id:
            return "This person is already linked to another user."

    if not for_update:
        if len(form_data["password"]) < 8:
            return "Password must be at least 8 characters."
        if form_data["password"] != form_data["password_confirm"]:
            return "Password and confirmation do not match."

    return None


def _person_options_for_user_forms() -> list[Person]:
    return db.session.scalars(
        select(Person).order_by(
            Person.is_active.desc(),
            Person.last_name.asc(),
            Person.first_name.asc(),
            Person.id.asc(),
        )
    ).all()


def _validate_user_delete_guardrails(user: User) -> str | None:
    if user.id == current_user.id:
        return "You cannot delete your currently logged-in account."

    if user.role == User.ROLE_ADMIN:
        admin_count = db.session.scalar(
            select(func.count(User.id)).where(
                User.role == User.ROLE_ADMIN,
                User.is_active.is_(True),
            )
        )
        if (admin_count or 0) <= 1:
            return "You cannot delete the final active admin account."

    return None


def _apply_avatar_upload(user: User, avatar_file) -> str | None:
    filename = secure_filename(avatar_file.filename or "")
    extension = Path(filename).suffix.lower()
    if extension not in AVATAR_ALLOWED_EXTENSIONS:
        return "Avatar must be a PNG, JPG, JPEG, GIF, or WEBP file."

    avatar_dir = Path(current_app.static_folder) / "img" / "avatars" / "uploads"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    final_name = f"user_{user.id or 'new'}_{uuid4().hex}{extension}"
    output_path = avatar_dir / final_name
    avatar_file.save(output_path)
    user.avatar_path = f"img/avatars/uploads/{final_name}"
    return None


def _safe_int(value) -> int | None:
    if value is None:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    try:
        return int(text_value)
    except ValueError:
        return None
