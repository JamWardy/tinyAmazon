-- Every user's password is "password". alice (1) and bob (2) sell; carol
-- (3) buys.
BEGIN;

INSERT INTO users (email, password_hash) VALUES ('alice@example.com', '6a5b978cfcf27d46bef9e74fda108984:1283574d8ebf473c56ea5a44f5841d775c8a0022079884c4882c26638ee2fa13');
INSERT INTO users (email, password_hash) VALUES ('bob@example.com', 'ef1103bd5401a3c3f87b5931b6851023:5eb38926fd10eeb043872b7f261ac7eb19ab1eb3893cdd3409b98955fe203f07');
INSERT INTO users (email, password_hash) VALUES ('carol@example.com', 'd0d536acbff2e814d5ee974a60534bf9:67cb374ca1c42122f727287b9a4eaebe321362cf2f683f22d6e12b4e914069de');

INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Walnut desk lamp', 'Brass switch, warm white bulb included.', 3499, 12);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Oak bookshelf', 'Five shelves, 180 cm tall.', 12900, 3);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Linen cushion cover', '45 x 45 cm, sage green.', 1500, 40);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Wool throw blanket', NULL, 4200, 0);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Ceramic mug', '350 ml, dishwasher safe.', 899, 60);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Ceramic teapot', 'Holds four cups.', 2450, 7);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Cast iron skillet', '26 cm, pre-seasoned.', 3200, 15);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Chef''s knife', '20 cm blade.', 5900, 0);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Bamboo chopping board', NULL, 1800, 25);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Glass storage jars (set of 3)', 'Airtight lids.', 1999, 18);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Desk organiser', 'Three trays and a pen pot.', 1450, 9);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Wall clock', 'Silent sweep movement.', 2700, 5);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Scented candle', 'Fig and cedar, 40 hours.', 1600, 30);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Doormat', NULL, 1200, 0);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (1, 'Picture frame A4', 'Black ash.', 1100, 22);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, 'Running shoes', 'Neutral cushioning, UK sizes 6-12.', 8500, 10);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, 'Trail running shoes', NULL, 9500, 4);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, 'Cotton T-shirt', 'Organic cotton, crew neck.', 1400, 100);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, 'Rain jacket', 'Packs into its own pocket.', 6500, 8);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, 'Wool socks (3 pairs)', 'Merino blend.', 1800, 0);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, 'Leather wallet', 'Six card slots.', 3500, 14);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, 'Canvas backpack', '20 litres, laptop sleeve.', 4800, 6);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, 'Sunglasses', 'UV400 lenses.', 2900, 11);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, 'Baseball cap', NULL, 1500, 20);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, 'Yoga mat', '6 mm thick.', 2500, 13);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, 'Water bottle', '750 ml, keeps cold for 24 hours.', 2200, 35);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, 'Gift card - 50% off sale', 'Half price on any one item.', 500, 50);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, '100% cotton hoodie', 'Brushed fleece inside.', 3900, 9);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, 'snake_case stickers', 'A sheet of 20 stickers for programmers.', 300, 200);
INSERT INTO items (seller_id, title, description, price, stock) VALUES (2, 'Bike lights', 'Front and rear, USB charging.', 2400, 0);

COMMIT;
