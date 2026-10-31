"""Member 1 - Authentication & Customer Management (branch: feature-auth)

Endpoints
  POST   /auth/register     public (first user ever becomes admin; only an admin can set another role)
  POST   /auth/login
  POST   /auth/logout
  GET    /auth/me
  GET    /customers         admin/staff   (?q= search)
  POST   /customers         admin/staff
  GET    /customers/<id>    admin/staff or the customer themself
  PUT    /customers/<id>    admin/staff or the customer themself
  DELETE /customers/<id>    admin

Other modules import: login_required, roles_required, current_customer_id
"""
from functools import wraps

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from database import (ApiError, execute, json_body, query_all, query_one,
                      require_fields, transaction, update_fields)

auth_bp = Blueprint("auth", __name__)

ROLES = ("admin", "staff", "customer")
CUSTOMER_FIELDS = ("name", "email", "phone", "address")


# ---------- decorators / helpers (used by all modules) ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            raise ApiError("Login required", 401)
        return f(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                raise ApiError("Login required", 401)
            if session.get("role") not in roles:
                raise ApiError("You do not have permission for this action", 403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def current_customer_id():
    """customer_id linked to the logged-in user (None for staff/admin or if unlinked)."""
    if session.get("role") != "customer":
        return None
    row = query_one("SELECT customer_id FROM customers WHERE user_id = %s",
                    (session["user_id"],))
    return row["customer_id"] if row else None


# ---------- authentication ----------
@auth_bp.post("/auth/register")
def register():
    d = json_body()
    require_fields(d, "name", "email", "password")
    if len(d["password"]) < 6:
        raise ApiError("Password must be at least 6 characters")

    email = d["email"].strip().lower()
    is_first_user = query_one("SELECT 1 AS x FROM users LIMIT 1") is None
    role = "customer"
    if is_first_user:
        role = "admin"
    elif d.get("role") in ROLES and session.get("role") == "admin":
        role = d["role"]

    customer_id = None
    with transaction() as cur:
        cur.execute(
            "INSERT INTO users (name, email, password_hash, role) "
            "VALUES (%s, %s, %s, %s) RETURNING user_id",
            (d["name"].strip(), email, generate_password_hash(d["password"]), role),
        )
        user_id = cur.fetchone()["user_id"]

        if role == "customer":
            # link to an existing staff-created customer record with the same email, if any
            cur.execute(
                "UPDATE customers SET user_id = %s WHERE email = %s AND user_id IS NULL "
                "RETURNING customer_id", (user_id, email))
            row = cur.fetchone()
            if not row:
                cur.execute(
                    "INSERT INTO customers (user_id, name, email, phone, address) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING customer_id",
                    (user_id, d["name"].strip(), email, d.get("phone"), d.get("address")))
                row = cur.fetchone()
            customer_id = row["customer_id"]

    return jsonify({"user_id": user_id, "email": email, "role": role,
                    "customer_id": customer_id}), 201


@auth_bp.post("/auth/login")
def login():
    d = json_body()
    require_fields(d, "email", "password")
    user = query_one("SELECT * FROM users WHERE email = %s", (d["email"].strip().lower(),))
    if not user or not check_password_hash(user["password_hash"], d["password"]):
        raise ApiError("Invalid email or password", 401)

    session.clear()
    session["user_id"] = user["user_id"]
    session["role"] = user["role"]
    customer = query_one("SELECT customer_id FROM customers WHERE user_id = %s",
                         (user["user_id"],))
    return jsonify({"user_id": user["user_id"], "name": user["name"], "role": user["role"],
                    "customer_id": customer["customer_id"] if customer else None})


@auth_bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@auth_bp.get("/auth/me")
@login_required
def me():
    user = query_one("SELECT user_id, name, email, role FROM users WHERE user_id = %s",
                     (session["user_id"],))
    user["customer_id"] = current_customer_id()
    return jsonify(user)


# ---------- customer CRUD ----------
def _check_customer_access(customer_id):
    if session.get("role") == "customer" and current_customer_id() != customer_id:
        raise ApiError("You can only access your own customer record", 403)


@auth_bp.get("/customers")
@roles_required("admin", "staff")
def list_customers():
    q = request.args.get("q")
    if q:
        rows = query_all("SELECT * FROM customers WHERE name ILIKE %s OR email ILIKE %s "
                         "ORDER BY customer_id", (f"%{q}%", f"%{q}%"))
    else:
        rows = query_all("SELECT * FROM customers ORDER BY customer_id")
    return jsonify(rows)


@auth_bp.post("/customers")
@roles_required("admin", "staff")
def create_customer():
    d = json_body()
    require_fields(d, "name", "email")
    row = execute(
        "INSERT INTO customers (name, email, phone, address) VALUES (%s, %s, %s, %s) "
        "RETURNING *", (d["name"], d["email"].strip().lower(), d.get("phone"), d.get("address")))
    return jsonify(row), 201


@auth_bp.get("/customers/<int:customer_id>")
@roles_required("admin", "staff", "customer")
def get_customer(customer_id):
    _check_customer_access(customer_id)
    row = query_one("SELECT * FROM customers WHERE customer_id = %s", (customer_id,))
    if not row:
        raise ApiError("Customer not found", 404)
    return jsonify(row)


@auth_bp.put("/customers/<int:customer_id>")
@roles_required("admin", "staff", "customer")
def update_customer(customer_id):
    _check_customer_access(customer_id)
    d = json_body()
    if "email" in d:
        d["email"] = d["email"].strip().lower()
    return jsonify(update_fields("customers", "customer_id", customer_id, d, CUSTOMER_FIELDS))


@auth_bp.delete("/customers/<int:customer_id>")
@roles_required("admin")
def delete_customer(customer_id):
    row = execute("DELETE FROM customers WHERE customer_id = %s RETURNING customer_id",
                  (customer_id,))
    if not row:
        raise ApiError("Customer not found", 404)
    return jsonify({"message": "Customer deleted", "customer_id": customer_id})
