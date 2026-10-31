import re
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character."
    return True, "Valid password"

def register_user(email, password, role='customer', name="", phone="", address=""):
    from database import get_db
    import sqlite3

    is_valid, msg = validate_password(password)
    if not is_valid:
        return {"success": False, "message": msg}

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
                       (email, hash_password(password), role))
        user_id = cursor.lastrowid

        cursor.execute("INSERT INTO customers (user_id, name, email, phone, address) VALUES (?, ?, ?, ?, ?)",
                       (user_id, name or email.split('@')[0], email, phone, address))
        conn.commit()
        return {"success": True, "message": "User registered successfully", "user_id": user_id}
    except sqlite3.IntegrityError:
        return {"success": False, "message": "Email already registered."}
    finally:
        conn.close()

def login_user(email, password):
    from database import get_db

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()

    if user and user['password_hash'] == hash_password(password):
        cursor.execute("SELECT customer_id, name FROM customers WHERE user_id = ?", (user['user_id'],))
        cust = cursor.fetchone()
        cust_id = cust['customer_id'] if cust else None
        conn.close()
        return {
            "success": True,
            "user": {
                "user_id": user['user_id'],
                "email": user['email'],
                "role": user['role'],
                "customer_id": cust_id
            }
        }
    conn.close()
    return {"success": False, "message": "Invalid email or password."}
