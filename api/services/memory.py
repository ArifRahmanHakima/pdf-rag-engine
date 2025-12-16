import os
import json
import redis
from datetime import datetime
from api.services.db import get_postgres_conn

# === Redis (dengan fallback ke Postgres jika tidak tersedia) ===
REDIS_AVAILABLE = False
redis_client = None

try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
        socket_connect_timeout=2  # Timeout 2 detik
    )
    # Test connection
    redis_client.ping()
    REDIS_AVAILABLE = True
    print("✅ Redis connected successfully")
except Exception as e:
    print(f"⚠️ Redis not available, using PostgreSQL only: {e}")
    REDIS_AVAILABLE = False

# ============ Redis Chat Memory (dengan Postgres fallback) ============= 
def get_chat_history(chat_id: str):
    """Get chat history from Redis (or Postgres fallback)"""
    # Jika Redis tersedia, coba ambil dari Redis dulu
    if REDIS_AVAILABLE and redis_client:
        try:
            key = f"chat:{chat_id}"
            history_json = redis_client.get(key)
            
            if history_json:
                return json.loads(history_json)
        except Exception as e:
            print(f"⚠️ Redis read error, falling back to Postgres: {e}")
    
    # Fallback ke Postgres
    return get_chat_history_postgres(chat_id)

def save_message_redis(chat_id: str, role: str, content: str):
    """Save message to Redis (if available)"""
    if not REDIS_AVAILABLE or not redis_client:
        # Skip Redis jika tidak tersedia
        return
    
    try:
        key = f"chat:{chat_id}"
        history = get_chat_history(chat_id)
        
        # Tambahkan message baru
        history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        # Simpan kembali ke Redis
        redis_client.set(key, json.dumps(history))
        
        # Set expiry 24 jam (opsional)
        redis_client.expire(key, 86400)
    except Exception as e:
        print(f"⚠️ Redis write error (ignored): {e}")

# ============ Postgres Persistent Chat ============= 
def save_message_postgres(chat_id, doc_id, user_id, role, content):
    """Save message to PostgreSQL"""
    conn = get_postgres_conn()
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chat_messages (chat_id, doc_id, user_id, role, content, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (chat_id, doc_id, user_id, role, content, datetime.now()))
        conn.commit()
    finally:
        conn.close()

def get_chat_history_postgres(chat_id):
    """Get chat history from PostgreSQL"""
    conn = get_postgres_conn()
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT role, content, timestamp
                FROM chat_messages
                WHERE chat_id = %s
                ORDER BY timestamp ASC
            """, (chat_id,))
            rows = cur.fetchall()
            
            # Convert to list of dicts
            history = [
                {
                    "role": row["role"],
                    "content": row["content"],
                    "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None
                }
                for row in rows
            ]
            return history
    finally:
        conn.close()

def delete_chat_history(chat_id: str):
    """Delete chat history from Redis and Postgres"""
    # Delete from Redis (if available)
    if REDIS_AVAILABLE and redis_client:
        try:
            key = f"chat:{chat_id}"
            redis_client.delete(key)
        except Exception as e:
            print(f"⚠️ Redis delete error (ignored): {e}")
    
    # Delete from Postgres
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_messages WHERE chat_id = %s", (chat_id,))
        conn.commit()
    finally:
        conn.close()