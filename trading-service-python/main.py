import os
from fastapi import FastAPI
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Load environment variables
load_dotenv()

app = FastAPI()

# ✅ Use Neon DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")

# 🔌 Database connection function
def get_db_connection():
    try:
        conn = psycopg2.connect(
            DATABASE_URL,
            sslmode="require"
        )
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None


# 🏠 Root endpoint
@app.get("/")
def read_root():
    return {"status": "Trading Service is running"}


# ❤️ Health check
@app.get("/health")
def health_check():
    conn = get_db_connection()
    if conn:
        conn.close()
        return {"status": "healthy", "database": "connected"}
    return {"status": "unhealthy", "database": "disconnected"}


# 📊 Get stocks
@app.get("/stocks")
def get_stocks():
    conn = get_db_connection()

    if not conn:
        return {"error": "Database connection failed"}

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # 🔥 Make sure this table exists in Neon
        cursor.execute("SELECT * FROM stock_signals LIMIT 10")
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        if not rows:
            return [{"stock_name": "RELIANCE", "price": 2950}]

        # ✅ Clean JSON response
        result = []
        for row in rows:
            result.append({
                "id": row.get("id"),
                "stock_name": row.get("stock_name"),
                "price": row.get("price"),
                "target": row.get("target"),
                "stop_loss": row.get("stop_loss"),
                "quantity": row.get("quantity"),
                "risk_reward": row.get("risk_reward"),
                "pnl": row.get("pnl")
            })

        return result

    except Exception as e:
        import traceback
        print("❌ Query failed:", e)
        traceback.print_exc()

        return {
            "error": "Query failed",
            "details": str(e)
        }


# 💰 Place trade (basic version)
@app.post("/trade")
def place_trade(trade: dict):
    conn = get_db_connection()

    if not conn:
        return {"error": "Database connection failed"}

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO stock_signals 
            (stock_name, price, target, stop_loss, quantity, risk_reward, pnl)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            trade.get("stock_name"),
            trade.get("price"),
            trade.get("target"),
            trade.get("stop_loss"),
            trade.get("quantity"),
            trade.get("risk_reward"),
            trade.get("pnl")
        ))

        new_id = cursor.fetchone()[0]
        conn.commit()

        cursor.close()
        conn.close()

        return {"message": "Trade inserted", "id": new_id}

    except Exception as e:
        import traceback
        print("❌ Insert failed:", e)
        traceback.print_exc()

        return {
            "error": "Insert failed",
            "details": str(e)
        }