import tempfile, sqlite3, os
import sys
sys.path.append(".")
from database import SessionLocal
print("Testing database connection...")
db = SessionLocal()
db.close()
print("✅ SQLite database connection successful")

try:
    import psycopg2
    conn = psycopg2.connect(
        host="localhost", 
        port=5432, 
        database="ai_validation", 
        user="ai_user", 
        password="secure_password_123"
    )
    conn.close()
    print("✅ PostgreSQL connection successful")
except Exception as e:
    print(f"❌ PostgreSQL error: {e}")

try:
    import redis
    r = redis.Redis(host="localhost", port=6379, db=0)
    r.ping()
    print("✅ Redis connection successful")
except Exception as e:
    print(f"❌ Redis error: {e}")

