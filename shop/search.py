"""The search service: items whose titles contain the term, from the replica.

From tinyAmazon/: python -m tinyhttp --host 127.0.0.1 --port 8003 shop.search:app
"""

from tinyweb import App, jsonify

from shop import common
from shop.errors import InvalidPage

app = App(__name__, static_folder=None)
common.handle_errors(app)
# The replica, so searching never slows ordering.
db = common.connect(common.REPLICA_PORT)


@app.route("/search")
def search(request):
    term = request.args.get("term", "")
    limit = number_arg(request, "limit", 20)
    if not 1 <= limit <= 100:
        raise InvalidPage("limit must be from 1 to 100.")
    cursor_id = number_arg(request, "cursor", 0)

    cursor = db.cursor()
    cursor.execute("SELECT id, title, price FROM items "
                   "WHERE title ILIKE ? AND stock > 0 AND id > ? "
                   "ORDER BY id LIMIT ?;",
                   (f"%{escape_like(term)}%", cursor_id, limit))
    rows = cursor.fetchall()
    items = [{"id": id, "title": title, "price": price}
             for id, title, price in rows]
    # A short page is the last; a full one may have more after it.
    next_cursor = rows[-1][0] if len(rows) == limit else None
    return jsonify({"items": items, "nextCursor": next_cursor})


def number_arg(request, name, default):
    """A whole number from the query, from 0 up, or 400."""
    if name not in request.args:
        return default
    value = request.args[name]
    if not (value.isascii() and value.isdigit()) or int(value) >= 2**63:
        raise InvalidPage(f"{name} must be a whole number, from 0 up.")
    return int(value)


def escape_like(term):
    """term with a \\ before each %, _ and \\, so they match only themselves."""
    # \ first, or it would escape the \s put in for the others.
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
