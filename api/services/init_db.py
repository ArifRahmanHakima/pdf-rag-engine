import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
    )

def create_chat_messages_table():
    conn = get_connection()

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id SERIAL PRIMARY KEY,
        chat_id VARCHAR NOT NULL,
        doc_id VARCHAR NOT NULL,
        user_id VARCHAR NOT NULL,
        role VARCHAR NOT NULL,
        content TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    with conn:
        with conn.cursor() as cur:
            cur.execute(create_table_sql)
            print("✅ Tabel chat_messages berhasil dibuat atau sudah ada.")
    conn.close()

def create_documents_table():
    conn = get_connection()

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        doc_id VARCHAR UNIQUE NOT NULL,
        file_name VARCHAR NOT NULL,
        file_path VARCHAR,
        summary TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    with conn:
        with conn.cursor() as cur:
            cur.execute(create_table_sql)
            print("✅ Tabel documents berhasil dibuat atau sudah ada.")
    conn.close()

def init_all_tables():
    """Initialize all database tables"""
    create_chat_messages_table()
    create_documents_table()
    print("✅ Semua tabel berhasil diinisialisasi.")

if __name__ == "__main__":
    init_all_tables()
