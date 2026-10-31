from datetime import datetime
from database import get_db

def generate_invoice_for_subscription(subscription_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT s.subscription_id, s.customer_id, p.price, p.product_id
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.plan_id
        WHERE s.subscription_id = ?
    """, (subscription_id,))
    sub = cursor.fetchone()
    
    if not sub:
        conn.close()
        return {"success": False, "message": "Subscription not found"}
        
    subtotal = sub['price']
    tax = subtotal * 0.10
    total = subtotal + tax
    today = datetime.now().strftime("%Y-%m-%d")
    due = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute(
        "INSERT INTO invoices (subscription_id, customer_id, invoice_date, due_date, subtotal, tax, total, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'Draft')",
        (subscription_id, sub['customer_id'], today, due, subtotal, tax, total)
    )
    inv_id = cursor.lastrowid
    
    cursor.execute(
        "INSERT INTO invoice_lines (invoice_id, product_id, description, quantity, unit_price, amount) VALUES (?, ?, 'Subscription Renewal', 1, ?, ?)",
        (inv_id, sub['product_id'], subtotal, subtotal)
    )
    conn.commit()
    conn.close()
    return {"success": True, "invoice_id": inv_id}

def record_payment(invoice_id, amount, payment_method, notes=""):
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute(
        "INSERT INTO payments (invoice_id, payment_date, amount, payment_method, notes) VALUES (?, ?, ?, ?, ?)",
        (invoice_id, today, amount, payment_method, notes)
    )
    
    cursor.execute("UPDATE invoices SET status = 'Paid' WHERE invoice_id = ?", (invoice_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Payment recorded successfully"}

def get_dashboard_metrics():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as active_count FROM subscriptions WHERE status = 'Active'")
    active_subs = cursor.fetchone()['active_count']
    
    cursor.execute("SELECT SUM(amount) as total_rev FROM payments")
    total_rev = cursor.fetchone()['total_rev'] or 0.0
    
    cursor.execute("SELECT SUM(total) as pending FROM invoices WHERE status != 'Paid'")
    pending_rev = cursor.fetchone()['pending'] or 0.0
    
    conn.close()
    return {
        "active_subscriptions": active_subs,
        "total_revenue": total_rev,
        "pending_revenue": pending_rev
    }
