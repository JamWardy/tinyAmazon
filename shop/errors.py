"""The shop's errors, one class per kind, each with its own title.

    raise EmailTaken(f"{email} already has an account.")

tinyweb answers any HTTPError, these included, with the handler for its
status, which is common.problem.
"""

from tinyweb import HTTPError


class ShopError(HTTPError):
    """Each subclass sets status and title."""

    def __init__(self, detail):
        super().__init__(self.status, detail)


class MissingCredentials(ShopError):
    status = 400
    title = "Missing email or password"


class EmailTaken(ShopError):
    status = 409
    title = "Email already registered"


class WrongCredentials(ShopError):
    status = 401
    title = "Wrong email or password"


class NotLoggedIn(ShopError):
    status = 401
    title = "Not logged in"


class InvalidListing(ShopError):
    status = 400
    title = "Invalid listing"


class InvalidPage(ShopError):
    status = 400
    title = "Invalid page"


class MissingIdempotencyKey(ShopError):
    status = 400
    title = "Missing Idempotency-Key"


class InvalidOrder(ShopError):
    status = 400
    title = "Invalid order"


class NoSuchItem(ShopError):
    status = 404
    title = "No such item"


class NotEnoughStock(ShopError):
    status = 409
    title = "Not enough stock"


class OrderClosed(ShopError):
    status = 409
    title = "Order closed"


class KeyReused(ShopError):
    status = 422
    title = "Idempotency-Key reused"


class CardDeclined(ShopError):
    status = 402
    title = "Card declined"


class PaymentFailed(ShopError):
    status = 502
    title = "Payment failed"
