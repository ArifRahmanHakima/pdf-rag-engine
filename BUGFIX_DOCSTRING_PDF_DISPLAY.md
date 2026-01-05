# Bug Fix: Docstring PDF Display Issue

## Problem
Ketika menggunakan **OCR biasa**, PDF tertampil dengan baik. Namun ketika menggunakan **Docstring extraction**, PDF tidak tertampil dengan error: `{"success":false,"error":"PDF not found"}`

## Root Cause
Perbedaan dalam pembuatan `doc_id` antara dua metode ekstraksi:

### OCR (Sebelumnya Bekerja)
```python
# api_handlers.py, line 47
doc_id = Path(file.filename).stem  # Contoh: "skqub262-2025-mark"
```

### Docstring (Bermasalah)
```python
# docstring_handlers.py, line 64 (LAMA)
doc_id = Path(file.filename).stem + "_docstring"  # Contoh: "skqub262-2025-mark_docstring"
```

### Masalah Querynya
Ketika frontend request PDF:
```python
# get_pdf_handler(), line 258-262
document = db_service.storage.db.query(Document).filter(
    Document.id == doc_id,  # Frontend kirim: "skqub262-2025-mark"
    Document.session_id == session_id
).first()  # Database punya: "skqub262-2025-mark_docstring" ❌ TIDAK MATCH
```

## Solution
Membuat `doc_id` konsisten antara dua metode, dan menggunakan field `doc_type` untuk membedakan:

### Perubahan 1: docstring_handlers.py
```python
# SEBELUM (line 64)
doc_id = Path(file.filename).stem + "_docstring"

# SESUDAH
doc_id = Path(file.filename).stem  # Konsisten dengan OCR
```

### Perubahan 2: document_service.py
```python
# SEBELUM (line 70)
extractor_type = "DocString" if docstring_api_key and "docstring" in doc_id else "OCR"
...
if docstring_api_key and "docstring" in doc_id:

# SESUDAH (line 70)
extractor_type = "DocString" if docstring_api_key else "OCR"
...
if docstring_api_key:
```

### Perubahan 3: document_service.py
```python
# SEBELUM (line 126)
doc_type="docstring" if (docstring_api_key and "docstring" in doc_id) else "ocr",

# SESUDAH
doc_type="docstring" if docstring_api_key else "ocr",
```

## Database Schema (No Change Needed)
Field `doc_type` di table `documents` tetap digunakan untuk membedakan:
```sql
doc_type = "docstring"  -- untuk Docstring extraction
doc_type = "ocr"        -- untuk OCR extraction
```

## Testing
Setelah perbaikan:

1. **Upload dengan Docstring**:
   - PDF disimpan dengan `doc_id` = "skqub262-2025-mark"
   - Stored dengan `doc_type` = "docstring"

2. **Retrieve PDF**:
   - Frontend request: `/api/pdf/{session_id}/skqub262-2025-mark`
   - Database query match: ✅ BERHASIL
   - PDF ditampilkan dengan baik

3. **Identifikasi Tipe Ekstraksi**:
   - Query field `doc_type` = "docstring" atau "ocr"

## Files Modified
1. `app/handlers/docstring_handlers.py` - Line 64
2. `app/services/document_service.py` - Lines 70, 81, 126

## Impact
- ✅ Docstring PDF sekarang dapat ditampilkan
- ✅ OCR PDF tetap berfungsi normal
- ✅ Konsistensi data antara OCR dan Docstring
- ✅ Tidak memerlukan perubahan frontend
- ✅ Tidak memerlukan perubahan database schema
