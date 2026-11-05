#!/bin/sh
# Starts the primary on 5480 and its read replica on 5481. The replica
# copies the primary's snapshot into replica.db when it connects.
set -e
cd "$(dirname "$0")"

server=../../tinysql/tinysql-server

$server primary.db --port 5480 &
primary=$!
$server replica.db --port 5481 --replica-of 5480 &
replica=$!

trap 'kill $primary $replica 2>/dev/null' INT TERM EXIT
wait
