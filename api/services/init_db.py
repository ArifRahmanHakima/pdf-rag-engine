import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

def get_connection():
    """Get PostgreSQL connection"""
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
    )


def create_users_table():
    """Create users table for authentication"""
    conn = get_connection()
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Create index on email for faster lookups
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    """
    
    with conn:
        with conn.cursor() as cur:
            cur.execute(create_table_sql)
            print("✅ Tabel users berhasil dibuat atau sudah ada.")
    conn.close()


def create_documents_table():
    """Create documents table for document access control"""
    conn = get_connection()
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        doc_id VARCHAR(255) UNIQUE NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        filename VARCHAR(500) NOT NULL,
        status VARCHAR(50) DEFAULT 'processing',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Create indexes for faster lookups
    CREATE INDEX IF NOT EXISTS idx_documents_doc_id ON documents(doc_id);
    CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
    """
    
    with conn:
        with conn.cursor() as cur:
            cur.execute(create_table_sql)
            print("✅ Tabel documents berhasil dibuat atau sudah ada.")
    conn.close()


def create_chat_messages_table():
    """Create chat_messages table for chat history"""
    conn = get_connection()

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id SERIAL PRIMARY KEY,
        chat_id VARCHAR(255) NOT NULL,
        doc_id VARCHAR(255) NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role VARCHAR(50) NOT NULL,
        content TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Create indexes for faster lookups
    CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id ON chat_messages(chat_id);
    CREATE INDEX IF NOT EXISTS idx_chat_messages_doc_id ON chat_messages(doc_id);
    CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id);
    """

    with conn:
        with conn.cursor() as cur:
            cur.execute(create_table_sql)
            print("✅ Tabel chat_messages berhasil dibuat atau sudah ada.")
    conn.close()


def init_all_tables():
    """Initialize all database tables"""
    print("🔧 Initializing database tables...")
    
    # Order matters due to foreign key constraints
    create_users_table()
    create_documents_table()
    create_chat_messages_table()
    
    print("✅ Semua tabel berhasil diinisialisasi!")


if __name__ == "__main__":
    init_all_tables()
