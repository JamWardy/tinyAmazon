# Design: an eBay-style marketplace

Step 3 of `TODO.md`.

## Functional requirements

- Sellers create listings with a stock count.
- Customers search for listings.
- Customers order a listing (one listing per order for now).

## Non-functional requirements

- **Ordering: consistency over availability.** You can never order an
  item that isn't available, and nothing is oversold. Better to reject
  an order than oversell.
- **Search: availability and low latency over consistency.** Search is
  read-heavy and eventually consistent. New listings and sold-out items
  show up within seconds. A stale result costs the user one click,
  because checkout re-validates.
- Pages already open in a browser are not updated live; correctness is
  enforced at checkout.

## Entities

- **User**: one entity for both buyers and sellers.
  - `id, email, password_hash`
  - `email` is unique; `password_hash` is an `hashlib.scrypt` hash,
    never the password itself. scrypt is slow on purpose, as hashes
    for passwords should be; a fast one such as SHA-256 is easy to
    guess against
  - `password_hash` is `<salt>:<hash>`, both hex: a random 16-byte
    salt, and the 32-byte `hashlib.scrypt` of the password with it, at
    `n=2**14, r=8, p=1, dklen=32`
- **Item** (listing): one seller's offer. The same product sold by two
  sellers is two Items.
  - `id, seller_id, title, description, price, stock`
- **Order**: one buyer, one Item, a quantity.
  - `id, user_id, item_id, quantity, unit_price, status, expires_at,
    idempotency_key, charge_id, created_at`
  - `unit_price` is the item's price when it's reserved, and what's
    charged, so a later price change doesn't change the order
  - `charge_id` is the payment provider's ID for the charge, for a
    refund
  - `status` is `PENDING`, `PAID`, `EXPIRED` (an unpaid reservation
    that ran out) or `CANCELLED` (refunded)
  - `price` is in pence, and `expires_at` and `created_at` in Unix
    seconds, all `INT`. The app passes the current time as a
    parameter, as TinySQL has no `now()`
  - Unique constraint on `(user_id, idempotency_key)`

## API

All write endpoints require a JWT. User and seller IDs come from the
token, never the request body. The auth service issues the token,
signed with HMAC-SHA256, and the gateway checks it.

The token is a JWT with the header `{"alg": "HS256", "typ": "JWT"}`
and the payload `{"sub": "<user id>", "iat": <now>}`, signed with the
secret in the `SHOP_JWT_SECRET` environment variable, which the auth
service and the gateway share; neither starts without it. It has no
`exp` until token expiry, a follow-up in `TODO.md`. The client sends
it in an `Authorization: Bearer <token>` header. How the gateway
checks it is in `tinygateway/DESIGN.md`.

Bodies are JSON, with keys in camelCase: an `Item` is `{id, sellerId,
title, description, price, stock}`, a `User` is `{id, email}`, and an
`Order` is `{id, userId, itemId, quantity, unitPrice, status,
expiresAt, idempotencyKey, chargeId, createdAt}`.

| Endpoint | Request | Response |
|---|---|---|
| `POST /users` | Body: email, password | `User` |
| `POST /login` | Body: email, password | `{ token }`, the JWT |
| `GET /search?term=&cursor=&limit=` | Search term, pagination | `{ items, nextCursor }`: `Partial<Item>[]` (summary fields), and the next cursor or `null` |
| `POST /listings` | Body: `Partial<Item>` (title, description, price, stock) | `Item` |
| `POST /orders` | Header: `Idempotency-Key`. Body: `{ itemId, quantity }` | `Order` |

### Status codes

| Endpoint | Status | When |
|---|---|---|
| `POST /users` | `201` | Created |
| | `400` | Email or password missing, or the body isn't JSON |
| | `409` | The email is taken |
| `POST /login` | `200` | The body has the JWT |
| | `400` | Email or password missing |
| | `401` | Wrong email or password, the same for both |
| `GET /search` | `200` | Results, perhaps none |
| | `400` | A bad `limit` or `cursor` |
| `POST /listings` | `201` | Created |
| | `400` | A field missing, or a bad value such as a negative price |
| | `401` | No token, or a bad one (from the gateway) |
| `POST /orders` | `201` | Placed and paid, or a retry of one (the same order) |
| | `400` | No `Idempotency-Key`, or one over 255 characters, or a bad body such as `quantity` 0 |
| | `401` | No token, or a bad one (from the gateway) |
| | `404` | No such item |
| | `409` | Not enough stock, or a retry of an `EXPIRED` or `CANCELLED` order |
| | `422` | The same key with a different body |
| | `402` | The card was declined |
| | `502` | The payment provider failed, or a refund did |

