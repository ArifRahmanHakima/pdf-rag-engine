# ============= AUTHENTICATION SERVICE =============
import os
import hashlib
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from api.services.db import get_postgres_conn

load_dotenv()

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "pdf-rag-engine-secret-key-2026")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", 24))
PASSWORD_SALT = os.getenv("PASSWORD_SALT", "pdf-rag-salt-2026")


def hash_password(password: str) -> str:
    """Hash password menggunakan SHA-256 dengan salt"""
    salted = PASSWORD_SALT + password
    return hashlib.sha256(salted.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """Verifikasi password dengan hash"""
    return hash_password(password) == hashed


def create_jwt_token(user_id: int, email: str, name: str) -> str:
    """Buat JWT token untuk user"""
    payload = {
        "user_id": user_id,
        "email": email,
        "name": name,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode dan validasi JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Ambil user berdasarkan email"""
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, email, password_hash, created_at FROM users WHERE email = %s",
                (email,)
            )
            result = cur.fetchone()
            return dict(result) if result else None
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Ambil user berdasarkan ID"""
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, email, created_at FROM users WHERE id = %s",
                (user_id,)
            )
            result = cur.fetchone()
            return dict(result) if result else None
    finally:
        conn.close()


def create_user(name: str, email: str, password: str) -> Dict[str, Any]:
    """Buat user baru"""
    password_hash = hash_password(password)
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (name, email, password_hash, created_at)
                VALUES (%s, %s, %s, NOW())
                RETURNING id, name, email, created_at
                """,
                (name, email, password_hash)
            )
            conn.commit()
            result = cur.fetchone()
            return dict(result) if result else None
    finally:
        conn.close()


def register_user(name: str, email: str, password: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Register user baru
    Returns: (user_data, error_message)
    """
    # Cek apakah email sudah terdaftar
    existing_user = get_user_by_email(email)
    if existing_user:
        return None, "Email sudah terdaftar"
    
    # Buat user baru
    user = create_user(name, email, password)
    if not user:
        return None, "Gagal membuat user"
    
    # Buat JWT token
    token = create_jwt_token(user["id"], user["email"], user["name"])
    
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"]
        }
    }, None


def login_user(email: str, password: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Login user
    Returns: (auth_data, error_message)
    """
    # Cari user berdasarkan email
    user = get_user_by_email(email)
    if not user:
        return None, "Email atau password salah"
    
    # Verifikasi password
    if not verify_password(password, user["password_hash"]):
        return None, "Email atau password salah"
    
    # Buat JWT token
    token = create_jwt_token(user["id"], user["email"], user["name"])
    
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"]
        }
    }, None


# ============= DOCUMENT ACCESS CONTROL =============

def create_document_record(user_id: int, doc_id: str, filename: str, status: str = "processing") -> Optional[Dict[str, Any]]:
    """Buat atau update record dokumen"""
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            # Gunakan INSERT ... ON CONFLICT untuk handle duplicate
            cur.execute(
                """
                INSERT INTO documents (doc_id, user_id, filename, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (doc_id) DO UPDATE
                SET user_id = %s, filename = %s, status = %s, updated_at = NOW()
                RETURNING id, doc_id, user_id, filename, status, created_at
                """,
                (doc_id, user_id, filename, status, user_id, filename, status)
            )
            conn.commit()
            result = cur.fetchone()
            return dict(result) if result else None
    finally:
        conn.close()


def update_document_status(doc_id: str, status: str) -> bool:
    """Update status dokumen"""
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documents 
                SET status = %s, updated_at = NOW()
                WHERE doc_id = %s
                """,
                (status, doc_id)
            )
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def get_document_by_id(doc_id: str) -> Optional[Dict[str, Any]]:
    """Ambil dokumen berdasarkan doc_id"""
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, doc_id, user_id, filename, status, created_at FROM documents WHERE doc_id = %s",
                (doc_id,)
            )
            result = cur.fetchone()
            return dict(result) if result else None
    finally:
        conn.close()


def get_user_documents(user_id: int) -> list:
    """Ambil semua dokumen milik user"""
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, doc_id, filename, status, created_at 
                FROM documents 
                WHERE user_id = %s 
                ORDER BY created_at DESC
                """,
                (user_id,)
            )
            results = cur.fetchall()
            return [dict(row) for row in results]
    finally:
        conn.close()


def verify_document_access(user_id: int, doc_id: str) -> bool:
    """Verifikasi apakah user memiliki akses ke dokumen"""
    doc = get_document_by_id(doc_id)
    if not doc:
        return False
    return doc["user_id"] == user_id


def delete_document_record(doc_id: str, user_id: int) -> bool:
    """Hapus record dokumen (hanya jika milik user)"""
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM documents WHERE doc_id = %s AND user_id = %s",
                (doc_id, user_id)
            )
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()
