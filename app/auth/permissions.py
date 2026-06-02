from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def _role_required(*roles: str):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


admin_required = _role_required("admin")
editor_required = _role_required("admin", "editor")
