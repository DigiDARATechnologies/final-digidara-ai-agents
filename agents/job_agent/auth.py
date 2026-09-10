"""Identity for this agent's own /api/jobs/* routes.

Unlike the original design (a JWT signed with a foreign certification
portal's secret), identity here rides the same verified header every other
Strategy F agent can trust: the orchestrator's gateway decodes the
platform's own login JWT and forwards a server-verified
`X-Digidara-User-Id` header (see agents/orchestrator/app/gateway/routes.py)
- this module never sees or trusts a raw token, only the header the
gateway already authenticated.

`X-Digidara-Is-Admin` follows the identical trust model, added specifically
for the holistic admin panel: it is set by the gateway only when the
platform's own `users.is_admin` column says so, never derived from
anything the browser sends.

Routes reached directly (not through the gateway - i.e. never, in
production) will see neither header and are correctly rejected as
unauthenticated; local `invoke.py` re-entry (current_app.test_client())
attaches these headers explicitly for every internal call.
"""

from functools import wraps

from flask import g, jsonify, request


def _user_id():
    return (request.headers.get("X-Digidara-User-Id") or "").strip()


def _is_admin():
    return (request.headers.get("X-Digidara-Is-Admin") or "").strip().lower() == "true"


def user_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = _user_id()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        g.job_user_id = user_id
        g.job_is_admin = _is_admin()
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = _user_id()
        if not user_id or not _is_admin():
            return jsonify({"error": "Administrator authorization required"}), 401
        g.job_user_id = user_id
        g.job_is_admin = True
        return view(*args, **kwargs)

    return wrapped
