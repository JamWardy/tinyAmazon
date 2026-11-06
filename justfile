# The database's primary (5480) and read replica (5481), then the auth,
# items, search and order services (8001 to 8004) and tinypay (9001), each
# its own process, on 127.0.0.1 only.

# Start the whole shop; Ctrl-C stops it all
run:
    #!/bin/sh
    set -e
    : "${SHOP_JWT_SECRET:?set it to a long random string, the secret tokens are signed with}"
    : "${TINYPAY_SECRET:?set it to a long random string, the API key for tinypay}"
    trap 'kill $pids 2>/dev/null' INT TERM EXIT

    # Waits until port accepts connections, or gives up if pid has died.
    wait_for() {
        until nc -z 127.0.0.1 "$1" 2>/dev/null; do
            kill -0 "$2" 2>/dev/null || { echo "run: nothing on port $1" >&2; exit 1; }
            sleep 0.1
        done
    }

    # The replica copies the primary's snapshot into replica.db as it
    # connects, and each service connects to the database as it starts.
    tinysql/tinysql-server shop/db/primary.db --port 5480 &
    pids="$!"
    wait_for 5480 $!
    tinysql/tinysql-server shop/db/replica.db --port 5481 --replica-of 5480 &
    pids="$pids $!"
    wait_for 5481 $!

    # python -m tinyhttp finds shop/ and tinyhttp/ from here. Idle
    # connections are kept longer than tinyproxy keeps them, so it's always
    # tinyproxy that closes one, never a request racing tinyhttp's close.
    start() {
        python3 -m tinyhttp --host 127.0.0.1 --port "$1" --keep-alive 75 "shop.$2:app" &
        pids="$pids $!"
    }
    start 8001 auth
    start 8002 items
    start 8003 search
    start 8004 orders
    start 9001 tinypay
    wait
