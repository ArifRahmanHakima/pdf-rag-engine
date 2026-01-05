# Virtual Folder Structure dalam PostgreSQL + Qdrant

## Konsep

Anda masih bisa membayangkan struktur **folder-like** meskipun datanya di database:

```
PostgreSQL (relational)           Qdrant (vector)
├─ sessions                       ├─ collections
│  ├─ folder_1/                   │  ├─ chunks
│  │  ├─ documents                │  │  ├─ vector_1 (embedding dari chunk 1)
│  │  │  ├─ doc_ocr_1             │  │  ├─ vector_2 (embedding dari chunk 2)
│  │  │  │  ├─ chunks             │  │  └─ ...
│  │  │  │  └─ metadata           │  │
│  │  │  ├─ doc_docstring_1       │  ├─ entities
│  │  │  │  ├─ chunks             │  │  └─ vector_X (entity embeddings)
│  │  │  │  └─ metadata           │  │
│  │  │  └─ ...                   │  └─ relationships
│  │  │                            │     └─ vector_Y (relation embeddings)
│  │  └─ metadata.json            │
│  │                               │
│  ├─ folder_2/
│  │  ├─ documents
│  │  │  └─ ...
│  │  └─ metadata.json
│  │
│  └─ folder_N/
│     └─ ...
```

## Mapping Details

### Session (folder_N) → PostgreSQL

```sql
-- PostgreSQL: sessions table
id          | created_at | updated_at | metadata
------------|------------|------------|----------
folder_1    | 2024-01-01 | 2024-01-05 | {"selected_doc": "doc_1", "status": "ready"}
folder_2    | 2024-01-02 | 2024-01-05 | {"selected_doc": "doc_2", "status": "ready"}
```

### Document (doc_ocr_1, doc_docstring_1) → PostgreSQL

```sql
-- PostgreSQL: documents table
id                  | session_id | filename            | doc_type  | pages | size   | extraction_time
--------------------|------------|---------------------|-----------|-------|--------|---------------
doc_ocr_1           | folder_1   | file.pdf            | ocr       | 5     | 45000  | 9.87
doc_docstring_1     | folder_1   | file2.pdf           | docstring | 4     | 50000  | 61.73
```

### Chunks (content dalam document) → PostgreSQL + Qdrant

```sql
-- PostgreSQL: chunks table (metadata & content)
id            | document_id    | session_id | content          | chunk_index | embedding_id
--------------|----------------|------------|------------------|-------------|-------------
a3f4b2c1d5... | doc_ocr_1      | folder_1   | "Menimbang: a..." | 0           | a3f4b2c1d5...
f8e7d6c5b4... | doc_ocr_1      | folder_1   | "b. bahwa..."     | 1           | f8e7d6c5b4...
...

-- Qdrant: chunks collection (vectors)
point_id | vector (1024-dim)        | payload
---------|--------------------------|----------------------------------------
12345678 | [0.234, 0.456, ..., 0.1] | {"chunk_id": "a3f4b2c1d5...", "doc_id": "doc_ocr_1"}
87654321 | [0.123, 0.789, ..., 0.9] | {"chunk_id": "f8e7d6c5b4...", "doc_id": "doc_ocr_1"}
```

## Query Examples - Visualisasi Folder Structure

### 1. List semua sessions (equivalent: ls rag_storage/pdf_sessions/)

```python
from app.db import SessionLocal, Session as SessionModel

db = SessionLocal()
sessions = db.query(SessionModel).all()

# Output:
# folder_1 (created: 2024-01-01, docs: 2)
# folder_2 (created: 2024-01-02, docs: 1)
# folder_3 (created: 2024-01-03, docs: 3)
```

### 2. List documents dalam session (equivalent: ls rag_storage/pdf_sessions/folder_1/documents/)

```python
from app.db import storage_manager

docs = storage_manager.get_session_documents('folder_1')

# Output:
# doc_ocr_1.pdf (4 pages, OCR, 9 chunks)
# doc_docstring_1.pdf (5 pages, DocString, 12 chunks)
```

### 3. List chunks dalam document (equivalent: cat rag_storage/pdf_sessions/folder_1/documents/doc_ocr_1/chunks.json)

