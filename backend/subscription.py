"""Member 3 - Subscription Module (branch: feature-subscription)

Status flow:  quotation -> active <-> paused -> cancelled | expired -> (renew) -> active

Endpoints
  POST /quotations                     create a quotation (customers: for themselves; staff: give customer_id)
  POST /quotations/<id>/confirm        quotation -> active, sets dates, generates first invoice
  POST /subscriptions                  staff shortcut: create + activate in one call
  GET  /subscriptions                  (?status= &customer_id=)  customers only see their own
  GET  /subscriptions/<id>
  POST /subscriptions/<id>/pause       active  -> paused
  POST /subscriptions/<id>/resume      paused  -> active
  POST /subscriptions/<id>/renew       active/expired -> active, extends end_date, bills now
  POST /subscriptions/<id>/cancel
  POST /subscriptions/expire-check     marks active subscriptions past end_date as expired

Create body: {customer_id, plan_id, quantity?, variant_id?, discount_code?}
"""
from datetime import date

from flask import Blueprint, jsonify, request, session

from auth import current_customer_id, login_required, roles_required
from database import (ApiError, add_cycle, execute, json_body, query_all,
                      query_one, require_fields, transaction)

subscription_bp = Blueprint("subscription", __name__)

STAFF = ("admin", "staff")

_LIST_SQL = """
    SELECT s.*, c.name AS customer_name, pr.product_name, p.billing_cycle, p.price AS plan_price
    FROM subscriptions s
    JOIN customers c  ON c.customer_id = s.customer_id
    JOIN plans p      ON p.plan_id = s.plan_id
    JOIN products pr  ON pr.product_id = p.product_id
"""


# ---------- helpers ----------
def _get_sub_or_404(subscription_id):
    row = query_one(_LIST_SQL + " WHERE s.subscription_id = %s", (subscription_id,))
    if not row:
        raise ApiError("Subscription not found", 404)
    return row


def _check_access(sub):
    if session.get("role") == "customer" and sub["customer_id"] != current_customer_id():
        raise ApiError("You can only access your own subscriptions", 403)


def _detail(subscription_id):
    sub = _get_sub_or_404(subscription_id)
    sub["lines"] = query_all(
        "SELECT sl.*, pr.product_name, v.attribute, v.value AS variant_value "
        "FROM subscription_lines sl "
        "JOIN products pr ON pr.product_id = sl.product_id "
        "LEFT JOIN product_variants v ON v.variant_id = sl.variant_id "
        "WHERE sl.subscription_id = %s ORDER BY sl.line_id", (subscription_id,))
    return sub


