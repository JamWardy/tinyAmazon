"""Paying through tinypay, the payment provider, on tinyrequests.

Its replies become CardDeclined or PaymentFailed, so the order service
handles the shop's errors, not tinypay's.
"""

import os
import sys

import tinyrequests

from shop.errors import CardDeclined, PaymentFailed

URL = "http://127.0.0.1:9001"
TIMEOUT = (2, 10)    # connect, read
SECRET = os.environ.get("TINYPAY_SECRET", "")
if not SECRET:
    sys.exit("shop.payments: set TINYPAY_SECRET, tinypay's API key")


def charge(order_id, amount):
    """Charge amount pence for the order; returns the charge's id. The
    order's id is the key, so paying again after a crash never charges
    twice."""
    reply = post("/charges", {"amount": amount}, str(order_id))
    if reply.status_code == 402:
        raise CardDeclined(provider_message(reply))
    return created(reply)["id"]


def refund(order_id, charge_id):
    created(post("/refunds", {"charge": charge_id}, f"refund-{order_id}"))


def post(path, body, key):
    try:
        return tinyrequests.post(
            URL + path, json=body, timeout=TIMEOUT,
            headers={"Authorization": f"Bearer {SECRET}",
                     "Idempotency-Key": key})
    except tinyrequests.RequestException as error:
        print(f"shop.payments: POST {path}: {error}", file=sys.stderr)
        raise PaymentFailed("The payment provider didn't answer; "
                            "try again with the same Idempotency-Key.")


def created(reply):
    """The body of a 201 with an id; anything else is the provider
    failing."""
    if reply.status_code == 201:
        try:
            body = reply.json()
        except ValueError:
            body = None
        if isinstance(body, dict) and isinstance(body.get("id"), str):
            return body
    print(f"shop.payments: {reply.url}: {reply.status_code} "
          f"{reply.text[:200]}", file=sys.stderr)
    raise PaymentFailed("The payment provider failed; "
                        "try again with the same Idempotency-Key.")


def provider_message(reply):
    try:
        return reply.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return "The card was declined."