Every `POST` also answers `415` when its `Content-Type` isn't
`application/json`.

### Errors

Every error, from every service, is a Problem Details body (RFC 9457),
with `Content-Type: application/problem+json`:

```json
{"title": "Not enough stock", "status": 409,
 "detail": "Item 5 has 1 left; you asked for 2."}
```

`title` is the same for every error of its kind, `status` repeats the
HTTP status, and `detail` says what went wrong this time. `type` is
left out, which means `about:blank`. Each service's own kinds of error
have titles of their own:

| Status | Title | When |
|---|---|---|
| `400` | Missing email or password | `POST /users` or `/login` without them |
| `409` | Email already registered | `POST /users` with a taken email |
| `401` | Wrong email or password | `POST /login`, either one wrong |
| `401` | Not logged in | No `X-User-Id`, or a bad one |
| `400` | Invalid listing | `POST /listings` with a field missing or bad |
| `400` | Invalid page | `GET /search` with a bad `limit` or `cursor` |
| `400` | Missing Idempotency-Key | `POST /orders` without one |
| `400` | Invalid order | `POST /orders` with a bad body, or a key over 255 characters |
| `404` | No such item | `POST /orders` for an item that doesn't exist |
| `409` | Not enough stock | `POST /orders` for more than is free, or the stock went while paying |
| `409` | Order closed | A retry of an `EXPIRED` or `CANCELLED` order |
| `422` | Idempotency-Key reused | The same key with a different item or quantity |
| `402` | Card declined | The payment provider declined the charge |
| `502` | Payment failed | The payment provider failed |

Any other error, such as a body that isn't JSON, has the status's own
words as its title, such as "Bad Request". tinyweb's own `404`, `405` and
`500` take the same shape, and so do the gateway's `401`, `502` and
`504`.

## Schema

```sql
CREATE TABLE users (
    id            INT PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL      -- salt and scrypt hash, as hex
);

CREATE TABLE items (
    id          INT PRIMARY KEY AUTOINCREMENT,
    seller_id   INT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT,                -- may be left out
    price       INT NOT NULL,        -- pence
    stock       INT NOT NULL
);

CREATE TABLE orders (
    id              INT PRIMARY KEY AUTOINCREMENT,
    user_id         INT NOT NULL,
    item_id         INT NOT NULL,
    quantity        INT NOT NULL,
    unit_price      INT NOT NULL,    -- pence, from the item when reserved
    status          TEXT NOT NULL,   -- PENDING, PAID, EXPIRED or CANCELLED
    expires_at      INT NOT NULL,    -- Unix seconds
    idempotency_key TEXT NOT NULL,
    charge_id       TEXT,            -- set once paid
    created_at      INT NOT NULL,    -- Unix seconds
    UNIQUE (user_id, idempotency_key)
);

CREATE INDEX orders_item_expires ON orders (item_id, expires_at);
```

Values such as a negative price or a `quantity` of 0 are rejected by
the service with `400`, before any SQL runs.

## Queries

`?` is a value passed in, never pasted into the SQL. `now` is the
current time in Unix seconds, from the service.

**`POST /users`**

```sql
INSERT INTO users (email, password_hash) VALUES (?, ?)
RETURNING id, email;
```

`RETURNING` gives back the new row, with the `id` TinySQL chose, for
the `201`'s body; the hash stays out of it.

A duplicate email breaks the `UNIQUE` constraint: `409`.

**`POST /login`**

```sql
SELECT id, password_hash FROM users WHERE email = ?;
```

No row, or a hash that doesn't match: `401`.

**`POST /listings`**

```sql
INSERT INTO items (seller_id, title, description, price, stock)
VALUES (?, ?, ?, ?, ?) RETURNING *;
```

**`GET /search`**

```sql
SELECT id, title, price FROM items
WHERE title ILIKE ? AND stock > 0 AND id > ?
ORDER BY id LIMIT ?;
```

