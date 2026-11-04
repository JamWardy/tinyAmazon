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

| Endpoint | Request | Response |
|---|---|---|
| `POST /users` | Body: email, password | `User` |
| `POST /login` | Body: email, password | JWT |
| `GET /search?term=&cursor=&limit=` | Search term, pagination | `Partial<Item>[]` (summary fields) plus next cursor |
| `POST /listings` | Body: `Partial<Item>` (title, description, price, stock) | `Item` |
| `POST /orders` | Header: `Idempotency-Key`. Body: `{ itemId, quantity }` | `Order` |

### Status codes

| Endpoint | Status | When |
|---|---|---|
| `POST /users` | `201` | Created |
| | `400` | Email or password missing, or the body isn't JSON |
| | `409` | The email is taken |
| `POST /login` | `200` | The body is the JWT |
| | `400` | Email or password missing |
| | `401` | Wrong email or password, the same for both |
| `GET /search` | `200` | Results, perhaps none |
| | `400` | A bad `limit` or `cursor` |
| `POST /listings` | `201` | Created |
| | `400` | A field missing, or a bad value such as a negative price |
| | `401` | No token, or a bad one (from the gateway) |
| `POST /orders` | `201` | Placed and paid, or a retry of one (the same order) |
| | `400` | No `Idempotency-Key`, or a bad body such as `quantity` 0 |
| | `401` | No token, or a bad one (from the gateway) |
| | `404` | No such item |
| | `409` | Not enough stock, or a retry of an `EXPIRED` or `CANCELLED` order |
| | `422` | The same key with a different body |
| | `402` | The card was declined |
| | `502` | The payment provider failed |

### Errors

Every error, from every service, is a Problem Details body (RFC 9457),
with `Content-Type: application/problem+json`:

```json
{"title": "Not enough stock", "status": 409,
 "detail": "Item 5 has 1 left; you asked for 2."}
```

`title` is the same for every error of its kind, `status` repeats the
HTTP status, and `detail` says what went wrong this time. `type` is
left out, which means `about:blank`. tinyweb's own `404`, `405` and
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
WHERE title LIKE ? AND stock > 0 AND id > ?
ORDER BY id LIMIT ?;
```

Each result is an item's `id`, `title` and `price`. `limit` is 20 when
it's left out, and at most 100. The term is passed as `'%term%'`. The
first page passes `0` as the cursor. If a page is full, the next cursor is its last `id`; otherwise
there's no next page.

**`POST /orders`**

1. Look for a retry:

   ```sql
   SELECT * FROM orders WHERE user_id = ? AND idempotency_key = ?;
   ```

   If there's one with a different `item_id` or `quantity`: `422`. A
   `PAID` one: `201` with it. A `PENDING` one: carry on from step 3.
   An `EXPIRED` or `CANCELLED` one: `409`, and the client starts again
   with a new key.

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
   `EXPIRED`, which frees the stock, and answer `402`. Failed: `502`.

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
   `CANCELLED` with its `charge_id`, `COMMIT`, `POST /refunds`, and
   answer `409`.

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

- The payment provider is a fake one for now, `tinypay/`, its own
  process with `POST /charges`, which takes an idempotency key so a
  retry never charges twice, and `POST /refunds`.
- The gateway is our own reverse proxy, `tinyproxy/`, with routing and
  auth on top (`tinygateway/`), as Kong is nginx with plugins. The
  proxy accepts a request, sends it on to the server behind it and
  passes the reply back, with `502` when that server is down and `504`
  when it's too slow. The load balancer and the CDN are built on the
  same proxy later, one picking a server and the other adding a cache.
- The proxy handles many connections at once, so a slow order never
  holds up a search. It's one process with an event loop, as nginx,
  HAProxy and Envoy are: non-blocking sockets, and `select()` to find
  whichever is ready, with each connection a small state machine
  (reading the request, sending it on, waiting, sending the reply
  back). It's written on `select()` itself, not `asyncio`.
- The auth service owns users: sign-up, and log-in, which returns a
  JWT. The gateway routes each path to its service, checks the token on
  every write, answering `401` before the service sees it, and passes
  the user on to the service in a header. It removes any such header
  the client sent, so a client can't name a user itself.
- The services listen on `127.0.0.1` only, so nothing outside the
  machine can reach them except through the gateway.
- Search reads from a replica, so search load never slows checkout.
  Replication lag fits the "seconds stale" requirement.
- The Order service owns stock and orders, and is the only place
  correctness is enforced.

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
- **Search matches titles containing the term**, `title LIKE
  '%term%'`, ordered by `id`. The cursor is the last `id` seen, so the
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
