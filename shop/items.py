"""The item CRUD service: sellers create listings.

From tinyAmazon/: python -m tinyhttp --host 127.0.0.1 --port 8002 shop.items:app
"""

from tinyweb import App, jsonify

from shop import common
from shop.errors import InvalidListing

app = App(__name__, static_folder=None)
common.handle_errors(app)
db = common.connect(common.PRIMARY_PORT)


@app.route("/listings", methods=["POST"])
def create_listing(request):
    seller_id = common.user_id(request)
    body = common.json_object(request)

    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        raise InvalidListing("Give the item a title.")
    description = body.get("description")
    if description is not None and not isinstance(description, str):
        raise InvalidListing("The description must be text, if given.")
    price, stock = body.get("price"), body.get("stock")
    if not common.whole_number(price):
        raise InvalidListing(
            "The price must be a whole number of pence, from 0 up.")
    if not common.whole_number(stock):
        raise InvalidListing("The stock must be a whole number, from 0 up.")

    cursor = db.cursor()
    cursor.execute("INSERT INTO items (seller_id, title, description, price, "
                   "stock) VALUES (?, ?, ?, ?, ?) RETURNING *;",
                   (seller_id, title, description, price, stock))
    id, seller_id, title, description, price, stock = cursor.fetchone()
    return jsonify({"id": id, "sellerId": seller_id, "title": title,
                    "description": description, "price": price,
                    "stock": stock}, 201)
