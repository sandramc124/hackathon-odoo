"""Member 4 - Billing, Payments & Dashboard (branch: feature-billing)

Invoice maths: subtotal = sum(lines) - discount, tax = subtotal * TAX_RATE, total = subtotal + tax.
A discount is stored as a negative invoice line. Tax rate and due days come from .env.

Endpoints
  POST /invoices/generate/<subscription_id>   staff   bill the current cycle of an active subscription
  POST /invoices/generate-due                 staff   bill every active subscription whose next_billing_date has arrived
  POST /invoices/update-overdue               staff   unpaid invoices past due_date -> overdue
  GET  /invoices                              (?status= &customer_id=)  customers only see their own
  GET  /invoices/<id>                         with lines, payments, amount_paid, balance
  POST /payments                              staff   {invoice_id, amount, payment_method}
  GET  /payments                              staff   (?invoice_id=)
  GET  /dashboard/summary                     staff   headline numbers
  GET  /dashboard/revenue                     staff   monthly revenue (?months=12)
  GET  /reports/revenue-by-product            staff
  GET  /reports/outstanding                   staff   unpaid / overdue invoices with balances

Other modules import: generate_invoice(subscription_id)
"""
import os
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request, session

from auth import current_customer_id, login_required, roles_required
from database import (ApiError, add_cycle, json_body, query_all, query_one,
                      require_fields, transaction)

billing_bp = Blueprint("billing", __name__)

STAFF = ("admin", "staff")
TAX_RATE = Decimal(os.getenv("TAX_RATE", "0.18"))
INVOICE_DUE_DAYS = int(os.getenv("INVOICE_DUE_DAYS", "15"))
PAYMENT_METHODS = ("cash", "card", "upi", "bank_transfer")
CENT = Decimal("0.01")


# ====================== Invoice generation ======================
def generate_invoice(subscription_id):
    """Creates an invoice for the subscription's current cycle, then advances
    next_billing_date by one cycle. Returns the full invoice detail dict."""
    with transaction() as cur:
        cur.execute(
            "SELECT s.*, p.billing_cycle FROM subscriptions s "
            "JOIN plans p ON p.plan_id = s.plan_id "
            "WHERE s.subscription_id = %s FOR UPDATE OF s", (subscription_id,))
        sub = cur.fetchone()
        if not sub:
            raise ApiError("Subscription not found", 404)
        if sub["status"] != "active":
            raise ApiError("Invoices can only be generated for active subscriptions "
                           f"(current status: {sub['status']})", 409)

        cur.execute(
            "SELECT sl.quantity, sl.unit_price, pr.product_name, v.value AS variant_value "
            "FROM subscription_lines sl "
            "JOIN products pr ON pr.product_id = sl.product_id "
            "LEFT JOIN product_variants v ON v.variant_id = sl.variant_id "
            "WHERE sl.subscription_id = %s ORDER BY sl.line_id", (subscription_id,))
        rows = cur.fetchall()
        if not rows:
            raise ApiError("Subscription has no lines to bill", 409)

        lines, subtotal = [], Decimal("0")
        for r in rows:
            desc = f"{r['product_name']} ({sub['billing_cycle']})"
            if r["variant_value"]:
                desc += f" - {r['variant_value']}"
            amount = r["quantity"] * r["unit_price"]
            lines.append((desc, r["quantity"], r["unit_price"], amount))
            subtotal += amount

        if sub["discount_id"]:
            cur.execute("SELECT * FROM discounts WHERE discount_id = %s AND is_active",
                        (sub["discount_id"],))
            disc = cur.fetchone()
            if disc:
                off = (subtotal * disc["value"] / 100 if disc["type"] == "percent"
                       else min(disc["value"], subtotal)).quantize(CENT)
                lines.append((f"Discount {disc['code']}", 1, -off, -off))
                subtotal -= off

        tax = (subtotal * TAX_RATE).quantize(CENT)
        total = subtotal + tax
        today = date.today()

        cur.execute(
            "INSERT INTO invoices (subscription_id, customer_id, invoice_date, due_date, "
            "subtotal, tax, total, status) VALUES (%s, %s, %s, %s, %s, %s, %s, 'unpaid') "
            "RETURNING invoice_id",
            (subscription_id, sub["customer_id"], today,
             today + timedelta(days=INVOICE_DUE_DAYS), subtotal, tax, total))
        invoice_id = cur.fetchone()["invoice_id"]

        for desc, qty, unit_price, amount in lines:
            cur.execute("INSERT INTO invoice_lines (invoice_id, description, quantity, "
                        "unit_price, amount) VALUES (%s, %s, %s, %s, %s)",
                        (invoice_id, desc, qty, unit_price, amount))

        next_date = add_cycle(sub["next_billing_date"] or today, sub["billing_cycle"], 1)
        cur.execute("UPDATE subscriptions SET next_billing_date = %s WHERE subscription_id = %s",
                    (next_date, subscription_id))

    return _invoice_detail(invoice_id)


