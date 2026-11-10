"""tinypay, the fake payment provider: a third party the order service
pays through, as Stripe is. Every charge succeeds. See DESIGN.md.

From tinyAmazon/: python -m tinyhttp --host 127.0.0.1 --port 9001 shop.tinypay:app
"""

import hmac
import json
import os
import secrets
import sys
import traceback

from tinyweb import App, abort, jsonify
from tinyweb.response import REASONS

from shop import common

SECRET = os.environ.get("TINYPAY_SECRET", "")
if not SECRET:
    sys.exit("shop.tinypay: set TINYPAY_SECRET, the API key the order "
             "service sends")

# Its own error codes, as Stripe's, as a third party's aren't the shop's.
CODES = {400: "invalid_request", 401: "invalid_api_key",
         404: "resource_missing", 409: "charge_already_refunded",
         415: "invalid_request", 422: "idempotency_key_reused"}

app = App(__name__, static_folder=None)

# All in memory, so a restart forgets them.
charges = {}       # id -> the charge
refunds = {}       # charge id -> its refund
# Idempotency-Key -> (the request, the reply's body and status), so a
# retry gets the first reply back without acting again.
replies = {}


def error(request, error):
    if error.status == 500:
        traceback.print_exception(error.__cause__)
    code = CODES.get(error.status, REASONS[error.status].lower()
                     .replace(" ", "_"))
    return jsonify({"error": {"code": code, "message": error.detail}},
                   error.status)


for status in REASONS:
    if status >= 400:
        app.error(status)(error)


def idempotent(view):
    """Run view once per Idempotency-Key, giving back its first reply to
    every retry."""

    def wrapper(request):
        if not hmac.compare_digest(request.headers.get("Authorization", ""),
                                   f"Bearer {SECRET}"):
            abort(401, "Invalid API key.")
        key = request.headers.get("Idempotency-Key")
        if not key:
            abort(400, "Send an Idempotency-Key header.")
        body = common.json_object(request)
        sent = (request.path, json.dumps(body, sort_keys=True))
        if key in replies:
            first, reply, status = replies[key]
            if first != sent:
                abort(422, f"Idempotency-Key {key} was used for a "
                           f"different request.")
            return jsonify(reply, status)
        reply, status = view(body)
        replies[key] = (sent, reply, status)
        return jsonify(reply, status)

    return wrapper


@app.route("/charges", methods=["POST"])
@idempotent
def charge(body):
    amount = body.get("amount")
    if not common.whole_number(amount) or amount == 0:
        abort(400, "amount must be a whole number of pence, from 1 up.")
    id = "ch_" + secrets.token_hex(12)
    charges[id] = {"id": id, "amount": amount, "status": "succeeded"}
    return charges[id], 201


@app.route("/refunds", methods=["POST"])
@idempotent
def refund(body):
    charge_id = body.get("charge")
    if not isinstance(charge_id, str):
        abort(400, "charge must be a charge's id.")
    if charge_id not in charges:
        abort(404, f"No such charge: {charge_id}.")
    if charge_id in refunds:
        abort(409, f"Charge {charge_id} has already been refunded.")
    id = "re_" + secrets.token_hex(12)
    refunds[charge_id] = {"id": id, "charge": charge_id,
                          "amount": charges[charge_id]["amount"]}
    return refunds[charge_id], 201
