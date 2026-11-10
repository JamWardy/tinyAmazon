"""The order service: reserve, pay, confirm, as DESIGN.md's ordering
flow, all in one POST /orders.

From tinyAmazon/: python -m tinyhttp --host 127.0.0.1 --port 8004 shop.orders:app
"""

import time
from dataclasses import dataclass

import tinysqlclient
from tinyweb import App, jsonify

from shop import common, payments
from shop.errors import (CardDeclined, InvalidOrder, KeyReused,
                         MissingIdempotencyKey, NoSuchItem, NotEnoughStock,
                         OrderClosed)

RESERVE_SECONDS = 600
MAX_KEY_LENGTH = 255

app = App(__name__, static_folder=None)
common.handle_errors(app)
db = common.connect(common.PRIMARY_PORT)


@dataclass
class Order:
    """A row of orders, in its columns' order, for SELECT * and
    RETURNING *."""
    id: int
    user_id: int
    item_id: int
    quantity: int
    unit_price: int
    status: str
    expires_at: int
    idempotency_key: str
    charge_id: str | None
    created_at: int

    def to_json(self):
        return {"id": self.id, "userId": self.user_id,
                "itemId": self.item_id, "quantity": self.quantity,
                "unitPrice": self.unit_price, "status": self.status,
                "expiresAt": self.expires_at,
                "idempotencyKey": self.idempotency_key,
                "chargeId": self.charge_id, "createdAt": self.created_at}


@app.route("/orders", methods=["POST"])
def place_order(request):
    user_id = common.user_id(request)
    key = request.headers.get("Idempotency-Key", "")
    if not key:
        raise MissingIdempotencyKey("Send an Idempotency-Key header, the "
                                    "same on every retry.")
    if len(key) > MAX_KEY_LENGTH:
        raise InvalidOrder(f"The Idempotency-Key must be at most "
                           f"{MAX_KEY_LENGTH} characters.")
    body = common.json_object(request)
    item_id, quantity = body.get("itemId"), body.get("quantity")
    if not common.whole_number(item_id):
        raise InvalidOrder("itemId must be an item's id.")
    if not common.whole_number(quantity) or quantity == 0:
        raise InvalidOrder("quantity must be a whole number, from 1 up.")

    order = find_or_reserve(user_id, key, item_id, quantity)
    if order.status == "PENDING":
        order = pay_and_confirm(order)
    if order.status == "PAID":
        return jsonify(order.to_json(), 201)
    if order.status == "CANCELLED":
        # Again, in case the refund failed the first time; its key makes
        # this a no-op if it didn't.
        payments.refund(order.id, order.charge_id)
    raise OrderClosed(f"Order {order.id} is {order.status}; start again "
                      f"with a new Idempotency-Key.")


def find_or_reserve(user_id, key, item_id, quantity):
    """The order this key already made, or a new PENDING one."""
    while True:
        order = find(user_id, key)
        if order:
            if (order.item_id, order.quantity) != (item_id, quantity):
                raise KeyReused(f"Idempotency-Key {key} was used for order "
                                f"{order.id}, of a different item or "
                                f"quantity.")
            return order
        try:
            return reserve(user_id, key, item_id, quantity)
        except tinysqlclient.IntegrityError as error:
            if error.sqlstate != "23505":
                raise
            # A retry with the same key got there first: find its order.


def find(user_id, key):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM orders "
                   "WHERE user_id = ? AND idempotency_key = ?;",
                   (user_id, key))
    row = cursor.fetchone()
    return Order(*row) if row else None


def reserve(user_id, key, item_id, quantity):
    now = int(time.time())
    cursor = db.cursor()
    with db.transaction():
        cursor.execute("SELECT price, stock FROM items WHERE id = ? "
                       "FOR UPDATE;", (item_id,))
        row = cursor.fetchone()
        if row is None:
            raise NoSuchItem(f"There's no item {item_id}.")
        price, stock = row
        check_available(cursor, item_id, stock, quantity, now)
        cursor.execute("INSERT INTO orders (user_id, item_id, quantity, "
                       "unit_price, status, expires_at, idempotency_key, "
                       "created_at) VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?) "
                       "RETURNING *;",
                       (user_id, item_id, quantity, price,
                        now + RESERVE_SECONDS, key, now))
        return Order(*cursor.fetchone())


def check_available(cursor, item_id, stock, quantity, now):
    """NotEnoughStock unless stock, less what unexpired PENDING orders
    hold, covers quantity. Call it with the item locked."""
    cursor.execute("SELECT SUM(quantity) FROM orders WHERE item_id = ? "
                   "AND status = 'PENDING' AND expires_at > ?;",
                   (item_id, now))
    # SUM of no rows is NULL.
    available = stock - (cursor.fetchone()[0] or 0)
    if available < quantity:
        raise NotEnoughStock(f"Item {item_id} has {max(available, 0)} left; "
                             f"you asked for {quantity}.")


def pay_and_confirm(order):
    try:
        charge_id = payments.charge(order.id,
                                    order.quantity * order.unit_price)
    except CardDeclined:
        db.cursor().execute("UPDATE orders SET status = 'EXPIRED' "
                            "WHERE id = ? AND status = 'PENDING';",
                            (order.id,))
        raise

    now = int(time.time())
    cursor = db.cursor()
    sold_out = False
    with db.transaction():
        cursor.execute("SELECT stock FROM items WHERE id = ? FOR UPDATE;",
                       (order.item_id,))
        (stock,) = cursor.fetchone()
        # A retry of the same order may have confirmed it while this one
        # was paying.
        order = find(order.user_id, order.idempotency_key)
        if order.status != "PENDING":
            return order
        if order.expires_at <= now:
            # The reservation ran out while paying, so it no longer counts
            # in the sum; the stock may have gone to someone else.
            try:
                check_available(cursor, order.item_id, stock,
                                order.quantity, now)
            except NotEnoughStock:
                sold_out = True
        status = "CANCELLED" if sold_out else "PAID"
        cursor.execute("UPDATE orders SET status = ?, charge_id = ? "
                       "WHERE id = ?;", (status, charge_id, order.id))
        if not sold_out:
            cursor.execute("UPDATE items SET stock = stock - ? WHERE id = ?;",
                           (order.quantity, order.item_id))

    if sold_out:
        payments.refund(order.id, charge_id)
        raise NotEnoughStock(f"Your reservation of item {order.item_id} ran "
                             f"out while paying, and it sold out; you've "
                             f"been refunded.")
    return find(order.user_id, order.idempotency_key)
