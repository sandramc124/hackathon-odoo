"""Entry point. Run:  python app.py   (or: flask --app app run --debug)

Changes to this file go through the team leader only.
"""
import logging
import os
from decimal import Decimal

import psycopg2
from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from auth import auth_bp
from billing import billing_bp
from database import ApiError
from products import products_bp
from subscription import subscription_bp

load_dotenv()


def _json_default(o):
    if isinstance(o, Decimal):
        return float(o)
    return DefaultJSONProvider.default(o)  # dates, datetimes, etc.


class JSONProvider(DefaultJSONProvider):
    default = staticmethod(_json_default)


def create_app():
    app = Flask(
    __name__,
    static_folder="../frontend",
    static_url_path=""
    
    )
    
    app.json = JSONProvider(app)
    app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")
    CORS(app, supports_credentials=True)

    for bp in (auth_bp, products_bp, subscription_bp, billing_bp):
        app.register_blueprint(bp)

    @app.get("/")
    def home():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(ApiError)
    def handle_api_error(e):
        return jsonify({"error": e.message}), e.status

    @app.errorhandler(psycopg2.IntegrityError)
    def handle_integrity_error(e):
        return jsonify({"error": "Conflicts with existing data "
                                 "(duplicate value or record is still referenced)"}), 409

    @app.errorhandler(psycopg2.DataError)
    def handle_data_error(e):
        return jsonify({"error": "Invalid value supplied (check dates and numbers)"}), 400

    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        return jsonify({"error": e.description}), e.code

    @app.errorhandler(Exception)
    def handle_unexpected(e):
        logging.exception("Unhandled error")
        return jsonify({"error": "Internal server error"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5000)))
