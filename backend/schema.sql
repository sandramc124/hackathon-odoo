CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100),
    phone VARCHAR(20),
    address TEXT
);

CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    description TEXT,
    base_price DECIMAL(10,2)
);

CREATE TABLE plans (
    plan_id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(product_id),
    billing_cycle VARCHAR(20),
    duration INT,
    price DECIMAL(10,2)
);

CREATE TABLE subscriptions (
    subscription_id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(customer_id),
    plan_id INT REFERENCES plans(plan_id),
    start_date DATE,
    end_date DATE,
    next_billing_date DATE,
    status VARCHAR(20)
);

CREATE TABLE invoices (
    invoice_id SERIAL PRIMARY KEY,
    subscription_id INT REFERENCES subscriptions(subscription_id),
    customer_id INT REFERENCES customers(customer_id),
    invoice_date DATE,
    due_date DATE,
    subtotal DECIMAL(10,2),
    tax DECIMAL(10,2),
    total DECIMAL(10,2),
    status VARCHAR(20)
);

CREATE TABLE payments (
    payment_id SERIAL PRIMARY KEY,
    invoice_id INT REFERENCES invoices(invoice_id),
    payment_date DATE,
    amount DECIMAL(10,2),
    payment_method VARCHAR(30)
);