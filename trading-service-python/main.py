import os
from fastapi import FastAPI
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Database configuration from .env
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", "5432")

# Database connection function
def get_db_connection():
    """Create and return a database connection to Neon"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
            sslmode="require"
        )
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

@app.get("/")
def read_root():
    """Health check endpoint"""
    return {"status": "Trading Service is running"}

@app.get("/health")
def health_check():
    """Check database connection"""
    conn = get_db_connection()
    if conn:
        conn.close()
        return {"status": "healthy", "database": "connected"}
    return {"status": "unhealthy", "database": "disconnected"}

@app.get("/stocks")
def get_stocks():
    """Get stocks from Neon database"""
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        # Adjust table name to your actual table
        cursor.execute("SELECT * FROM stock_signals LIMIT 10")
        stocks = cursor.fetchall()
        cursor.close()
        conn.close()

        if not stocks:
            # Fallback sample data
            return [{"stock": "RELIANCE", "price": 2950121}]

        # Convert rows (dicts) into clean JSON
        result = []
        for row in stocks:
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
        print(f"❌ Query failed: {e}")
        conn.close()
        return [{"stock": "RELIANCE", "price": 290050}]