Each result is an item's `id`, `title` and `price`. `limit` is 20 when
it's left out, and at most 100. The term is passed as `'%term%'`, with
a `\` put before each `%`, `_` and `\` in it, so they match only
themselves: `50%` is passed as `'%50\%%'`. The first page passes `0` as
the cursor. If a page is full, the next cursor is its last `id`; otherwise
there's no next page. A `limit` outside 1 to 100, or a `cursor` that
isn't a whole number from 0 up, is `400`.

**`POST /orders`**

1. Look for a retry:

   ```sql
   SELECT * FROM orders WHERE user_id = ? AND idempotency_key = ?;
   ```

   If there's one with a different `item_id` or `quantity`: `422`. A
   `PAID` one: `201` with it. A `PENDING` one: carry on from step 3.
   An `EXPIRED` or `CANCELLED` one: `409`, and the client starts again
   with a new key. A `CANCELLED` one is refunded again first, in case
   its refund failed; the refund's key makes that a no-op if it
   didn't.

   `quantity` is a whole number from 1 up that fits `INT`, and the key
   any string of 1 to 255 characters, as Stripe allows.

2. Reserve:

   ```sql
   BEGIN;
   SELECT price, stock FROM items WHERE id = ? FOR UPDATE;  -- none: 404
   SELECT SUM(quantity) FROM orders
   WHERE item_id = ? AND status = 'PENDING' AND expires_at > ?;  -- now
   -- stock minus that sum is less than quantity: ROLLBACK, 409
   INSERT INTO orders (user_id, item_id, quantity, unit_price, status,
                       expires_at, idempotency_key, created_at)
   VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?)  -- expires_at is now + 600
   RETURNING *;  -- its id is the payment's idempotency key
   COMMIT;
   ```

   If the `INSERT` breaks the `UNIQUE` constraint, a retry got there
   first: `ROLLBACK` and go back to step 1.

3. Pay: `POST /charges` to the payment provider, for `quantity ×
   unit_price`, with the order's `id` as its idempotency key, so paying
   again after a crash never charges twice. Declined: set the order
   `EXPIRED`, which frees the stock, and answer `402`. Failed: `502`,
   and the order stays `PENDING`, so a retry with the same key carries
   on from here. Failed means no answer within 2 seconds to connect or
   10 to read, or any reply but a `201` or a `402`, such as a `5xx`.

4. Confirm:

   ```sql
   BEGIN;
   SELECT stock FROM items WHERE id = ? FOR UPDATE;
   -- if the order has expired, check the stock is still free, as in step 2
   UPDATE orders SET status = 'PAID', charge_id = ? WHERE id = ?;
   UPDATE items SET stock = stock - ? WHERE id = ?;
   COMMIT;
   ```

   If it expired and the stock went to someone else: set the order
   `CANCELLED` with its `charge_id`, `COMMIT`, `POST /refunds` with the
   key `refund-<order id>`, and answer `409`, or `502` if the refund
   failed.

   A retry of the same order may have confirmed it while this one was
   paying, so the order is read again after the lock, and left as it
   is unless it's still `PENDING`.

**The cleanup job** (optional)

```sql
UPDATE orders SET status = 'EXPIRED'
WHERE status = 'PENDING' AND expires_at <= ?;  -- now
```

## High-level architecture

```
Client → API Gateway (auth, routing)
           ├── Auth service       → tinysql primary
           ├── Search service     → tinysql read replica
           ├── Item CRUD service  → tinysql primary
           └── Order service      → tinysql primary
                                  → third-party payment provider