```python
chunks = storage_manager.get_chunks_by_document('doc_ocr_1')

# Output:
# Chunk 0: "Menimbang: a. bahwa..." (342 chars)
# Chunk 1: "b. bahwa berdasarkan..." (456 chars)
# Chunk 2: "c. bahwa berdasarkan..." (389 chars)
# Total: 3 chunks
```

### 4. Get chunk detail dengan embedding vector

```python
chunk = chunks[0]
print(f"Content: {chunk.content}")
print(f"Size: {chunk.metadata['length']} chars")
print(f"Embedding ID: {chunk.embedding_id}")

# Retrieve vector dari Qdrant
from app.db import qdrant_manager
points = qdrant_manager.client.retrieve(
    collection_name='chunks',
    ids=[int(chunk.embedding_id[:16], 16)]
)
print(f"Vector: {points[0].vector}")
```

## Persistence & Structure

### Lama (File-based):
```
rag_storage/
├── pdf_sessions/
│  ├── folder_1/
│  │  ├── documents/
│  │  │  ├── doc_ocr_1/
│  │  │  │  └── chunks.json  ← chunks content
│  │  │  │  └── metadata.json
│  │  │  └── doc_docstring_1/
│  │  │     └── chunks.json
│  │  └── metadata.json
│  └── folder_2/
├── kv_store_text_chunks.json       ← all chunks
├── vdb_chunks.json                 ← all embeddings
├── kv_store_doc_status.json
└── ...
```

### Baru (Database):
```
rag_storage/
├── (metadata HANYA di database, bukan file)

PostgreSQL (on: localhost:5432)
├── sessions table
├── documents table
├── chunks table
└── embeddings table

Qdrant (on: localhost:6333)
├── chunks collection (vectors)
├── entities collection
└── relationships collection
```

## Keuntungan Struktur Baru

| Aspek | File-based | Database |
|-------|-----------|----------|
| **Scale** | 100K+ chunks = slow | 1M+ chunks = fast |
| **Query** | Load seluruh JSON | SQL indexes, quick filters |
| **Search** | Linear scan | Vector DB similarity |
| **Concurrent** | Lock issues | Database handles it |
| **Backup** | Manual copy folders | `pg_dump`, Qdrant snapshots |
| **Consistency** | Manual sync | ACID transactions |
| **Integration** | Custom parsing | Standard ORM (SQLAlchemy) |

## Backward Compatibility

Jika perlu convert existing data:

```python
# Load old file-based chunks
import json
with open('rag_storage/kv_store_text_chunks.json') as f:
    old_chunks = json.load(f)

# Migrate ke database
from app.db import storage_manager

for chunk_id, chunk_data in old_chunks.items():
    # Parse metadata dari chunk_data
    doc_id = chunk_data.get('doc_id', 'unknown')
    session_id = 'folder_1'  # Determine from path
    
    # Save to new database
    storage_manager.save_chunks(
        session_id=session_id,
        document_id=doc_id,
        chunks=[chunk_data['content']],
        doc_type='ocr'
    )
```

## Monitoring & Debugging

```python
# Check database state
from app.db import SessionLocal, Session, Document, Chunk

db = SessionLocal()

# Session stats
sessions = db.query(Session).all()
print(f"Total sessions: {len(sessions)}")

# Document stats
docs = db.query(Document).all()
print(f"Total documents: {len(docs)}")
doc_by_type = db.query(Document.doc_type, func.count(Document.id)).group_by(Document.doc_type).all()
print(f"Documents by type: {doc_by_type}")

# Chunk stats
chunks = db.query(Chunk).all()
print(f"Total chunks: {len(chunks)}")
total_size = sum(c.metadata['length'] for c in chunks if c.metadata)
print(f"Total size: {total_size} chars = {total_size / 1024:.2f} KB")

# Qdrant stats
from app.db import qdrant_manager
info = qdrant_manager.client.get_collection('chunks')
print(f"Qdrant vectors: {info.points_count}")
```

## Summary

Struktur **folder-like virtual** di database memberikan:
- ✅ Flexibility: Query dengan SQL atau vector search
- ✅ Organization: Sessions → Documents → Chunks (relational)
- ✅ Scalability: Database handles scale vs file system
- ✅ Performance: Indexes + vector similarity
- ✅ Reliability: ACID transactions + backups
