#!/usr/bin/env python3
"""
Quick setup script untuk persistent PDF feature
Menjalankan semua migrasi yang diperlukan
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.init_db import create_chat_messages_table
from api.services.init_documents_table import create_documents_table

def main():
    print("=" * 60)
    print("🚀 SETUP PERSISTENT PDF FEATURE")
    print("=" * 60)
    
    print("\n📦 Step 1: Creating chat_messages table...")
    try:
        create_chat_messages_table()
        print("✅ chat_messages table ready")
    except Exception as e:
        print(f"❌ Error creating chat_messages table: {e}")
        return False
    
    print("\n📦 Step 2: Creating documents table...")
    try:
        create_documents_table()
        print("✅ documents table ready")
    except Exception as e:
        print(f"❌ Error creating documents table: {e}")
        return False
    
    print("\n📁 Step 3: Checking uploads directory...")
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    pdfs_dir = os.path.join(upload_dir, "pdfs")
    
    try:
        os.makedirs(pdfs_dir, exist_ok=True)
        print(f"✅ Upload directory ready: {pdfs_dir}")
    except Exception as e:
        print(f"❌ Error creating upload directory: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ SETUP COMPLETE!")
    print("=" * 60)
    print("\n📚 Next steps:")
    print("1. Restart your server (docker-compose restart or manual)")
    print("2. Open browser to http://localhost:8000")
    print("3. Upload a PDF file")
    print("4. Refresh the page - PDF should reload automatically")
    print("\n📖 See PERSISTENT_PDF_SETUP.md for detailed documentation")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
