import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

def create_chat_messages_table():
    conn = psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
    )

    try:
        with conn:
            with conn.cursor() as cur:
                # Cek apakah tabel sudah ada dengan struktur lama (session_id)
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'chat_messages' AND column_name = 'session_id';
                """)
                
                has_session_id = cur.fetchone() is not None
                
                if has_session_id:
                    # Drop tabel lama dengan struktur tidak sesuai
                    print("⚠️ Tabel chat_messages ditemukan dengan struktur lama, akan dibuat ulang...")
                    cur.execute("DROP TABLE IF EXISTS chat_messages CASCADE;")
                
                # Buat tabel dengan struktur yang benar
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id SERIAL PRIMARY KEY,
                        chat_id VARCHAR NOT NULL,
                        doc_id VARCHAR NOT NULL,
                        user_id VARCHAR NOT NULL,
                        role VARCHAR NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Buat index untuk performa query
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id ON chat_messages(chat_id);
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_doc_id ON chat_messages(doc_id);
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id);
                """)
                
                print("✅ Tabel chat_messages berhasil dibuat atau sudah ada.")
    finally:
        conn.close()

if __name__ == "__main__":
    create_chat_messages_table()