def _invoice_detail(invoice_id):
    inv = query_one(
        "SELECT i.*, c.name AS customer_name, "
        "COALESCE((SELECT SUM(amount) FROM payments WHERE invoice_id = i.invoice_id), 0) "
        "AS amount_paid "
        "FROM invoices i JOIN customers c ON c.customer_id = i.customer_id "
        "WHERE i.invoice_id = %s", (invoice_id,))
    if not inv:
        raise ApiError("Invoice not found", 404)
    inv["balance"] = inv["total"] - inv["amount_paid"]
    inv["lines"] = query_all("SELECT * FROM invoice_lines WHERE invoice_id = %s "
                             "ORDER BY line_id", (invoice_id,))
    inv["payments"] = query_all("SELECT * FROM payments WHERE invoice_id = %s "
                                "ORDER BY payment_id", (invoice_id,))
    return inv


@billing_bp.post("/invoices/generate/<int:subscription_id>")
@roles_required(*STAFF)
def generate_invoice_route(subscription_id):
    return jsonify(generate_invoice(subscription_id)), 201


@billing_bp.post("/invoices/generate-due")
@roles_required(*STAFF)
def generate_due_invoices():
    due = query_all(
        "SELECT subscription_id FROM subscriptions WHERE status = 'active' "
        "AND next_billing_date <= CURRENT_DATE "
        "AND (end_date IS NULL OR next_billing_date <= end_date)")
    created, failed = [], []
    for row in due:
        try:
            created.append(generate_invoice(row["subscription_id"])["invoice_id"])
        except ApiError as e:
            failed.append({"subscription_id": row["subscription_id"], "error": e.message})
    return jsonify({"invoices_created": created, "failed": failed})


@billing_bp.post("/invoices/update-overdue")
@roles_required(*STAFF)
def update_overdue():
    rows = query_all("UPDATE invoices SET status = 'overdue' "
                     "WHERE status = 'unpaid' AND due_date < CURRENT_DATE RETURNING invoice_id")
    return jsonify({"marked_overdue": [r["invoice_id"] for r in rows]})


# ====================== Invoice queries ======================
@billing_bp.get("/invoices")
@login_required
def list_invoices():
    sql = ("SELECT i.*, c.name AS customer_name FROM invoices i "
           "JOIN customers c ON c.customer_id = i.customer_id WHERE 1 = 1")
    params = []
    if session["role"] == "customer":
        cid = current_customer_id()
        if not cid:
            return jsonify([])
        sql += " AND i.customer_id = %s"
        params.append(cid)
    elif request.args.get("customer_id"):
        sql += " AND i.customer_id = %s"
        params.append(request.args["customer_id"])
    if request.args.get("status"):
        sql += " AND i.status = %s"
        params.append(request.args["status"])
    return jsonify(query_all(sql + " ORDER BY i.invoice_id DESC", params))


@billing_bp.get("/invoices/<int:invoice_id>")
@login_required
def get_invoice(invoice_id):
    inv = _invoice_detail(invoice_id)
    if session["role"] == "customer" and inv["customer_id"] != current_customer_id():
        raise ApiError("You can only view your own invoices", 403)
    return jsonify(inv)


# ====================== Payments ======================
@billing_bp.post("/payments")
@roles_required(*STAFF)
def record_payment():
    d = json_body()
    require_fields(d, "invoice_id", "amount", "payment_method")
    if d["payment_method"] not in PAYMENT_METHODS:
        raise ApiError(f"payment_method must be one of: {', '.join(PAYMENT_METHODS)}")
    try:
        amount = Decimal(str(d["amount"])).quantize(CENT)
    except InvalidOperation:
        raise ApiError("amount must be a number")
    if amount <= 0:
        raise ApiError("amount must be greater than zero")

    with transaction() as cur:
        cur.execute("SELECT invoice_id, total, status FROM invoices "
                    "WHERE invoice_id = %s FOR UPDATE", (d["invoice_id"],))
        inv = cur.fetchone()
        if not inv:
            raise ApiError("Invoice not found", 404)
        if inv["status"] == "paid":
            raise ApiError("Invoice is already fully paid", 409)

        cur.execute("SELECT COALESCE(SUM(amount), 0) AS paid FROM payments WHERE invoice_id = %s",
                    (inv["invoice_id"],))
        paid = cur.fetchone()["paid"]
        balance = inv["total"] - paid
        if amount > balance:
            raise ApiError(f"Amount exceeds the outstanding balance ({balance})", 400)

        cur.execute("INSERT INTO payments (invoice_id, amount, payment_method) "
                    "VALUES (%s, %s, %s) RETURNING *",
                    (inv["invoice_id"], amount, d["payment_method"]))
        payment = cur.fetchone()
        if paid + amount >= inv["total"]:
            cur.execute("UPDATE invoices SET status = 'paid' WHERE invoice_id = %s",
                        (inv["invoice_id"],))
    return jsonify({"payment": payment, "invoice_fully_paid": paid + amount >= inv["total"]}), 201


