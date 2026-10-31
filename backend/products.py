"""Member 2 - Products & Subscription Plans (branch: feature-products)

Endpoints (read = any logged-in user, write = admin/staff)
  /products                 GET (?all=1 includes inactive) | POST
  /products/<id>            GET (with variants + plans) | PUT | DELETE (soft: is_active=false)
  /products/<id>/variants   GET | POST
  /variants/<id>            PUT | DELETE
  /plans                    GET (?product_id=) | POST
  /plans/<id>               GET | PUT | DELETE (soft)
  /discounts                GET | POST                      (admin/staff)
  /discounts/<id>           PUT | DELETE                    (admin/staff)
  /discounts/validate       POST {code, amount?}            (any logged-in user)
"""
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request

from auth import login_required, roles_required
from database import (ApiError, execute, json_body, query_all, query_one,
                      require_fields, update_fields)

products_bp = Blueprint("products", __name__)

STAFF = ("admin", "staff")
BILLING_CYCLES = ("weekly", "monthly", "quarterly", "yearly")


def _money(value, field):
    try:
        v = Decimal(str(value))
    except InvalidOperation:
        raise ApiError(f"{field} must be a number")
    if v < 0:
        raise ApiError(f"{field} cannot be negative")
    return v


def _clean_money(d, *fields):
    for f in fields:
        if f in d:
            d[f] = _money(d[f], f)


def _product_or_404(product_id):
    row = query_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    if not row:
        raise ApiError("Product not found", 404)
    return row


# ====================== Products ======================
@products_bp.get("/products")
@login_required
def list_products():
    if request.args.get("all"):
        rows = query_all("SELECT * FROM products ORDER BY product_id")
    else:
        rows = query_all("SELECT * FROM products WHERE is_active ORDER BY product_id")
    return jsonify(rows)


@products_bp.post("/products")
@roles_required(*STAFF)
def create_product():
    d = json_body()
    require_fields(d, "product_name", "price")
    _clean_money(d, "price")
    row = execute("INSERT INTO products (product_name, description, price) "
                  "VALUES (%s, %s, %s) RETURNING *",
                  (d["product_name"], d.get("description"), d["price"]))
    return jsonify(row), 201


@products_bp.get("/products/<int:product_id>")
@login_required
def get_product(product_id):
    product = _product_or_404(product_id)
    product["variants"] = query_all(
        "SELECT * FROM product_variants WHERE product_id = %s ORDER BY variant_id", (product_id,))
    product["plans"] = query_all(
        "SELECT * FROM plans WHERE product_id = %s AND is_active ORDER BY plan_id", (product_id,))
    return jsonify(product)


@products_bp.put("/products/<int:product_id>")
@roles_required(*STAFF)
def update_product(product_id):
    d = json_body()
    _clean_money(d, "price")
    return jsonify(update_fields("products", "product_id", product_id, d,
                                 ("product_name", "description", "price", "is_active")))


@products_bp.delete("/products/<int:product_id>")
@roles_required(*STAFF)
def delete_product(product_id):
    # soft delete: existing subscriptions keep referencing the product
    row = execute("UPDATE products SET is_active = FALSE WHERE product_id = %s "
                  "RETURNING product_id", (product_id,))
    if not row:
        raise ApiError("Product not found", 404)
    execute("UPDATE plans SET is_active = FALSE WHERE product_id = %s", (product_id,))
    return jsonify({"message": "Product deactivated", "product_id": product_id})


# ====================== Variants ======================
@products_bp.get("/products/<int:product_id>/variants")
@login_required
def list_variants(product_id):
    _product_or_404(product_id)
    return jsonify(query_all(
        "SELECT * FROM product_variants WHERE product_id = %s ORDER BY variant_id", (product_id,)))


@products_bp.post("/products/<int:product_id>/variants")
@roles_required(*STAFF)
def create_variant(product_id):
    _product_or_404(product_id)
    d = json_body()
    require_fields(d, "attribute", "value")
    extra = _money(d.get("extra_price", 0), "extra_price")
    row = execute("INSERT INTO product_variants (product_id, attribute, value, extra_price) "
                  "VALUES (%s, %s, %s, %s) RETURNING *",
                  (product_id, d["attribute"], d["value"], extra))
    return jsonify(row), 201


@products_bp.put("/variants/<int:variant_id>")
@roles_required(*STAFF)
def update_variant(variant_id):
    d = json_body()
    _clean_money(d, "extra_price")
    return jsonify(update_fields("product_variants", "variant_id", variant_id, d,
                                 ("attribute", "value", "extra_price")))


@products_bp.delete("/variants/<int:variant_id>")
@roles_required(*STAFF)
def delete_variant(variant_id):
    row = execute("DELETE FROM product_variants WHERE variant_id = %s RETURNING variant_id",
                  (variant_id,))
    if not row:
        raise ApiError("Variant not found", 404)
    return jsonify({"message": "Variant deleted", "variant_id": variant_id})


