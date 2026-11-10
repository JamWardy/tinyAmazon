"""The auth service: sign-up, and log-in, which gives a JWT.

From tinyAmazon/: python -m tinyhttp --host 127.0.0.1 --port 8001 shop.auth:app
"""

import base64
import hashlib
import hmac
import json
import os
import sys
import time

import tinysqlclient
from tinyweb import App, jsonify

from shop import common
from shop.errors import EmailTaken, MissingCredentials, WrongCredentials

SECRET = os.environ.get("SHOP_JWT_SECRET", "").encode()
if not SECRET:
    sys.exit("shop.auth: set SHOP_JWT_SECRET, the secret tokens are signed "
             "with")

app = App(__name__, static_folder=None)
common.handle_errors(app)
db = common.connect(common.PRIMARY_PORT)


@app.route("/users", methods=["POST"])
def sign_up(request):
    email, password = credentials(request)
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO users (email, password_hash) VALUES (?, ?) "
                       "RETURNING id, email;", (email, hash_password(password)))
    except tinysqlclient.IntegrityError as error:
        if error.sqlstate == "23505":
            raise EmailTaken(f"{email} already has an account.")
        raise
    id, email = cursor.fetchone()
    return jsonify({"id": id, "email": email}, 201)


@app.route("/login", methods=["POST"])
def log_in(request):
    email, password = credentials(request)
    cursor = db.cursor()
    cursor.execute("SELECT id, password_hash FROM users WHERE email = ?;",
                   (email,))
    row = cursor.fetchone()
    if row is None:
        # Hash anyway, so a missing email takes as long as a wrong password,
        # and the time doesn't say which emails have accounts.
        hash_password(password)
        raise WrongCredentials("Check them and try again.")
    id, stored = row
    if not check_password(password, stored):
        raise WrongCredentials("Check them and try again.")
    return jsonify({"token": make_token(id)})


def credentials(request):
    body = common.json_object(request)
    email, password = body.get("email"), body.get("password")
    if not (isinstance(email, str) and email and
            isinstance(password, str) and password):
        raise MissingCredentials("Give an email and a password.")
    return email, password


# scrypt's settings, as DESIGN.md gives them.
SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def hash_password(password, salt=None):
    """"<salt>:<hash>", both hex, for password_hash."""
    salt = os.urandom(16) if salt is None else salt
    digest = hashlib.scrypt(password.encode(), salt=salt, **SCRYPT)
    return f"{salt.hex()}:{digest.hex()}"


def check_password(password, stored):
    salt, _ = stored.split(":")
    # compare_digest takes as long however much matches, so the time
    # doesn't give the hash away a byte at a time.
    return hmac.compare_digest(hash_password(password, bytes.fromhex(salt)),
                               stored)


def make_token(user_id):
    """A JWT for user_id, signed with HMAC-SHA256 (RFC 7519)."""
    header = encode_part({"alg": "HS256", "typ": "JWT"})
    # sub is a string in the RFC.
    payload = encode_part({"sub": str(user_id), "iat": int(time.time())})
    signed = f"{header}.{payload}"
    signature = hmac.new(SECRET, signed.encode(), hashlib.sha256).digest()
    return f"{signed}.{base64url(signature)}"


def encode_part(data):
    return base64url(json.dumps(data, separators=(",", ":")).encode())


def base64url(data):
    # The URL-safe alphabet, without the = padding, as JWTs use.
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
