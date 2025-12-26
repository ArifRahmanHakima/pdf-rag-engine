#!/usr/bin/env python3
"""
Speed benchmark untuk PDF processing
"""
import os
import sys
import time
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from api.services.pdf_processor import process_pdf_async

async def benchmark_pdf_processing():
    """Test speed of PDF processing"""
    
    # Find a test PDF
    uploads_dir = Path("./uploads")
    pdf_files = list(uploads_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("❌ No PDF files found in ./uploads directory")
        return
    
    test_pdf = pdf_files[0]
    print(f"📄 Testing with: {test_pdf.name}")
    print(f"📊 File size: {test_pdf.stat().st_size / (1024*1024):.2f} MB")
    print("-" * 70)
    
    # Run benchmark
    start_time = time.time()
    
    try:
        doc_id, message = await process_pdf_async(str(test_pdf))
        elapsed = time.time() - start_time
        
        print(f"\n✅ SUCCESS!")
        print(f"📈 Total time: {elapsed:.2f} seconds")
        print(f"📄 Doc ID: {doc_id}")
        print(f"💬 Message: {message}")
        
        if elapsed <= 60:
            print(f"\n🚀 TARGET MET! ⚡ ({elapsed:.2f}s <= 60s)")
        else:
            print(f"\n⚠️  Target missed ({elapsed:.2f}s > 60s)")
            
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ ERROR after {elapsed:.2f}s: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(benchmark_pdf_processing())
