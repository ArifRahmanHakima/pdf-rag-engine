# Database Migration Guide: Local Storage → PostgreSQL + Qdrant

## Overview

Sistem RAG Anda telah dimigrasikan dari penyimpanan file lokal ke database modern:

- **Chunks**: PostgreSQL (menggantikan `kv_store_text_chunks.json`)
- **Embeddings**: Qdrant (menggantikan `vdb_chunks.json`)
- **Metadata**: PostgreSQL dengan relasi folder-like

## Setup Instructions

### 1. Install PostgreSQL

**Windows:**
```powershell
# Gunakan PostgreSQL installer dari: https://www.postgresql.org/download/windows/
# Atau gunakan Chocolatey
choco install postgresql
```

**Create database dan user:**
```sql
CREATE USER rag_user WITH PASSWORD 'rag_password';
CREATE DATABASE rag_system OWNER rag_user;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE rag_system TO rag_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO rag_user;
```

### 2. Install dan Run Qdrant

**Menggunakan Docker (Recommended):**
```powershell
docker run -d `
  --name qdrant `
  -p 6333:6333 `
  -p 6334:6334 `
  -v qdrant_storage:/qdrant/storage `
  qdrant/qdrant:latest
```

**Atau local binary:**
```
Download dari: https://github.com/qdrant/qdrant/releases
Jalankan: qdrant.exe
```

### 3. Update Dependencies

```powershell
# Install database packages
pip install sqlalchemy psycopg2-binary qdrant-client

# Atau dari requirements
pip install -r requirements.txt
```

### 4. Update .env File

Copy dari `.env.example`:
```powershell
cp .env.example .env
```

Update nilai PostgreSQL dan Qdrant sesuai konfigurasi Anda:
```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=rag_password
POSTGRES_DB=rag_system

QDRANT_HOST=localhost
QDRANT_PORT=6333
```

### 5. Initialize Database

```powershell
python -c "from app.db import init_db; init_db()"
```

Ini akan membuat semua tables di PostgreSQL dan collections di Qdrant.

## Database Schema

### PostgreSQL Tables

```
sessions (folder structure)
├── id (PK): session folder ID (folder_1, folder_2, etc)
├── metadata: session metadata
└── documents (1-to-many)
    ├── id (PK): document ID
    ├── session_id (FK)
    ├── filename
    ├── doc_type: 'ocr' atau 'docstring'
    ├── pages, size, extraction_time
    └── chunks (1-to-many)
        ├── id (PK): MD5 hash dari content
        ├── document_id (FK)
        ├── session_id: denormalized for speed
        ├── content: text content
        ├── chunk_index: order
        ├── embedding_id: reference ke Qdrant
        └── metadata: JSON

embeddings (tracking)
├── id (PK)
├── chunk_id (FK ke chunks)
├── qdrant_id: ID di Qdrant
└── ...
```

### Qdrant Collections

```
chunks
├── vector: embedding (1024-dim)
├── payload:
│   ├── chunk_id
│   ├── session_id
│   ├── document_id
│   ├── chunk_index
│   └── metadata

entities
├── vector: embedding
└── payload: entity metadata

relationships
├── vector: embedding
└── payload: relationship metadata
```

## API Changes

### Lama (File-based):
```python
# Load dari JSON
with open('kv_store_text_chunks.json') as f:
    chunks = json.load(f)
```

### Baru (Database-based):
```python
from app.db import storage_manager

# Get chunks
chunks = storage_manager.get_chunks_by_document(doc_id)

# Search by embedding
results = storage_manager.search_chunks_by_embedding(
    embedding=query_vector,
    limit=10,
    session_id=session_id
)

# Save chunks
storage_manager.save_chunks(
    session_id=session_id,
    document_id=doc_id,
    chunks=chunk_texts,
    embeddings=embedding_vectors
)
```

## Migration dari Local Storage (Optional)

Jika ingin migrate data lama dari JSON files:

```python
from app.db import storage_manager
import json
from pathlib import Path

# Load old chunks
with open('rag_storage/kv_store_text_chunks.json') as f:
    old_chunks = json.load(f)

# Migrate to database
for chunk_id, chunk_data in old_chunks.items():
    # ... mapping logic
    storage_manager.save_chunks(...)
```

## Benefits

✅ **Scalability**: PostgreSQL handle volume besar data
✅ **Structured Queries**: SQL queries untuk metadata
✅ **Vector Search**: Qdrant native vector similarity
✅ **Multi-tenancy**: Session isolation dengan database relations
✅ **Persistence**: Data persisten antar server restart
✅ **Concurrent Access**: Database handle concurrent requests
✅ **Backup/Recovery**: Standard database backup tools

## Troubleshooting

### PostgreSQL Connection Error
```
ERROR: could not connect to server
```
- Check: `psql -U rag_user -d rag_system -h localhost`
- Verify .env credentials

### Qdrant Connection Error
```
ConnectionError: Failed to connect to Qdrant
```
- Check: `http://localhost:6333/health`
- Verify Qdrant running

### Alembic Migrations (Future)

Untuk manage schema changes:
```powershell
alembic init alembic
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Performance Tips

1. **Indexing**: Already configured pada frequently queried columns
2. **Connection Pool**: SQLAlchemy uses pooling by default
3. **Batch Operations**: Gunakan batch untuk multiple inserts
4. **Qdrant Snapshots**: Regular backups

```python
# Backup Qdrant
qdrant_manager.client.create_snapshot(collection_name='chunks')

# Restore
qdrant_manager.client.recover_snapshot(snapshot_path='...')
```

## Next Steps

1. Update `document_service.py` untuk gunakan `storage_manager` 
2. Update `search_logic.py` untuk gunakan Qdrant search
3. Test dengan sample PDFs
4. Monitor performance dan optimize queries
