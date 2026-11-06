#!/bin/sh
# Starts the shop's database again from schema.sql and seed.sql. The REPL
# can't open primary.db while `just run` has it, so stop that first.
set -e
cd "$(dirname "$0")"

rm -f primary.db replica.db
output=$(cat schema.sql seed.sql | ../../tinysql/tinysql primary.db)

# The REPL prints errors to stdout and carries on, exiting 0.
if echo "$output" | grep 'Error:'; then
    rm -f primary.db
    exit 1
fi
echo "Loaded primary.db"
