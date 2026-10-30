# TODO

A toy online marketplace, built from scratch to learn how each part
works, in the same layers a real deployment has, each in its own
process. The design is in `DESIGN.md`:

```
client ─► API gateway ─► HTTP server ──WSGI──► framework + service ─► TinySQL server
          (auth, routing) (gunicorn's job)       (Flask's job)          (Postgres's job)
```

The gateway routes to four services, each its own process: search,
which reads a TinySQL read replica, and auth, items and orders, which
use the primary. The order service also calls a payment provider.

## Layout

One folder per part, as each is its own project in the real world:

```
tinyAmazon/
  tinysql/     the database        (Postgres's job)
  tinyhttp/    the HTTP server     (gunicorn's job)   ← step 1
  tinyweb/     the framework       (Flask's job)      ← step 2, once WSGI goes in
  shop/        the services: auth, search, items and orders  ← step 4
  db/          our database: schema, seed data and data files
```

- `tinysql/` is in C, with its own `TODO.md` for what the database
  needs for the shop. It gets a server in step 4.
- `db/` is the shop's own database, run on TinySQL's server, as an app
  keeps its schema in its own repo, never in Postgres's:

  ```
  db/
    schema.sql    the CREATE TABLEs and the index, from DESIGN.md
    seed.sql      sample rows
    primary.db    the data files, git-ignored
    replica.db
  ```
- The rest is in Python, with no libraries beyond Python's own, so
  `socket`, not `http.server`.
- The imports show where one part ends and the next begins:
  `tinyhttp` never imports `shop`; it's given a WSGI app to run, as
  gunicorn is told `shop:app`. `shop` never imports `tinyhttp`, so it
  can run on real gunicorn instead. `tinyweb` sits between them, as
  Flask does.
- Later parts get folders of their own in the same way, such as the
  gateway, `tinyproxy/` and `tinydns/`.

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

- [x] Serve files under `/static/`, with a `Content-Type` from the
      extension, and never a path outside the folder (`/static/../`)
- [x] `Cache-Control`, `ETag`, `Last-Modified` and `304 Not Modified`
- [x] A hello-world page with some CSS
- [x] WSGI between the server and the app (PEP 3333), then check it
      both ways: a real Flask app on our server, and our app on real
      gunicorn
- [x] Routing: send `GET /products/5` to the code for a product page,
      answer `GET /health` with `200 OK`, and unknown paths with `404`

### 3. System design

In `DESIGN.md`. Design the shop first, then list what TinySQL lacks;
that list becomes TinySQL's work for step 4.

- [x] Requirements: an eBay-style marketplace. Sellers list items with
      a stock count, customers search them and order one listing at a
      time
- [x] Entities: users (buyers and sellers alike), items (listings) and
      orders
- [x] API: `GET /search`, `POST /listings` and `POST /orders`, with a
      JWT on every write; the ordering flow (reserve, pay, confirm) and
      idempotency keys
- [x] Architecture: an API gateway, four services, a TinySQL primary
      and a read replica
- [x] Each endpoint's status codes: see `DESIGN.md`
- [x] The schema: column types, keys and constraints, and the queries
      behind each endpoint; see `DESIGN.md`
- [x] What TinySQL is missing for it: see `tinysql/TODO.md`

### 4. The marketplace, as designed

- [ ] In `tinysql/`: a server, its wire protocol, parameters (`?`) and
      transactions per connection, one at a time, with an idle time
      limit. One process, with a `select()` loop over every connection;
      see "Decisions" below and `DESIGN.md`
- [ ] A client in Python, so the services can send queries
- [ ] `db/schema.sql`, from the schema in `DESIGN.md`, and
      `db/seed.sql`, the sample rows for it; delete
      `tinysql/seed/retail.sql` and `tinysql/shop.db`
- [ ] Load `db/schema.sql` and `db/seed.sql` into a fresh
      `db/primary.db`
- [ ] A read replica, `db/replica.db`, a few seconds behind the primary
- [ ] A script in `db/` that starts the primary and the replica
- [ ] JSON in tinyweb: read a JSON body, with `400` if it isn't, and
      return one with `Content-Type: application/json`; and `402` and
      `502` in `REASONS`
- [ ] The auth service: `POST /users` and `POST /login`, which returns
      a JWT signed with HMAC-SHA256 (`hmac`, `hashlib`, `base64`,
      `json`), on the primary
- [ ] The item service: `POST /listings`, on the primary
- [ ] The search service: `GET /search`, on the replica
- [ ] The fake payment provider, `tinypay/`
- [ ] The order service: `POST /orders`: reserve, pay and confirm, with
      idempotency keys, on the primary
- [ ] The API gateway: checks the JWT on every write, passes the user
      on to the service, and routes each path to its service

### 5. Follow-ups

The shop and the database:

- [ ] The rest of `tinysql/TODO.md`: foreign keys, `JOIN`, ...
- [ ] The cleanup job: mark old `PENDING` orders `EXPIRED`. Optional,
      as nothing depends on it
- [ ] Token expiry and refresh
- [ ] Pages that call the API

Performance:

- [ ] Measure first: requests a second, and how long each query takes
- [ ] Pre-fork workers, as gunicorn does: a master binds the socket,
      forks several workers that each `accept()`, and restarts any that
      die (see `tinyhttp/PRE_FORK.md`)
- [ ] Keep-alive: several requests on one connection
- [ ] An event loop (`select` or `kqueue`), as nginx does: many
      connections in one process

In front of the shop:

- [ ] Rate limiting in the API gateway
- [ ] Reverse proxy: serves `/static/` itself, and reads slow clients'
      requests in full before passing them on
- [ ] Load balancer: the proxy, sharing requests round-robin between two
      copies of a service (`:8001` and `:8002`) using one TinySQL server
- [ ] DNS: `shop.local` in `/etc/hosts` first, then a small UDP server
      that answers for it
- [ ] CDN: a caching proxy that follows `Cache-Control` for `/static/`

## Notes for the design

### Passwords

Store a hash of the password, never the password itself, using a slow
hash made for passwords (bcrypt, scrypt or Argon2), not a fast one such
as SHA-256. Python has `hashlib.scrypt`.

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
- **A JSON API,** as `DESIGN.md` has, behind an API gateway. Pages that
  call it come later.
- **Requests at once, in stages,** as real servers did:
  1. One at a time. A client that connects and sends nothing blocks
     everyone (the Slowloris attack). That's why gunicorn's docs say to
     put it behind nginx.
  2. Pre-fork workers, gunicorn's model.
  3. An event loop, nginx's model.
- **No TLS.** Writing it by hand is too much; use a library, or leave
  it out.
