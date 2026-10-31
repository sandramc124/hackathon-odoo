-- Sample data. Run AFTER schema.sql:  psql -d subscription_db -f seed.sql
-- Users are created through POST /auth/register (the first user becomes admin).

INSERT INTO customers (name, email, phone, address) VALUES
  ('Aarav Sharma', 'aarav@example.com', '9876543210', 'Kochi, Kerala'),
  ('Meera Nair',   'meera@example.com', '9876501234', 'Kottayam, Kerala');

INSERT INTO products (product_name, description, price) VALUES
  ('CRM Suite',      'Customer relationship management', 1000.00),
  ('Accounting Pro', 'Invoicing and bookkeeping',        1500.00);

INSERT INTO product_variants (product_id, attribute, value, extra_price) VALUES
  (1, 'Users',   '5 users',  0),
  (1, 'Users',   '25 users', 500.00),
  (2, 'Edition', 'Premium',  300.00);

INSERT INTO plans (product_id, billing_cycle, duration, price) VALUES
  (1, 'monthly', 12, 1000.00),
  (1, 'yearly',   1, 10000.00),
  (2, 'monthly',  6, 1500.00);

INSERT INTO discounts (code, type, value, valid_from, valid_until) VALUES
  ('WELCOME10', 'percent', 10,     CURRENT_DATE - 30, CURRENT_DATE + 365),
  ('FLAT200',   'fixed',   200.00, CURRENT_DATE - 30, CURRENT_DATE + 365);

-- One active subscription, due for billing today (lets Member 4 test invoicing immediately)
INSERT INTO subscriptions (customer_id, plan_id, status, start_date, end_date, next_billing_date)
VALUES (1, 1, 'active', CURRENT_DATE, CURRENT_DATE + INTERVAL '12 months', CURRENT_DATE);

INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price)
VALUES (1, 1, 1, 1, 1000.00);