```

- The payment provider is a fake one for now, tinypay, in
  `shop/tinypay.py`: a simple mock of a third party, as Stripe is, in
  its own process on port 9001. See "The payment provider" below.
- The gateway is our own reverse proxy, `tinyproxy/`, with routing and
  auth on top (`tinygateway/`), as Kong is nginx with plugins. The
  proxy accepts a request, sends it on to the server behind it and
  passes the reply back, with `502` when that server is down and `504`
  when it's too slow. The load balancer and the CDN are built on the
  same proxy, one picking a server and the other adding a cache.
- tinyproxy is a simple nginx, in C, and tinygateway a simple Kong, in
  Python, for learning how they work. Each follows its original's
  behaviour, so what it teaches holds for the real one, but
  understanding comes before copying: where a name or a quirk of the
  original would get in the way, it uses a clearer one. Neither uses
  any of its original's code. As Kong's Lua runs inside nginx
  through OpenResty, tinyproxy embeds Python and calls the gateway's
  code at nginx's phases. How tinyproxy works is in
  `tinyproxy/DESIGN.md`.
- The proxy handles many connections at once, so a slow order never
  holds up a search. It's one process with an event loop, as nginx,
  HAProxy and Envoy are: non-blocking sockets, and `select()` to find
  whichever is ready, with each connection a small state machine
  (reading the request, sending it on, waiting, sending the reply
  back).
- The gateway's config is `shop/gateway.conf`, as it's the shop's
  setup, not tinyproxy's. It listens on port 8000, on every interface,
  as the shop's only way in. `just run` starts it last, once the
  services are up; `make` in `tinyproxy/` builds it first, as for
  TinySQL's server. In it:
  - Each service is a named `upstream` (`auth`, `items`, `search`,
    `orders`) with its one `host` and `keepalive_max_idle 16;`, the
    number in nginx's own `keepalive` example.
  - Each path is an exact location: `location = /users` and `= /login`
    to auth, `= /search` to search, `= /listings` to items and `=
    /orders` to orders, with the jwt plugin on `/listings` and
    `/orders`. Any other path gets the gateway's `404`.
  - The cors plugin is on every path, set once in the `server` block,
    and before jwt, with `plugins "cors jwt"`, on `/listings` and
    `/orders`. It allows `GET, POST`, the headers `Authorization,
    Content-Type, Idempotency-Key`, and a max age of 600 seconds, from
    the frontend's origin, `http://localhost:8080`.
  - The `server` block sends HTTP/1.1 with `Host $host`,
    `X-Forwarded-For $proxy_add_x_forwarded_for`, `Connection ""` for
    upstream keep-alive, and `X-User-Id ""`, and logs to `/dev/stdout`.
    The timeouts and body size are tinyproxy's defaults.
  - tinypay isn't behind it, as a third party isn't.
- The auth service owns users: sign-up, and log-in, which returns a
  JWT. The gateway routes each path to its service, checks the token on
  every write but sign-up and log-in, answering `401` before the service sees it, and passes
  the user's id on to the service in an `X-User-Id` header. It removes
  any such header the client sent, so a client can't name a user
  itself: the jwt plugin does on the routes it checks, and
  `shop/gateway.conf`'s `server` block sets `proxy_set_header
  X-User-Id "";` for the rest. A location that sets a
  `proxy_set_header` of its own inherits none of the server's, so it
  must repeat that line. A service that needs the user answers `401` itself if the
  header is missing or isn't an id, so it never acts for no one.
- The services listen on `127.0.0.1` only, so nothing outside the
  machine can reach them except through the gateway.
- Search reads from a replica, so search load never slows checkout.
  Replication lag fits the "seconds stale" requirement.
- The TinySQL primary listens on port 5480, and the replica on 5481.
  The services listen on 8001 (auth), 8002 (items), 8003 (search) and
  8004 (orders).
- The Order service owns stock and orders, and is the only place
  correctness is enforced.

## The frontend

Pages in the browser that call the API through the gateway, as a site
on one origin calling an API on another does, with CORS between them.

- `shop/frontend.py`, a tinyweb app, serves them from `shop/web/` on
  `http://localhost:8080`, started by `just run`. They must be opened
  at `localhost`, not `127.0.0.1`, as the gateway allows that origin
  exactly. They call the API at `http://localhost:8000`.
- Plain HTML, CSS and JavaScript with `fetch`: no libraries and no
  build step.
- Three pages, as the API has no endpoint for one item or a user's
  orders:
  - `/`: search, with "More" for the next page, and a quantity and
    Buy on each result.
  - `/login`: log in, or sign up and then log in.
  - `/sell`: a new listing, showing the `Item` made.
- The JWT is kept in `localStorage`, so it survives a reload, and
  "Log out" removes it. Any script on the page can read it, so a
  cross-site scripting bug would leak it; an `HttpOnly` cookie would
  not, but needs credentialed CORS and the gateway reading cookies. A
  `401` removes it and sends the user to `/login`.
- Buying follows "Ordering flow": each Buy makes a new
  `Idempotency-Key` with `crypto.randomUUID()`. A network error or a
  `502` turns the button to "Try again", which sends the same key; any
  other reply ends that attempt, so the next Buy gets a new key.
- An error shows its Problem Details `title` and `detail`.

## The payment provider

tinypay is a mock of a third party, so it keeps to its own API, not the
shop's: its errors aren't Problem Details. Every charge succeeds, so
the order service's `402` is there for a real provider.

