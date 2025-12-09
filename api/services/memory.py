import os
import json
import redis
from datetime import datetime
from api.services.db import get_postgres_conn


# === Redis ===
redis_client = redis.Redis(
    host="localhost",    # ganti sesuai env
    port=6379,
    decode_responses=True
)

SESSION_TTL = 86400  # 24 hours

# ============ Redis Session Management =============

def save_session_data(session_id: str, data: dict):
    """Save complete session data (PDF info + chat history)"""
    key = f"session:{session_id}"
    redis_client.set(key, json.dumps(data), ex=SESSION_TTL)
    
def get_session_data(session_id: str):
    """Get complete session data"""
    key = f"session:{session_id}"
    data_json = redis_client.get(key)
    return json.loads(data_json) if data_json else None

def update_session_pdf(session_id: str, doc_id: str, pdf_name: str, pdf_url: str):
    """Update PDF info in session"""
    session = get_session_data(session_id) or {}
    session['doc_id'] = doc_id
    session['pdf_name'] = pdf_name
    session['pdf_url'] = pdf_url
    session['chat_history'] = session.get('chat_history', [])
    save_session_data(session_id, session)
    
def add_session_message(session_id: str, role: str, content: str):
    """Add message to session chat history"""
    session = get_session_data(session_id) or {'chat_history': []}
    if 'chat_history' not in session:
        session['chat_history'] = []
    session['chat_history'].append({'role': role, 'content': content})
    save_session_data(session_id, session)

# ============ Redis Chat Memory (Legacy) =============

def get_chat_history(chat_id: str):
    key = f"chat:{chat_id}"
    history_json = redis_client.get(key)
    return json.loads(history_json) if history_json else []

def save_message_redis(chat_id: str, role: str, content: str):
    key = f"chat:{chat_id}"
    history = get_chat_history(chat_id)
    history.append({"role": role, "content": content})
    redis_client.set(key, json.dumps(history), ex=SESSION_TTL)

# ============ Postgres Persistent Chat =============

def save_message_postgres(chat_id, doc_id, user_id, role, content):
    conn = get_postgres_conn()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO chat_messages (chat_id, doc_id, user_id, role, content, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (chat_id, doc_id, user_id, role, content, datetime.now()))
        conn.commit()
    conn.close()

def get_chat_history_postgres(chat_id):
    conn = get_postgres_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT role, content FROM chat_messages
            WHERE chat_id = %s ORDER BY timestamp ASC
        """, (chat_id,))
        rows = cur.fetchall()
    conn.close()
    return rows
