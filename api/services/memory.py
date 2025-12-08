import os
import json
import redis
from datetime import datetime
from api.services.db import get_postgres_conn

# === Redis ===
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

# ============ Redis Chat Memory ============= 
def get_chat_history(chat_id: str):
    """Get chat history from Redis"""
    key = f"chat:{chat_id}"
    history_json = redis_client.get(key)
    
    if history_json:
        return json.loads(history_json)
    else:
        return []

def save_message_redis(chat_id: str, role: str, content: str):
    """Save message to Redis"""
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
    # Delete from Redis
    key = f"chat:{chat_id}"
    redis_client.delete(key)
    
    # Delete from Postgres
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_messages WHERE chat_id = %s", (chat_id,))
        conn.commit()
    finally:
        conn.close()