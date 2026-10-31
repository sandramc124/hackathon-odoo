from flask import Flask, request, jsonify
from database import init_db, get_db
import auth
import products
import subscription
import billing

app = Flask(__name__, static_folder="../frontend", static_url_path="")

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    res = auth.register_user(data.get("email"), data.get("password"), data.get("role", "customer"), data.get("name"))
    return jsonify(res)

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    res = auth.login_user(data.get("email"), data.get("password"))
    return jsonify(res)

@app.route("/api/products", methods=["GET", "POST"])
def handle_products():
    if request.method == "POST":
        data = request.json
        res = products.create_product(data["product_name"], data.get("description", ""), data["price"])
        return jsonify(res)
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products")
        prods = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(prods)

@app.route("/api/subscriptions", methods=["GET", "POST"])
def handle_subscriptions():
    if request.method == "POST":
        data = request.json
        res = subscription.create_subscription(data["customer_id"], data["plan_id"], data["start_date"])
        return jsonify(res)
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subscriptions")
        subs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(subs)

@app.route("/api/dashboard", methods=["GET"])
def get_dashboard():
    return jsonify(billing.get_dashboard_metrics())

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
