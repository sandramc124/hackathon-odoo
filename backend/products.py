from database import get_db

def create_product(product_name, description, price, cost_price=0.0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO products (product_name, description, price, cost_price) VALUES (?, ?, ?, ?)",
        (product_name, description, price, cost_price)
    )
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"success": True, "product_id": product_id}

def create_variant(product_id, variant_name, price_extra):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO product_variants (product_id, variant_name, price_extra) VALUES (?, ?, ?)",
        (product_id, variant_name, price_extra)
    )
    variant_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"success": True, "variant_id": variant_id}

def create_plan(product_id, plan_name, billing_cycle, duration, price, min_quantity=1, auto_close=0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO plans (product_id, plan_name, billing_cycle, duration, price, min_quantity, auto_close) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (product_id, plan_name, billing_cycle, duration, price, min_quantity, auto_close)
    )
    plan_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"success": True, "plan_id": plan_id}

def create_discount(code, discount_type, value, min_purchase=0.0, usage_limit=-1):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO discounts (code, discount_type, value, min_purchase, usage_limit) VALUES (?, ?, ?, ?, ?)",
        (code, discount_type, value, min_purchase, usage_limit)
    )
    discount_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"success": True, "discount_id": discount_id}