@billing_bp.get("/payments")
@roles_required(*STAFF)
def list_payments():
    sql, params = "SELECT * FROM payments WHERE 1 = 1", []
    if request.args.get("invoice_id"):
        sql += " AND invoice_id = %s"
        params.append(request.args["invoice_id"])
    return jsonify(query_all(sql + " ORDER BY payment_id DESC", params))


# ====================== Dashboard & reports ======================
@billing_bp.get("/dashboard/summary")
@roles_required(*STAFF)
def dashboard_summary():
    revenue = query_one("SELECT COALESCE(SUM(amount), 0) AS v FROM payments")["v"]
    outstanding = query_one(
        "SELECT COALESCE(SUM(i.total - COALESCE(p.paid, 0)), 0) AS v FROM invoices i "
        "LEFT JOIN (SELECT invoice_id, SUM(amount) AS paid FROM payments GROUP BY invoice_id) p "
        "ON p.invoice_id = i.invoice_id WHERE i.status IN ('unpaid', 'overdue')")["v"]
    by_status = query_all("SELECT status, COUNT(*) AS count FROM subscriptions GROUP BY status")
    return jsonify({
        "total_revenue": revenue,
        "outstanding_amount": outstanding,
        "total_customers": query_one("SELECT COUNT(*) AS v FROM customers")["v"],
        "active_subscriptions": query_one(
            "SELECT COUNT(*) AS v FROM subscriptions WHERE status = 'active'")["v"],
        "overdue_invoices": query_one(
            "SELECT COUNT(*) AS v FROM invoices WHERE status = 'overdue'")["v"],
        "subscriptions_by_status": {r["status"]: r["count"] for r in by_status},
    })


@billing_bp.get("/dashboard/revenue")
@roles_required(*STAFF)
def dashboard_revenue():
    try:
        months = max(1, min(int(request.args.get("months", 12)), 60))
    except ValueError:
        raise ApiError("months must be a whole number")
    rows = query_all(
        "SELECT to_char(date_trunc('month', payment_date), 'YYYY-MM') AS month, "
        "SUM(amount) AS revenue, COUNT(*) AS payments FROM payments "
        "WHERE payment_date >= date_trunc('month', CURRENT_DATE) - make_interval(months => %s) "
        "GROUP BY 1 ORDER BY 1", (months - 1,))
    return jsonify(rows)


@billing_bp.get("/reports/revenue-by-product")
@roles_required(*STAFF)
def revenue_by_product():
    return jsonify(query_all(
        "SELECT pr.product_id, pr.product_name, SUM(pay.amount) AS revenue "
        "FROM payments pay "
        "JOIN invoices i ON i.invoice_id = pay.invoice_id "
        "JOIN subscriptions s ON s.subscription_id = i.subscription_id "
        "JOIN plans pl ON pl.plan_id = s.plan_id "
        "JOIN products pr ON pr.product_id = pl.product_id "
        "GROUP BY pr.product_id, pr.product_name ORDER BY revenue DESC"))


@billing_bp.get("/reports/outstanding")
@roles_required(*STAFF)
def outstanding_report():
    return jsonify(query_all(
        "SELECT i.invoice_id, i.customer_id, c.name AS customer_name, i.due_date, i.status, "
        "i.total, COALESCE(p.paid, 0) AS amount_paid, i.total - COALESCE(p.paid, 0) AS balance "
        "FROM invoices i JOIN customers c ON c.customer_id = i.customer_id "
        "LEFT JOIN (SELECT invoice_id, SUM(amount) AS paid FROM payments GROUP BY invoice_id) p "
        "ON p.invoice_id = i.invoice_id "
        "WHERE i.status IN ('unpaid', 'overdue') ORDER BY i.due_date"))
