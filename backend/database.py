import sqlite3
import os

DB_NAME = os.path.join(os.path.dirname(__file__), "subscription_system.db")

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r") as f:
        schema = f.read()
    conn = get_db()
    conn.executescript(schema)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
