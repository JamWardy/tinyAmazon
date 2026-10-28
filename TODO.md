# TODO

A toy online shop, built from scratch to learn how each part works,
in the same layers a real deployment has, each in its own process:

```
browser ─► proxy / load balancer ─► HTTP server ──WSGI──► framework + shop app ─► TinySQL server
           (nginx's job, later)     (gunicorn's job)       (Flask's job)          (Postgres's job)
```

## Layout

One folder per part, as each is its own project in the real world:

```
tinyAmazon/
  tinysql/     the database        (Postgres's job)
  tinyhttp/    the HTTP server     (gunicorn's job)   ← step 1
  tinyweb/     the framework       (Flask's job)      ← step 2, once WSGI goes in
  shop/        the app: routes, templates, static/    ← step 2 onwards
```

- `tinysql/` is in C, with its own `TODO.md` for what the database
  needs for the shop. It gets a server in step 4.
- The rest is in Python, with no libraries beyond Python's own, so
  `socket`, not `http.server`.
- The imports show where one part ends and the next begins:
  `tinyhttp` never imports `shop`; it's given a WSGI app to run, as
  gunicorn is told `shop:app`. `shop` never imports `tinyhttp`, so it
  can run on real gunicorn instead. `tinyweb` sits between them, as
  Flask does.
- Later parts get folders of their own in the same way, such as
  `tinyproxy/` and `tinydns/`.

For step 1, before WSGI, `tinyhttp/` is just:

```
tinyhttp/
  __init__.py
  __main__.py   # so `python -m tinyhttp` starts it
  server.py     # socket, bind, listen, accept, read, respond
```

`request.py` (parsing) and `response.py` can be split out once
`server.py` gets long.

## Plan

TinySQL is paused until step 4. Steps 1 and 2 need no database.

### 1. The web server, up and running

- [x] Accept a connection, read a request, send a response, one
      connection at a time
- [x] Parse the request line and headers; answer with a status line,
      `Content-Type` and `Content-Length`
- [x] Bad requests get `400`
- [x] Break it on purpose: `nc localhost 8000` and type nothing, and
      every other request waits (see "Requests at once" below, and
      `tinyhttp/PRE_FORK.md`)

### 2. Static files and a hello-world page

- [ ] Serve files under `/static/`, with a `Content-Type` from the
      extension, and never a path outside the folder (`/static/../`)
- [ ] `Cache-Control`, `ETag` and `304 Not Modified`
- [ ] A hello-world page with some CSS
- [ ] A page showing a few rows from the seed, copied into a JSON file
      by hand, since the database comes in step 4
- [ ] WSGI between the server and the app (PEP 3333), then check it
      both ways: a real Flask app on our server, and our app on real
      gunicorn
- [ ] Routing: send `GET /products/5` to the code for a product page,
      answer `GET /health` with `200 OK`, and unknown paths with `404`

### 3. System design

In `DESIGN.md`. Design the shop first, then list what TinySQL lacks;
that list becomes TinySQL's work for step 4.

- [ ] Requirements: what a visitor and a customer can do, and what's
      out of scope
- [ ] Entities and how they relate (users, products, basket, orders,
      payments, reviews, sessions, ...)
- [ ] Pages and API: each route, its method, what it takes and returns,
      and its status codes
- [ ] The schema: tables, keys and constraints, and the queries behind
      each page
- [ ] New seed data for that schema, replacing `tinysql/seed/retail.sql`
      and `tinysql/shop.db`
- [ ] What TinySQL is missing for it (see `tinysql/TODO.md`)

### 4. The web server and the database, talking

- [ ] In `tinysql/`: a server, its wire protocol, parameters (`?`) and
      transactions per connection; see "Decisions" below
- [ ] A client in Python, so the shop can send queries
- [ ] Load the new seed into a fresh database
- [ ] Templates: fill in an HTML page from the query results
- [ ] The pages from step 3: products, product page, sign-up and log-in
      with sessions, basket, checkout (then a redirect to the order,
      Post/Redirect/Get), order history

### 5. Follow-ups

The shop and the database:

- [ ] The rest of `tinysql/TODO.md`: `UNIQUE`, `AUTOINCREMENT`,
      arithmetic, `CREATE INDEX`, `LIKE`, `OFFSET`, `JOIN`, ...
