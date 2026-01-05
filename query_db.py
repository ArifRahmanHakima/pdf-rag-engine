#!/usr/bin/env python3
"""
PostgreSQL Database Commands - cara berbeda untuk melihat data
Script ini menyediakan berbagai cara untuk query database PostgreSQL
"""

import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Get database config from .env
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "rag_db")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

def print_option(num, desc):
    print(f"\n{num}. {desc}")

print("""
╔════════════════════════════════════════════════════════════════════╗
║         PostgreSQL Database Query - Berbagai Cara                  ║
╚════════════════════════════════════════════════════════════════════╝

CARA 1: Python Script (inspect_tables.py) - RECOMMENDED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Paling mudah, sudah dibuat dan siap dijalankan.

  Command:
    python inspect_tables.py

  Keuntungan:
    ✅ Output rapi dan terformat
    ✅ Menampilkan summary semua table
    ✅ Easy to use, tidak perlu password


CARA 2: Command Line - psql
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Menggunakan PostgreSQL command line tool.

  Koneksi ke database:
    psql -h {host} -U {user} -d {db} -W
    
  Ganti dengan nilai Anda:
    psql -h {host} -U {db_user} -d {db_name} -W
    
  Kemudian gunakan SQL commands:
    \\dt                          -- List semua tables
    SELECT * FROM sessions;       -- Lihat sessions
    SELECT * FROM documents;      -- Lihat documents
    SELECT * FROM chunks;         -- Lihat chunks
    SELECT * FROM embeddings;     -- Lihat embeddings
    
  Exit:
    \\q


CARA 3: GUI Tools
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tools visual yang lebih user-friendly:

  pgAdmin (Web-based):
    https://www.pgadmin.org/download/
    Buka browser → http://localhost:5050
    
  DBeaver (Desktop):
    https://dbeaver.io/download/
    Buka DBeaver → New Connection → PostgreSQL
    
  DataGrip (JetBrains):
    https://www.jetbrains.com/datagrip/


CARA 4: Python Interactive
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Query database dari Python REPL.

  Command:
    python
    
  Kemudian:
    from app.db.models import SessionLocal, Document, Session, Chunk
    db = SessionLocal()
    
    # Lihat semua documents
    docs = db.query(Document).all()
    for doc in docs:
        print(f"{doc.id}: {doc.filename}")
    
    # Lihat chunks dari document tertentu
    chunks = db.query(Chunk).filter(Chunk.document_id == "doc_id").all()
    for chunk in chunks:
        print(chunk.content)
    
    db.close()


CARA 5: SQL Query langsung
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lihat file query_db.py yang sudah dibuat untuk contoh queries.

  Berikut SQL yang berguna:

  1. Lihat jumlah data:
     SELECT 'Sessions' as table_name, COUNT(*) FROM sessions
     UNION ALL
     SELECT 'Documents', COUNT(*) FROM documents
     UNION ALL
     SELECT 'Chunks', COUNT(*) FROM chunks
     UNION ALL
     SELECT 'Embeddings', COUNT(*) FROM embeddings;

  2. Lihat documents dengan chunks count:
     SELECT d.id, d.filename, d.doc_type, COUNT(c.id) as chunk_count
     FROM documents d
     LEFT JOIN chunks c ON d.id = c.document_id
     GROUP BY d.id;

  3. Lihat chunks dari document tertentu:
     SELECT chunk_index, LENGTH(content) as content_length, content
     FROM chunks
     WHERE document_id = 'doc_id'
     ORDER BY chunk_index;

  4. Lihat embeddings stats:
     SELECT document_id, COUNT(*) as embedding_count, AVG(vector_dim) as avg_dim
     FROM embeddings
     GROUP BY document_id;


CONNECTION INFO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

print(f"  Host:     {DB_HOST}")
print(f"  Port:     {DB_PORT}")
print(f"  Database: {DB_NAME}")
print(f"  User:     {DB_USER}")
print(f"  Password: {'***' if DB_PASSWORD else '(tidak ada)'}")

print("""
NEXT STEPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Jalankan: python inspect_tables.py
2. Upload dokumen dari UI
3. Jalankan lagi: python inspect_tables.py
4. Lihat data yang sudah masuk!

════════════════════════════════════════════════════════════════════════
""")
