-- Database Schema for Odoo Subscription Management System

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT CHECK(role IN ('admin', 'staff', 'customer')) NOT NULL DEFAULT 'customer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    address TEXT,
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL,
    cost_price REAL DEFAULT 0.0,
    product_type TEXT DEFAULT 'service'
);

CREATE TABLE IF NOT EXISTS product_variants (
    variant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    variant_name TEXT NOT NULL,
    price_extra REAL DEFAULT 0.0,
    FOREIGN KEY(product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plans (
    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    plan_name TEXT NOT NULL,
    billing_cycle TEXT CHECK(billing_cycle IN ('daily', 'weekly', 'monthly', 'yearly')) NOT NULL,
    duration INTEGER DEFAULT 1,
    price REAL NOT NULL,
    min_quantity INTEGER DEFAULT 1,
    auto_close BOOLEAN DEFAULT 0,
    start_date DATE,
    end_date DATE,
    FOREIGN KEY(product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS discounts (
    discount_id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    discount_type TEXT CHECK(discount_type IN ('fixed', 'percentage')) NOT NULL,
    value REAL NOT NULL,
    min_purchase REAL DEFAULT 0.0,
    min_quantity INTEGER DEFAULT 1,
    start_date DATE,
    end_date DATE,
    usage_limit INTEGER DEFAULT -1,
    used_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    status TEXT CHECK(status IN ('Draft', 'Quotation', 'Confirmed', 'Active', 'Paused', 'Closed')) DEFAULT 'Draft',
    start_date DATE NOT NULL,
    end_date DATE,
    next_billing_date DATE NOT NULL,
    payment_terms TEXT DEFAULT 'Immediate',
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY(plan_id) REFERENCES plans(plan_id)
);

CREATE TABLE IF NOT EXISTS subscription_lines (
    line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER DEFAULT 1,
    unit_price REAL NOT NULL,
    tax_rate REAL DEFAULT 0.0,
    subtotal REAL NOT NULL,
    FOREIGN KEY(subscription_id) REFERENCES subscriptions(subscription_id) ON DELETE CASCADE,
    FOREIGN KEY(product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,
    subtotal REAL NOT NULL,
    tax REAL NOT NULL,
    total REAL NOT NULL,
    status TEXT CHECK(status IN ('Draft', 'Confirmed', 'Paid', 'Cancelled')) DEFAULT 'Draft',
    FOREIGN KEY(subscription_id) REFERENCES subscriptions(subscription_id),
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS invoice_lines (
    line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    description TEXT,
    quantity INTEGER DEFAULT 1,
    unit_price REAL NOT NULL,
    amount REAL NOT NULL,
    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id) ON DELETE CASCADE,
    FOREIGN KEY(product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    payment_date DATE NOT NULL,
    amount REAL NOT NULL,
    payment_method TEXT CHECK(payment_method IN ('Bank Transfer', 'Credit Card', 'Cash', 'PayPal')) NOT NULL,
    notes TEXT,
    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
);
