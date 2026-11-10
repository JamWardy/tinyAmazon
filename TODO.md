# TODO

A toy online marketplace, built from scratch to learn how each part
works, in the same layers a real deployment has, each in its own
process.

`DESIGN.md` is the one place that says how the system works. This file
lists the work, in order, and points there rather than repeating it.

```
client ─► API gateway ─► HTTP server ──WSGI──► framework + service ─► TinySQL server
          (Kong's job)    (gunicorn's job)       (Flask's job)          (Postgres's job)
```

## Layout

One folder per part, as each is its own project in the real world:

```
tinyAmazon/
  tinysql/     the database        (Postgres's job)
  tinysqlclient/ its Python client (psycopg's job)    ← step 4
  tinyrequests/ an HTTP client     (requests' job)    ← step 4
  tinyhttp/    the HTTP server     (gunicorn's job)   ← step 1
  tinyweb/     the framework       (Flask's job)      ← step 2, once WSGI goes in
  shop/        the shop itself: its services, its database, and
               tinypay, the fake payment provider        ← step 4
  tinyproxy/   the reverse proxy, in C (nginx's job)  ← step 4
  tinygateway/ the API gateway, in Python, run by tinyproxy
               (Kong's job)                        ← step 4
```

- `tinysql/` is in C, with its own `TODO.md` for what the database
  needs for the shop. It gets a server in step 4.
- `tinyproxy/` is in C too, as nginx is, with its own `DESIGN.md` and
  `TODO.md`, and so has `tinygateway/`.
- `shop/` is our app: the auth, search, items and orders services, and
  `shop/db/`, the shop's own database, run on TinySQL's server, as an
  app keeps its schema in its own repo, never in Postgres's. Everything
  outside `shop/` is the technology it runs on:

  ```
  shop/db/
    schema.sql    the CREATE TABLEs and the index, from DESIGN.md
    seed.sql      sample rows
    primary.db    the data files, git-ignored
    replica.db
  ```
- The rest is in Python, with no libraries beyond Python's own, so
  `socket`, not `http.server`.
- The imports show where one part ends and the next begins:
  `tinyhttp` never imports `shop`; it's given each service's WSGI app
  to run. `shop` never imports `tinyhttp`; they meet only through WSGI.
  `tinyweb` sits between them, as Flask does. The services run only on
  tinyhttp: Flask and gunicorn are used nowhere but `tinyAmazonTest/`,
  to check that tinyhttp and tinyweb keep to WSGI.
- Later parts get folders of their own in the same way, such as
  `tinydns/`.

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

All in `DESIGN.md`, except the last, which is in `tinysql/TODO.md`.

- [x] Requirements
- [x] Entities
- [x] API and status codes
- [x] Schema and queries
- [x] Architecture
- [x] The ordering flow
- [x] What TinySQL is missing for it

### 4. The marketplace, as designed

Each part is built as `DESIGN.md` describes it, in this order.

1. The database server:
   - [x] In `tinysql/`: the server, the file lock and replication, in
         `tinysql/TODO.md`
2. Its client:
   - [x] `tinysqlclient/`, a TinySQL client in Python, so the services
         can send queries, in `tinysqlclient/TODO.md`
3. Our database, in `shop/db/`:
   - [x] `shop/db/schema.sql`, from the schema in `DESIGN.md`, and
         `shop/db/seed.sql`, the sample rows for it, by hand: three
         users (two sellers and a buyer, each with the password
         `password`), about 30 items, some sold out and some with `%`
         or `_` in the title for search's escaping, and no orders;
         delete `tinysql/seed/retail.sql` and `tinysql/shop.db`
   - [x] `shop/db/reset.sh`: deletes both data files and loads
         `schema.sql` and `seed.sql` into a fresh `primary.db` through
         the REPL
   - [x] `just run`, in `justfile`: starts the primary and the read
         replica, on the ports in `DESIGN.md`, then every service; the
         replica fills `replica.db` from the primary's snapshot, and
         Ctrl-C stops them all
4. The web server and the framework:
   - [x] tinyhttp's step 4, in `tinyhttp/TODO.md`
   - [x] tinyweb's step 4, in `tinyweb/TODO.md`
5. The services that need no other service, one module each in
   `shop/`, with what they share in `shop/common.py`, each started
   by `just run`:
   - [x] The auth service, `shop/auth.py`
   - [x] The item CRUD service, `shop/items.py`
   - [x] The search service, `shop/search.py`
