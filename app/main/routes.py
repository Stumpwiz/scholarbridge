from flask import current_app, jsonify, render_template

from app.main import bp


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
