from datetime import datetime, timedelta
from database import get_db

def calculate_next_billing(start_date_str, billing_cycle):
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
    if billing_cycle == 'daily':
        return (start_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    elif billing_cycle == 'weekly':
        return (start_dt + timedelta(weeks=1)).strftime("%Y-%m-%d")
    elif billing_cycle == 'monthly':
        return (start_dt + timedelta(days=30)).strftime("%Y-%m-%d")
    elif billing_cycle == 'yearly':
        return (start_dt + timedelta(days=365)).strftime("%Y-%m-%d")
    return start_date_str

def create_subscription(customer_id, plan_id, start_date, payment_terms="Immediate", status="Active"):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT billing_cycle, price FROM plans WHERE plan_id = ?", (plan_id,))
    plan = cursor.fetchone()
    if not plan:
        conn.close()
        return {"success": False, "message": "Plan not found"}
        
    next_billing = calculate_next_billing(start_date, plan['billing_cycle'])
    
    cursor.execute(
        "INSERT INTO subscriptions (customer_id, plan_id, status, start_date, next_billing_date, payment_terms) VALUES (?, ?, ?, ?, ?, ?)",
        (customer_id, plan_id, status, start_date, next_billing, payment_terms)
    )
    sub_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"success": True, "subscription_id": sub_id}

def update_subscription_status(subscription_id, new_status):
    valid_statuses = ['Draft', 'Quotation', 'Confirmed', 'Active', 'Paused', 'Closed']
    if new_status not in valid_statuses:
        return {"success": False, "message": "Invalid status"}
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE subscriptions SET status = ? WHERE subscription_id = ?", (new_status, subscription_id))
    conn.commit()
    conn.close()
    return {"success": True, "status": new_status}
