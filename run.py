from app import create_app
from app.extensions import db

app = create_app()


@app.cli.command("init-db")
def init_db_command():
    """Initialize database tables for currently defined models."""
    with app.app_context():
        db.create_all()
    print("Database initialized.")


if __name__ == "__main__":
    app.run()
