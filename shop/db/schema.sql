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