6. Paying:
   - [x] `tinyrequests/`, an HTTP client in Python, so the order
         service can call tinypay, in `tinyrequests/TODO.md`
   - [x] tinypay, the fake payment provider, `shop/tinypay.py`
7. The order service:
   - [x] `shop/payments.py`: charging and refunding through tinypay,
         on `tinyrequests/`, as `DESIGN.md` describes under
         "`POST /orders`" and "The payment provider"
   - [x] The order service, `shop/orders.py`
8. The reverse proxy and the API gateway, in stages, as
   `tinyproxy/DESIGN.md` and "High-level architecture" in `DESIGN.md`
   describe. tinyproxy's stages are in `tinyproxy/TODO.md`:
   - [x] 1. HTTP forwarding (tinyproxy)
   - [x] 2. Path-based routing (tinyproxy)
   - [x] 3. Host-based routing (tinyproxy)
   - [x] 4. Upstream pools (tinyproxy)
   - [x] 5. Keep-alive, with clients and to the services (tinyproxy)
   - [x] 6. Load balancing: round robin, least connections, hashing
         (tinyproxy)
   - [ ] 7. Health checks:
     - [x] Passive (tinyproxy)
     - [ ] Active (tinygateway), after stage 8, as it runs in the
           gateway's Python, with timers and non-blocking sockets for it
   - [x] 8. Middleware: phases with Python embedded, in
         `tinyproxy/TODO.md`, and the plugins run at them, in
         `tinygateway/TODO.md`
   - [x] 9. Authentication: the JWT check and `X-User-Id`
         (tinygateway)
   - [ ] 10. Rate limiting (tinygateway)
   - [ ] 11. Caching (tinyproxy)
   - [ ] 12. Retries (tinyproxy)
   - [ ] 13. Observability: logs and `stub_status` (tinyproxy),
         metrics and tracing (tinygateway)
   - [x] `shop/gateway.conf`, started by `just run` on port 8000,
         once stage 9 is done, as "High-level architecture" in
         `DESIGN.md` describes
   - [ ] Two search services behind one pool in `shop/gateway.conf`,
         so stage 7's passive health checks have something to do

### 5. Follow-ups

The docs:

- [ ] Rewrite every `DESIGN.md` (the top level, `tinyproxy/`,
      `tinygateway/` and the rest) so a person can read it. They're
      written for agents for now: long, dense and hard to follow.

The shop and the database:

- [ ] The rest of `tinysql/TODO.md`: foreign keys, `JOIN`, ...
- [ ] The cleanup job (optional; see `DESIGN.md`)
- [ ] Token expiry and refresh
- [x] Pages that call the API, as "The frontend" in `DESIGN.md`
      describes: `shop/frontend.py` and `shop/web/`, started by `just
      run`, with `cors_origins` in `shop/gateway.conf`
- [ ] A health endpoint on each service, for stage 7's active health
      checks to probe, and for `just run` to wait on, in place of
      `nc -z`'s empty connections

Performance:

- [ ] Measure first: requests a second, and how long each query takes
- [ ] Pre-fork workers, as gunicorn does: a master binds the socket,
      forks several workers that each `accept()`, and restarts any that
      die (see `tinyhttp/PRE_FORK.md`)
- [ ] An event loop (`select` or `kqueue`), as nginx does: many
      connections in one process

In front of the shop:

- [ ] `tinyproxy/` serves `/static/` itself
- [ ] DNS: `shop.local` in `/etc/hosts` first, then a small UDP server
      that answers for it

## Decisions

How we build it. Decisions about the system itself are in `DESIGN.md`.

- **The web tier is in Python, from `socket` up.** Python's `socket` and
  `os.fork` are thin wrappers over the same system calls as C, and
  Flask and gunicorn are Python, so we can swap ours for theirs through
  WSGI to check our work. In C, most of the time would go on strings
  and buffers, which `tinysql/` already teaches.
- **Except the proxy, which is in C, as nginx is.** Each part is
  written in its original's language, so tinyproxy's loop, buffers and
  phases are built as nginx's are. tinygateway is Python embedded in
  it, as Kong is Lua embedded in nginx.
- **Requests at once, in stages,** as real servers did:
  1. One at a time. A client that connects and sends nothing blocks
     everyone (the Slowloris attack). That's why gunicorn's docs say to
     put it behind nginx.
  2. Pre-fork workers, gunicorn's model.
  3. An event loop, nginx's model.
- **No TLS.** Writing it by hand is too much; use a library, or leave
  it out.
