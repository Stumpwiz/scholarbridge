from flask import jsonify

from app.auth import bp


@bp.get("/status")
def status():
    return jsonify({"auth": "initialized", "workflows": "not_implemented"})
