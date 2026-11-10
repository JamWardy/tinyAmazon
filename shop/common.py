"""What the shop's services share: the database, the user, and errors."""

import sys
import traceback

import tinysqlclient
from tinyweb import abort, jsonify
from tinyweb.response import REASONS

from shop.errors import NotLoggedIn

PRIMARY_PORT = 5480
REPLICA_PORT = 5481


def connect(port):
    """One connection for the process, opened as it starts, as
    tinysqlclient's DESIGN.md says. It reopens itself if it drops."""
    try:
        return tinysqlclient.connect(port=port)
    except tinysqlclient.OperationalError as error:
        sys.exit(f"shop: {error}; is `just run` running?")


def handle_errors(app):
    """Answer every error with a Problem Details body, as DESIGN.md says."""
    for status in REASONS:
        if status >= 400:
            app.error(status)(problem)


def problem(request, error):
    if error.status == 500:
        # The client gets nothing of it, so the log is the only trace.
        traceback.print_exception(error.__cause__)
        detail = "Something went wrong on our side."
    else:
        detail = error.detail
    # The shop's own errors have their own titles; the rest, such as
    # tinyweb's 404, have the status's words.
    title = getattr(error, "title", REASONS[error.status])
    response = jsonify({"title": title,
                        "status": error.status, "detail": detail},
                       error.status)
    response.headers["Content-Type"] = "application/problem+json"
    return response


def json_object(request):
    """The body as a JSON object, with 400 for any other JSON."""
    body = request.json()
    if not isinstance(body, dict):
        abort(400, "The body must be a JSON object.")
    return body


def user_id(request):
    """The user the gateway says sent this, or 401."""
    value = request.headers.get("X-User-Id", "")
    if not (value.isascii() and value.isdigit()) or int(value) == 0:
        raise NotLoggedIn("Log in first.")
    return int(value)


def whole_number(value):
    """Whether value is a JSON whole number that fits TinySQL's INT, from 0
    up. bool is excluded, as True is an int in Python."""
    return (isinstance(value, int) and not isinstance(value, bool)
            and 0 <= value < 2**63)