def _create(customer_id, plan_id, quantity=1, variant_id=None, discount_code=None):
    """Inserts a subscription with status 'quotation' plus its line. Returns subscription_id."""
    if not query_one("SELECT 1 AS x FROM customers WHERE customer_id = %s", (customer_id,)):
        raise ApiError("Customer not found", 404)
    plan = query_one("SELECT * FROM plans WHERE plan_id = %s AND is_active", (plan_id,))
    if not plan:
        raise ApiError("Plan not found or inactive", 404)

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ApiError("quantity must be a whole number")
    if quantity < 1:
        raise ApiError("quantity must be at least 1")

    unit_price = plan["price"]
    if variant_id:
        variant = query_one("SELECT extra_price FROM product_variants "
                            "WHERE variant_id = %s AND product_id = %s",
                            (variant_id, plan["product_id"]))
        if not variant:
            raise ApiError("Variant does not belong to this plan's product", 400)
        unit_price += variant["extra_price"]

    discount_id = None
    if discount_code:
        disc = query_one(
            "SELECT discount_id FROM discounts WHERE code = %s AND is_active "
            "AND (valid_from IS NULL OR valid_from <= CURRENT_DATE) "
            "AND (valid_until IS NULL OR valid_until >= CURRENT_DATE)",
            (discount_code.strip().upper(),))
        if not disc:
            raise ApiError("Invalid or expired discount code", 400)
        discount_id = disc["discount_id"]

    with transaction() as cur:
        cur.execute("INSERT INTO subscriptions (customer_id, plan_id, discount_id, status) "
                    "VALUES (%s, %s, %s, 'quotation') RETURNING subscription_id",
                    (customer_id, plan_id, discount_id))
        sid = cur.fetchone()["subscription_id"]
        cur.execute("INSERT INTO subscription_lines "
                    "(subscription_id, product_id, variant_id, quantity, unit_price) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (sid, plan["product_id"], variant_id or None, quantity, unit_price))
    return sid


def _activate(subscription_id):
    """quotation -> active and bill the first cycle. Returns the first invoice."""
    from billing import generate_invoice  # Member 4's function (lazy import avoids a cycle)

    sub = _get_sub_or_404(subscription_id)
    if sub["status"] != "quotation":
        raise ApiError(f"Only quotations can be confirmed (current status: {sub['status']})", 409)
    plan = query_one("SELECT billing_cycle, duration FROM plans WHERE plan_id = %s",
                     (sub["plan_id"],))
    start = date.today()
    end = add_cycle(start, plan["billing_cycle"], plan["duration"])
    execute("UPDATE subscriptions SET status = 'active', start_date = %s, end_date = %s, "
            "next_billing_date = %s WHERE subscription_id = %s",
            (start, end, start, subscription_id))
    return generate_invoice(subscription_id)


def _transition(subscription_id, allowed_from, set_sql):
    """Status change guarded by the current status. `set_sql` is a code constant."""
    sub = _get_sub_or_404(subscription_id)
    if sub["status"] not in allowed_from:
        raise ApiError(f"Cannot do this while status is '{sub['status']}' "
                       f"(allowed from: {', '.join(allowed_from)})", 409)
    execute(f"UPDATE subscriptions SET {set_sql} WHERE subscription_id = %s", (subscription_id,))
    return _detail(subscription_id)


# ---------- quotations ----------
@subscription_bp.post("/quotations")
@login_required
def create_quotation():
    d = json_body()
    require_fields(d, "plan_id")
    if session["role"] == "customer":
        customer_id = current_customer_id()
        if not customer_id:
            raise ApiError("No customer profile is linked to this account")
    else:
        require_fields(d, "customer_id")
        customer_id = d["customer_id"]
    sid = _create(customer_id, d["plan_id"], d.get("quantity", 1),
                  d.get("variant_id"), d.get("discount_code"))
    return jsonify(_detail(sid)), 201


@subscription_bp.post("/quotations/<int:subscription_id>/confirm")
@login_required
def confirm_quotation(subscription_id):
    _check_access(_get_sub_or_404(subscription_id))
    invoice = _activate(subscription_id)
    return jsonify({"subscription": _detail(subscription_id), "invoice": invoice})


# ---------- subscriptions ----------
@subscription_bp.post("/subscriptions")
@roles_required(*STAFF)
def create_subscription():
    d = json_body()
    require_fields(d, "customer_id", "plan_id")
    sid = _create(d["customer_id"], d["plan_id"], d.get("quantity", 1),
                  d.get("variant_id"), d.get("discount_code"))
    invoice = _activate(sid)
    return jsonify({"subscription": _detail(sid), "invoice": invoice}), 201


@subscription_bp.get("/subscriptions")
@login_required
def list_subscriptions():
    sql, params = _LIST_SQL + " WHERE 1 = 1", []
    if session["role"] == "customer":
        cid = current_customer_id()
        if not cid:
            return jsonify([])
        sql += " AND s.customer_id = %s"
        params.append(cid)
    elif request.args.get("customer_id"):
        sql += " AND s.customer_id = %s"
        params.append(request.args["customer_id"])
    if request.args.get("status"):
        sql += " AND s.status = %s"
        params.append(request.args["status"])
    return jsonify(query_all(sql + " ORDER BY s.subscription_id DESC", params))


@subscription_bp.get("/subscriptions/<int:subscription_id>")
@login_required
def get_subscription(subscription_id):
    sub = _detail(subscription_id)
    _check_access(sub)
    return jsonify(sub)


@subscription_bp.post("/subscriptions/<int:subscription_id>/pause")
@roles_required(*STAFF)
def pause_subscription(subscription_id):
    return jsonify(_transition(subscription_id, ("active",), "status = 'paused'"))


@subscription_bp.post("/subscriptions/<int:subscription_id>/resume")
@roles_required(*STAFF)
def resume_subscription(subscription_id):
    # no billing for the paused period: next billing can't be in the past
    return jsonify(_transition(
        subscription_id, ("paused",),
        "status = 'active', next_billing_date = GREATEST(next_billing_date, CURRENT_DATE)"))


@subscription_bp.post("/subscriptions/<int:subscription_id>/cancel")
@roles_required(*STAFF)
def cancel_subscription(subscription_id):
    return jsonify(_transition(
        subscription_id, ("quotation", "active", "paused"),
        "status = 'cancelled', end_date = CURRENT_DATE, next_billing_date = NULL"))


@subscription_bp.post("/subscriptions/<int:subscription_id>/renew")
@roles_required(*STAFF)
def renew_subscription(subscription_id):
    from billing import generate_invoice

    sub = _get_sub_or_404(subscription_id)
    if sub["status"] not in ("active", "expired"):
        raise ApiError(f"Only active or expired subscriptions can be renewed "
                       f"(current status: {sub['status']})", 409)
    plan = query_one("SELECT billing_cycle, duration FROM plans WHERE plan_id = %s",
                     (sub["plan_id"],))
    today = date.today()
    base = max(sub["end_date"] or today, today)
    new_end = add_cycle(base, plan["billing_cycle"], plan["duration"])
    execute("UPDATE subscriptions SET status = 'active', end_date = %s, "
            "next_billing_date = GREATEST(COALESCE(next_billing_date, CURRENT_DATE), CURRENT_DATE) "
            "WHERE subscription_id = %s", (new_end, subscription_id))
    invoice = generate_invoice(subscription_id)
    return jsonify({"subscription": _detail(subscription_id), "invoice": invoice})


@subscription_bp.post("/subscriptions/expire-check")
@roles_required(*STAFF)
def expire_check():
    rows = query_all(
        "UPDATE subscriptions SET status = 'expired', next_billing_date = NULL "
        "WHERE status = 'active' AND end_date < CURRENT_DATE RETURNING subscription_id")
    return jsonify({"expired": [r["subscription_id"] for r in rows]})
