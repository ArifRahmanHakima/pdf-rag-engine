import os
from dotenv import load_dotenv
from api.services.db import get_postgres_conn

load_dotenv()

def save_document(doc_id: str, file_name: str, file_path: str = None, summary: str = None):
    """Simpan atau update dokumen ke database"""
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            # Upsert - insert atau update jika sudah ada
            cur.execute("""
                INSERT INTO documents (doc_id, file_name, file_path, summary)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (doc_id) 
                DO UPDATE SET 
                    file_name = EXCLUDED.file_name,
                    file_path = EXCLUDED.file_path,
                    summary = COALESCE(EXCLUDED.summary, documents.summary)
            """, (doc_id, file_name, file_path, summary))
            conn.commit()
            print(f"✅ Document saved to DB: {file_name} ({doc_id})")
    except Exception as e:
        print(f"❌ Error saving document: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_all_documents():
    """Ambil semua dokumen dari database"""
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT doc_id, file_name, file_path, summary, created_at
                FROM documents
                ORDER BY created_at DESC
            """)
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"❌ Error getting documents: {e}")
        return []
    finally:
        conn.close()

def get_document_by_id(doc_id: str):
    """Ambil dokumen berdasarkan doc_id"""
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT doc_id, file_name, file_path, summary, created_at
                FROM documents
                WHERE doc_id = %s
            """, (doc_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"❌ Error getting document: {e}")
        return None
    finally:
        conn.close()

def get_chat_history(doc_id: str, user_id: str = None):
    """Ambil chat history untuk dokumen tertentu"""
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            if user_id:
                cur.execute("""
                    SELECT role, content, timestamp
                    FROM chat_messages
                    WHERE doc_id = %s AND user_id = %s
                    ORDER BY timestamp ASC
                """, (doc_id, user_id))
            else:
                cur.execute("""
                    SELECT role, content, timestamp
                    FROM chat_messages
                    WHERE doc_id = %s
                    ORDER BY timestamp ASC
                """, (doc_id,))
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"❌ Error getting chat history: {e}")
        return []
    finally:
        conn.close()

def delete_document(doc_id: str):
    """Hapus dokumen dan chat history dari database"""
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            # Hapus chat messages terlebih dahulu (foreign key)
            cur.execute("DELETE FROM chat_messages WHERE doc_id = %s", (doc_id,))
            # Hapus dokumen
            cur.execute("DELETE FROM documents WHERE doc_id = %s", (doc_id,))
            conn.commit()
            print(f"🗑️ Document deleted from DB: {doc_id}")
            return True
    except Exception as e:
        print(f"❌ Error deleting document: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
