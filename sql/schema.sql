CREATE TABLE customers (
    customer_id INTEGER,
    name TEXT,
    email TEXT
);

CREATE TABLE orders (
    order_id INTEGER,
    customer_id INTEGER,
    order_date TEXT,
    amount REAL,
    status TEXT
);