| Endpoint | Request | Response |
|---|---|---|
| `POST /charges` | Body: `{ amount }`, in pence, from 1 up | `201 { id, amount, status }`: `id` is `ch_` and 24 random hex digits; `status` is `"succeeded"` |
| `POST /refunds` | Body: `{ charge }`, a charge's `id` | `201 { id, charge, amount }`: `id` is `re_` and 24 random hex digits; the whole amount is refunded |

- Every request sends `Authorization: Bearer <key>`, the key in the
  `TINYPAY_SECRET` environment variable, which tinypay and the order
  service share; tinypay won't start without it.
- Every request sends an `Idempotency-Key` header. The first reply to a
  key is kept and given back to every retry with it, without charging
  or refunding again. The order service sends the order's `id` for its
  charge, and `refund-<order id>` for its refund.
- Charges, refunds and kept replies are held in memory, so a restart
  forgets them.

Errors are `{"error": {"code": ..., "message": ...}}`, with codes as
Stripe's:

| Status | Code | When |
|---|---|---|
| `400` | `invalid_request` | No `Idempotency-Key`, or a bad body, such as an `amount` of 0 |
| `401` | `invalid_api_key` | No key, or the wrong one |
| `404` | `resource_missing` | A refund of a charge that doesn't exist |
| `409` | `charge_already_refunded` | A second refund of a charge, under a new key |
| `415` | `invalid_request` | A `Content-Type` that isn't `application/json` |
| `422` | `idempotency_key_reused` | A key sent again with a different path or body |

Any other status, such as tinyweb's `405`, has the status's words in
snake case as its code, such as `method_not_allowed`.

## Ordering flow

1. The client generates an idempotency key (UUID) once per checkout
   attempt and reuses it on every retry. The server rejects order
   requests without a key.
2. **Reserve**, in one transaction:
   1. Lock the item row (`SELECT ... FOR UPDATE`).
   2. Calculate `available = stock` minus the quantity in `PENDING`
      orders where `expires_at > now()`.
   3. If enough is available, insert a `PENDING` order with
      `expires_at` about ten minutes ahead. Otherwise, reject.
3. **Pay** via the third-party provider.
4. **Confirm**, in one transaction: lock the item row, mark the order
   `PAID`, and decrement stock. If the reservation expired and someone
   else took the unit, cancel and refund (rare).
5. **Retries**: a repeated idempotency key returns the existing order.
   The unique constraint covers retries that arrive at the same moment.
   A retry of a `PENDING` order carries on from paying. A repeated key
   with a different body gets `422`.

All of this is one `POST /orders` request, which answers `201` with the
`PAID` order.

## Key decisions

- **TinySQL is one server process with an event loop.** `select()`
  waits on every connection at once, and the server runs one statement
  at a time, from whichever is ready, as Redis does. Services talk to
  it over a socket rather than linking TinySQL themselves: TinySQL
  loads the whole database into memory and saves it back, so several
  processes each holding a copy would overwrite each other's saves. One
  server that owns the data is how Postgres and MySQL work. TinySQL
  locks a database file while it has it open, so a second process,
  such as a REPL, fails with "database is in use" rather than
  overwriting it, as Postgres's `postmaster.pid` stops a second server.
- **TinySQL runs one transaction at a time**, as SQLite and VoltDB do,
  holding the others until `COMMIT` or `ROLLBACK`. So `FOR UPDATE`
  holds without row locks: a second order for the item waits, then
  sees the new stock. A transaction left idle too long is rolled back,
  as Postgres's `idle_in_transaction_session_timeout` does, so a stalled
  client can't block everyone.
- **Search ignores reservations.** It shows anything with `stock > 0`.
  Reserved items still appear, and checkout handles the rest.
- **Search matches titles containing the term, ignoring case**, `title
  ILIKE '%term%'`, ordered by `id`. It reads every item, as no index
  finds text in the middle of a title. The cursor is the last `id` seen, so the
  next page is `WHERE id > ?`, with no `OFFSET`.
- **The replica copies the primary by a log of statements**, as MySQL's
  statement-based replication does: the primary sends each change to
  the replica after it commits.
- **Reservations live in TinySQL, not Redis.** Expiry is calculated at
  read time, so no job has to run for correctness. A Redis-only
  reservation can be lost on restart and lead to overselling.
- **Background jobs are optional.** A cleanup job may mark old pending
  orders `EXPIRED`, but nothing depends on it running on time. An index
  on `(item_id, expires_at)` keeps the availability check fast.
