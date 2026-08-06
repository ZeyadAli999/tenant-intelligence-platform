CREATE SCHEMA business;

CREATE TABLE business.customers (
    id BIGSERIAL PRIMARY KEY,
    customer_code VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(255),
    country VARCHAR(100) NOT NULL,
    tax_identifier VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE business.orders (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES business.customers(id),
    order_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL,
    total_amount NUMERIC(14, 2) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE business.invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id BIGINT NOT NULL REFERENCES business.orders(id),
    invoice_number VARCHAR(50) NOT NULL UNIQUE,
    issued_at TIMESTAMPTZ NOT NULL,
    due_date DATE,
    amount NUMERIC(14, 2) NOT NULL,
    paid BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE VIEW business.customer_order_totals AS
SELECT
    customer.id AS customer_id,
    customer.name,
    COUNT(orders.id) AS order_count,
    COALESCE(SUM(orders.total_amount), 0) AS total_order_value
FROM business.customers AS customer
LEFT JOIN business.orders AS orders ON orders.customer_id = customer.id
GROUP BY customer.id, customer.name;

INSERT INTO business.customers (customer_code, name, email, country, tax_identifier)
VALUES
    ('CUST-001', 'Demo Customer One', 'one@example.test', 'Egypt', 'EG-SECRET-001'),
    ('CUST-002', 'Demo Customer Two', 'two@example.test', 'France', 'FR-SECRET-002'),
    ('CUST-003', 'Demo Customer Three', 'three@example.test', 'Egypt', 'EG-SECRET-003');

INSERT INTO business.orders (customer_id, order_date, status, total_amount, metadata)
SELECT id, DATE '2026-08-01', 'confirmed', 1250.50, '{"channel":"demo"}'::jsonb
FROM business.customers
WHERE customer_code = 'CUST-001';

INSERT INTO business.orders (customer_id, order_date, status, total_amount, metadata)
SELECT id, DATE '2026-08-03', 'pending', 875.25, '{"channel":"demo"}'::jsonb
FROM business.customers
WHERE customer_code = 'CUST-003';

INSERT INTO business.invoices (
    order_id,
    invoice_number,
    issued_at,
    due_date,
    amount,
    paid
)
SELECT id, 'INV-001', TIMESTAMPTZ '2026-08-02 10:00:00+00', DATE '2026-09-01', 1250.50, FALSE
FROM business.orders
LIMIT 1;