# ====================== Plans ======================
def _validate_plan(d):
    if "billing_cycle" in d and d["billing_cycle"] not in BILLING_CYCLES:
        raise ApiError(f"billing_cycle must be one of: {', '.join(BILLING_CYCLES)}")
    if "duration" in d:
        try:
            d["duration"] = int(d["duration"])
        except (TypeError, ValueError):
            raise ApiError("duration must be a whole number of billing cycles")
        if d["duration"] < 1:
            raise ApiError("duration must be at least 1")
    _clean_money(d, "price")


@products_bp.get("/plans")
@login_required
def list_plans():
    sql = ("SELECT pl.*, pr.product_name FROM plans pl "
           "JOIN products pr ON pr.product_id = pl.product_id WHERE pl.is_active")
    params = []
    if request.args.get("product_id"):
        sql += " AND pl.product_id = %s"
        params.append(request.args["product_id"])
    return jsonify(query_all(sql + " ORDER BY pl.plan_id", params))


@products_bp.post("/plans")
@roles_required(*STAFF)
def create_plan():
    d = json_body()
    require_fields(d, "product_id", "billing_cycle", "price")
    d.setdefault("duration", 1)
    _validate_plan(d)
    _product_or_404(d["product_id"])
    row = execute("INSERT INTO plans (product_id, billing_cycle, duration, price) "
                  "VALUES (%s, %s, %s, %s) RETURNING *",
                  (d["product_id"], d["billing_cycle"], d["duration"], d["price"]))
    return jsonify(row), 201


@products_bp.get("/plans/<int:plan_id>")
@login_required
def get_plan(plan_id):
    row = query_one("SELECT pl.*, pr.product_name FROM plans pl "
                    "JOIN products pr ON pr.product_id = pl.product_id WHERE pl.plan_id = %s",
                    (plan_id,))
    if not row:
        raise ApiError("Plan not found", 404)
    return jsonify(row)


@products_bp.put("/plans/<int:plan_id>")
@roles_required(*STAFF)
def update_plan(plan_id):
    d = json_body()
    _validate_plan(d)
    return jsonify(update_fields("plans", "plan_id", plan_id, d,
                                 ("billing_cycle", "duration", "price", "is_active")))


@products_bp.delete("/plans/<int:plan_id>")
@roles_required(*STAFF)
def delete_plan(plan_id):
    row = execute("UPDATE plans SET is_active = FALSE WHERE plan_id = %s RETURNING plan_id",
                  (plan_id,))
    if not row:
        raise ApiError("Plan not found", 404)
    return jsonify({"message": "Plan deactivated", "plan_id": plan_id})


# ====================== Discounts ======================
def _validate_discount(d):
    if "type" in d and d["type"] not in ("percent", "fixed"):
        raise ApiError("type must be 'percent' or 'fixed'")
    _clean_money(d, "value")
    if d.get("type") == "percent" and d.get("value", 0) > 100:
        raise ApiError("Percent discount cannot exceed 100")


@products_bp.get("/discounts")
@roles_required(*STAFF)
def list_discounts():
    return jsonify(query_all("SELECT * FROM discounts ORDER BY discount_id"))


@products_bp.post("/discounts")
@roles_required(*STAFF)
def create_discount():
    d = json_body()
    require_fields(d, "code", "type", "value")
    _validate_discount(d)
    row = execute("INSERT INTO discounts (code, type, value, valid_from, valid_until) "
                  "VALUES (%s, %s, %s, %s, %s) RETURNING *",
                  (d["code"].strip().upper(), d["type"], d["value"],
                   d.get("valid_from"), d.get("valid_until")))
    return jsonify(row), 201


@products_bp.put("/discounts/<int:discount_id>")
@roles_required(*STAFF)
def update_discount(discount_id):
    d = json_body()
    _validate_discount(d)
    if "code" in d:
        d["code"] = d["code"].strip().upper()
    return jsonify(update_fields("discounts", "discount_id", discount_id, d,
                                 ("code", "type", "value", "valid_from", "valid_until",
                                  "is_active")))


@products_bp.delete("/discounts/<int:discount_id>")
@roles_required(*STAFF)
def delete_discount(discount_id):
    row = execute("DELETE FROM discounts WHERE discount_id = %s RETURNING discount_id",
                  (discount_id,))
    if not row:
        raise ApiError("Discount not found", 404)
    return jsonify({"message": "Discount deleted", "discount_id": discount_id})


@products_bp.post("/discounts/validate")
@login_required
def validate_discount():
    d = json_body()
    require_fields(d, "code")
    row = query_one(
        "SELECT * FROM discounts WHERE code = %s AND is_active "
        "AND (valid_from IS NULL OR valid_from <= CURRENT_DATE) "
        "AND (valid_until IS NULL OR valid_until >= CURRENT_DATE)",
        (d["code"].strip().upper(),))
    if not row:
        raise ApiError("Invalid or expired discount code", 404)
    result = {"valid": True, "discount": row}
    if d.get("amount") is not None:
        amount = _money(d["amount"], "amount")
        off = amount * row["value"] / 100 if row["type"] == "percent" else min(row["value"], amount)
        off = off.quantize(Decimal("0.01"))
        result.update(discount_amount=off, final_amount=amount - off)
    return jsonify(result)