- [ ] Search, pages of results, writing reviews, addresses at checkout
- [ ] Proper auth: password hashing, session expiry, CSRF tokens
- [ ] A small JSON API, e.g. for the basket

Performance:

- [ ] Measure first: requests a second, and how long each query takes
- [ ] Pre-fork workers, as gunicorn does: a master binds the socket,
      forks several workers that each `accept()`, and restarts any that
      die (see `tinyhttp/PRE_FORK.md`)
- [ ] Keep-alive: several requests on one connection
- [ ] An event loop (`select` or `kqueue`), as nginx does: many
      connections in one process

In front of the shop:

- [ ] Reverse proxy: serves `/static/` itself, and reads slow clients'
      requests in full before passing them on
- [ ] Load balancer: the proxy, sharing requests round-robin between two
      app servers (`:8001` and `:8002`) using one TinySQL server
- [ ] DNS: `shop.local` in `/etc/hosts` first, then a small UDP server
      that answers for it
- [ ] CDN: a caching proxy that follows `Cache-Control` for `/static/`
- [ ] API gateway: in front of the JSON API, checking who's calling and
      limiting how often

## Notes for the design

Written for the old seed schema, as a starting point for step 3.

### The pages

Each page and the queries behind it. `?` is a value the server passes
in, never pasted into the SQL.

| Page | Queries |
|---|---|
| Products in a category | `SELECT * FROM products WHERE category_id = ? AND is_active = 1 ORDER BY price_cents LIMIT 20` |
| Product page | `SELECT * FROM products WHERE id = ?`, then `SELECT * FROM reviews WHERE product_id = ?` |
| Log in | `SELECT * FROM users WHERE email = ?` |
| Basket | `SELECT * FROM cart_items WHERE user_id = ?`, then each product by its `id` |
| Checkout | In a transaction: insert the order, insert each item, `UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?`, insert the payment, empty the basket |
| Order history | `SELECT * FROM orders WHERE user_id = ? ORDER BY order_date DESC` |

There's no `JOIN`, so a page that needs several tables runs one query
per table, and the server puts the results together.

### Checkout

The hardest part, because it must happen completely or not at all:

1. Read the basket.
2. `BEGIN`.
3. Insert the order, and get its new ID.
4. For each item: lower the product's stock, only if there's enough,
   then insert the order item with today's price.
5. Insert the payment.
6. Empty the basket.
7. `COMMIT`. If any step fails, such as an item out of stock,
   `ROLLBACK` instead, and nothing has changed.

The item's price is copied into `order_items.unit_price_cents`, so a
later price change doesn't change an old order.

### Logging in

- Store a hash of the password, never the password itself, using a
  slow hash made for passwords (bcrypt, scrypt or Argon2), not a fast
  one such as SHA-256. Python has `hashlib.scrypt`.
- After logging in, the server gives the browser a session ID in a
  cookie, and keeps a `sessions` table mapping each ID to its user. The
  ID is random and long enough that no one can guess it (`secrets`).
- Sessions live in the database, not in the app server's memory, so
  any app server can answer any request. That's what lets the load
  balancer work later.

## Decisions

- **TinySQL gets a network protocol, not a foreign function
  interface.** `database_load` reads the whole database into memory and
  `tinysql_run` saves it back. Several worker processes would each hold
  their own copy and overwrite each other's saves. One server that owns
  the data is how Postgres and MySQL work. It runs one statement at a
  time, so TinySQL not being safe across threads doesn't matter.
- **The web tier is in Python, from `socket` up.** Python's `socket` and
  `os.fork` are thin wrappers over the same system calls as C, and
  Flask and gunicorn are Python, so we can swap ours for theirs through
  WSGI to check our work. In C, most of the time would go on strings
  and buffers, which `tinysql/` already teaches.
- **HTML pages first, JSON later.** Pages made on the server teach more
  of HTTP: forms, redirects, status codes, cookies and `Content-Type`.
  A JSON API comes later, for the API gateway to sit in front of.
- **Requests at once, in stages,** as real servers did:
  1. One at a time. A client that connects and sends nothing blocks
     everyone (the Slowloris attack). That's why gunicorn's docs say to
     put it behind nginx.
  2. Pre-fork workers, gunicorn's model.
  3. An event loop, nginx's model.
- **No TLS.** Writing it by hand is too much; use a library, or leave
  it out.
