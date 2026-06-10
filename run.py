import click
from sqlalchemy import func, or_

from app import create_app
from app.db_safety import require_data_mutation_opt_in
from app.extensions import db
from app.models import Person, User

app = create_app()


@app.cli.command("init-db")
def init_db_command():
    """Initialize database tables for currently defined models."""
    with app.app_context():
        db.create_all()
    print("Database initialized.")


@app.cli.command("seed-committee-users")
@click.option("--password", default="ChangeMe123!", show_default=True, help="Initial password for seeded users.")
@click.option("--force-password-reset", is_flag=True, help="Reset password for existing seeded users.")
@click.option(
    "--allow-data-mutation",
    is_flag=True,
    help="Explicitly allow demo/seed data writes for this command.",
)
def seed_committee_users_command(password: str, force_password_reset: bool, allow_data_mutation: bool):
    """Seed initial committee users for demo authentication workflows."""
    require_data_mutation_opt_in(
        "seed committee users",
        allow_flag=allow_data_mutation,
    )

    committee = (
        {"first": "George", "last": "Wright", "username": "george.wright", "fallback_email": "geo@loyola.edu",
         "role": User.ROLE_ADMIN},
    )

    with app.app_context():
        created = 0
        updated = 0

        for member in committee:
            person = db.session.query(Person).filter(
                func.lower(Person.last_name) == member["last"].lower(),
                or_(
                    func.lower(Person.first_name) == member["first"].lower(),
                    func.lower(Person.preferred_name) == member["first"].lower(),
                ),
            ).one_or_none()

            if person is None:
                person = Person(
                    first_name=member["first"],
                    last_name=member["last"],
                    preferred_name=member["first"],
                    is_active=True,
                )
                db.session.add(person)
                db.session.flush()

            desired_email = _preferred_user_email(person, fallback=member["fallback_email"])
            user = db.session.query(User).filter(
                func.lower(User.username) == member["username"].lower()
            ).one_or_none()

            if user is None:
                user = User(
                    username=member["username"],
                    email=desired_email,
                    role=member["role"],
                    is_active=True,
                    person_id=person.id,
                )
                user.set_password(password)
                db.session.add(user)
                created += 1
            else:
                user.role = member["role"]
                user.person_id = person.id
                if _is_placeholder_email(user.email) and desired_email and not _is_placeholder_email(desired_email):
                    if not _email_in_use_by_other_user(desired_email, user.id):
                        user.email = desired_email
                if force_password_reset:
                    user.set_password(password)
                updated += 1

        db.session.commit()

    print(f"Committee users created: {created}")
    print(f"Committee users updated: {updated}")
    if created or force_password_reset:
        print(f"Initial password: {password}")


@app.cli.command("sync-users-from-people")
def sync_users_from_people_command():
    """Replace placeholder user emails with linked Person email when available."""
    with app.app_context():
        users = db.session.query(User).filter(User.person_id.isnot(None)).all()
        updated = 0

        for user in users:
            if not _is_placeholder_email(user.email):
                continue
            if user.person is None:
                continue

            person_email = _clean_email(user.person.email)
            if not person_email:
                continue
            if _is_placeholder_email(person_email):
                continue
            if _email_in_use_by_other_user(person_email, user.id):
                continue

            user.email = person_email
            updated += 1

        if updated:
            db.session.commit()

    print(f"Users updated: {updated}")


def _clean_email(value: str | None) -> str | None:
    if value is None:
        return None
    email = value.strip()
    return email or None


def _is_placeholder_email(value: str | None) -> bool:
    email = (_clean_email(value) or "").lower()
    return email.endswith("@example.org") or email.endswith("@example.com")


def _preferred_user_email(person: Person, fallback: str) -> str:
    person_email = _clean_email(person.email)
    if person_email:
        return person_email
    return fallback


def _email_in_use_by_other_user(email: str, current_user_id: int) -> bool:
    existing = (
        db.session.query(User)
        .filter(
            func.lower(User.email) == email.lower(),
            User.id != current_user_id,
        )
        .one_or_none()
    )
    return existing is not None


if __name__ == "__main__":
    app.run()
