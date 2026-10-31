# Odoo Hackathon 2026
# Subscription Management System

## Team Members

| Member | Module | Branch |
|---------|--------|--------|
| Member 1 | Authentication & Customer Management | feature-auth |
| Member 2 | Products & Subscription Plans | feature-products |
| Member 3 | Subscription Management | feature-subscription |
| Member 4 | Billing, Payments & Dashboard | feature-billing |

---

# Project Objective

Develop a Subscription Management System that enables businesses to:

- Manage customers
- Manage products and subscription plans
- Create and manage subscriptions
- Generate invoices
- Record payments
- Display business analytics through dashboards

---

# Project Structure

```
hackathon-odoo/

backend/
│
├── app.py
├── database.py
├── schema.sql
├── auth.py
├── products.py
├── subscription.py
├── billing.py
│
frontend/

README.md
```

---

# Database Tables

- users
- customers
- products
- product_variants
- plans
- discounts
- subscriptions
- subscription_lines
- invoices
- invoice_lines
- payments

Do NOT rename tables or columns without informing the entire team.

---

# Standard Variable Names

## Customer

```
customer_id
name
email
phone
address
```

## Product

```
product_id
product_name
description
price
```

## Plan

```
plan_id
product_id
billing_cycle
duration
price
```

## Subscription

```
subscription_id
customer_id
plan_id
status
start_date
end_date
next_billing_date
```

## Invoice

```
invoice_id
subscription_id
customer_id
invoice_date
due_date
subtotal
tax
total
status
```

## Payment

```
payment_id
invoice_id
payment_date
amount
payment_method
```

Use these exact names throughout the project.

---

# Team Responsibilities

## Member 1 - Authentication & Customer Management

Files:

```
backend/auth.py
```

Responsibilities:

- Register
- Login
- Logout
- User Roles
- Customer CRUD

Database Tables:

- users
- customers

---

## Member 2 - Products & Plans

Files:

```
backend/products.py
```

Responsibilities:

- Products
- Product Variants
- Subscription Plans
- Discounts

Database Tables:

- products
- product_variants
- plans
- discounts

---

## Member 3 - Subscription Module

Files:

```
backend/subscription.py
```

Responsibilities:

- Quotations
- Subscription Creation
- Pause Subscription
- Resume Subscription
- Renew Subscription
- Cancel Subscription

Database Tables:

- subscriptions
- subscription_lines

---

## Member 4 - Billing Module

Files:

```
backend/billing.py
```

Responsibilities:

- Invoice Generation
- Payments
- Revenue Dashboard
- Reports

Database Tables:

- invoices
- invoice_lines
- payments

---

# Git Workflow

Clone Repository

```
git clone <repository-url>
```

Create Branch

```
git checkout -b feature-auth
```

or

```
feature-products
feature-subscription
feature-billing
```

Check Current Branch

```
git branch
```

Save Changes

```
git add .
git commit -m "Meaningful commit message"
```

Push Changes

```
git push origin feature-name
```

Never push directly to **main**.

---

# Daily Workflow

1. Pull latest changes

```
git checkout main
git pull origin main
```

2. Switch back to your branch

```
git checkout feature-name
```

3. Merge latest main

```
git merge main
```

4. Continue coding.

---

# Integration Process

Every few hours:

- Push your latest code.
- Create a Pull Request.
- Team leader reviews the changes.
- Merge into main after testing.
- Everyone pulls the updated main branch.

---

# Development Rules

- Do not edit another member's files.
- Do not change database schema without team approval.
- Do not rename variables.
- Commit frequently.
- Test before pushing.
- Resolve merge conflicts before creating a Pull Request.

---

# Development Order

Phase 1

- Database
- Authentication
- Products
- Subscription
- Billing

Phase 2

- API Integration
- Frontend Integration

Phase 3

- Dashboard
- Reports
- Testing

---

# Final Workflow

Customer Registration

↓

Product Selection

↓

Choose Subscription Plan

↓

Create Subscription

↓

Generate Invoice

↓

Record Payment

↓

Update Dashboard

---

# Tech Stack

Backend:
- Python

Database:
- PostgreSQL

Version Control:
- Git & GitHub

IDE:
- Visual Studio Code

---

# Goal

Deliver a complete, scalable, and user-friendly Subscription Management System that satisfies all hackathon requirements and demonstrates clean architecture, teamwork, and reliable functionality.