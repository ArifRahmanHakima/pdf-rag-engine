"""
DocString API Service - Handles PDF extraction via Nanonets DocString API
"""

import httpx
import asyncio
from typing import Optional
from pathlib import Path


DOCSTRING_BASE_URL = "https://extraction-api.nanonets.com/api/v1"


async def extract_with_docstring_sync(
    file_path: str, 
    api_key: str,
    output_format: str = "markdown"
) -> str:
    """
    Synchronous extraction untuk PDFs ≤5 halaman
    
    Uses /api/v1/extract/sync endpoint untuk immediate results
    
    Args:
        file_path: Path ke PDF file
        api_key: DocString API key
        output_format: Output format (markdown, html, json, csv)
    
    Returns:
        Extracted content as string (markdown format)
    
    Raises:
        Exception: Jika API request gagal
    """
    
    if not api_key:
        raise ValueError("DocString API key is not configured. Please set DOCSTRING_API_KEY in .env")
    
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")
    
    # Check file size (API limit is usually 50MB)
    file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
    print(f"[*] DocString sync extraction: {file_path_obj.name} ({file_size_mb:.2f} MB)", flush=True)
    
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            with open(file_path, 'rb') as f:
                files = {
                    'file': (file_path_obj.name, f, 'application/pdf')
                }
                data = {
                    'output_format': output_format
                }
                headers = {
                    'Authorization': f'Bearer {api_key}'
                }
                
                print(f"[*] Calling DocString API (sync endpoint)...", flush=True)
                
                response = await client.post(
                    f"{DOCSTRING_BASE_URL}/extract/sync",
                    files=files,
                    data=data,
                    headers=headers
                )
                
                print(f"[*] DocString API response: {response.status_code}", flush=True)
                
                if response.status_code == 200:
                    result = response.json()
                    # Extract content from nested structure: result.result.markdown.content
                    content = result.get('result', {}).get('markdown', {}).get('content', '')
                    # Fallback to other possible keys
                    if not content:
                        content = result.get('markdown', {}).get('content', '') or result.get('content', '') or ''
                    if not content:
                        print(f"[!] Empty response from DocString: {result}", flush=True)
                        raise Exception(f"DocString API returned empty content. Response: {result}")
                    print(f"[✓] DocString sync extraction complete ({len(content)} chars)", flush=True)
                    return content
                elif response.status_code == 400:
                    # File exceeds size limit - fallback to async extraction
                    error_msg = response.json().get('detail', response.text)
                    print(f"[!] Sync extraction failed (400 Bad Request): {error_msg}", flush=True)
                    print(f"[*] Falling back to async extraction...", flush=True)
                    # Return async extraction coroutine instead
                    return await extract_with_docstring_async(file_path, api_key)
                elif response.status_code == 401:
                    error_msg = "Invalid or expired API key"
                    print(f"[!] DocString API error (401 Unauthorized): {error_msg}", flush=True)
                    raise Exception(f"DocString API authentication failed. Please check DOCSTRING_API_KEY")
                elif response.status_code == 403:
                    error_msg = "API key doesn't have permission"
                    print(f"[!] DocString API error (403 Forbidden): {error_msg}", flush=True)
                    raise Exception(f"DocString API permission denied. Please check your plan limits")
                else:
                    error_msg = response.text
                    print(f"[!] DocString API error: {response.status_code} - {error_msg}", flush=True)
                    raise Exception(f"DocString API error: {response.status_code} - {error_msg}")
    
    except httpx.TimeoutException as te:
        print(f"[!] DocString API timeout: {te}", flush=True)
        raise Exception(f"DocString API request timed out after 90 seconds. File may be too large.")
    except httpx.RequestError as re:
        print(f"[!] DocString API connection error: {re}", flush=True)
        raise Exception(f"Failed to connect to DocString API: {str(re)}")
    except Exception as e:
        print(f"[!] DocString extraction error: {e}", flush=True)
        raise


async def extract_with_docstring_async(
    file_path: str,
    api_key: str,
    output_format: str = "markdown",
    max_polls: int = 300,
    poll_interval: int = 1
) -> str:
    """
    Asynchronous extraction untuk PDFs >5 halaman dengan polling
    
    Uses /api/v1/extract/async untuk submit job, kemudian poll hasil
    
    Args:
        file_path: Path ke PDF file
        api_key: DocString API key
        output_format: Output format (markdown, html, json, csv)
        max_polls: Max polling attempts (300 = 5 min dengan 1s interval)
        poll_interval: Interval antar polling (seconds)
    
    Returns:
        Extracted content as string (markdown format)
    
    Raises:
        TimeoutError: Jika extraction timeout
        Exception: Jika job failed atau API error
    """
    
    async with httpx.AsyncClient(timeout=300) as client:
        # Step 1: Submit job
        with open(file_path, 'rb') as f:
            files = {
                'file': (Path(file_path).name, f, 'application/pdf')
            }
            data = {
                'output_format': output_format
            }
            headers = {
                'Authorization': f'Bearer {api_key}'
            }
            
            print(f"[*] DocString async submission (>5 pages): {Path(file_path).name}", flush=True)
            
            submit_response = await client.post(
                f"{DOCSTRING_BASE_URL}/extract/async",
                files=files,
                data=data,
                headers=headers
            )
            
            if submit_response.status_code != 202:
                error_msg = submit_response.text
                print(f"[!] Failed to submit async job: {error_msg}", flush=True)
                raise Exception(f"Failed to submit async job: {error_msg}")
            
            job_data = submit_response.json()
            record_id = job_data.get('record_id')
            print(f"[✓] Job submitted with ID: {record_id}", flush=True)
        
        # Step 2: Poll untuk hasil
        for attempt in range(max_polls):
            await asyncio.sleep(poll_interval)
            
            check_response = await client.get(
                f"{DOCSTRING_BASE_URL}/extract/results/{record_id}",
                headers=headers
            )
            
            if check_response.status_code == 200:
                result_data = check_response.json()
                status = result_data.get('status')
                
                if status == 'completed':
                    # Extract content from nested structure: result.result.markdown.content (polling response)
                    content = result_data.get('result', {}).get('markdown', {}).get('content', '')
                    # Fallback: result.markdown.content
                    if not content:
                        content = result_data.get('markdown', {}).get('content', '')
                    # Last resort: direct content key
                    if not content:
                        content = result_data.get('content', '')
                    
                    if not content:
                        print(f"[!] No content in completed result: {result_data}", flush=True)
                        raise Exception("DocString API returned empty content in completed job")
                    
                    print(f"[✓] DocString async extraction complete ({len(content)} chars)", flush=True)
                    return content
                elif status == 'failed':
                    error = result_data.get('error', 'Unknown error')
                    print(f"[!] Job failed: {error}", flush=True)
                    raise Exception(f"DocString job failed: {error}")
                # else: still processing, continue polling
            
            # Log setiap 30 detik
            if attempt % 30 == 0 and attempt > 0:
                print(f"[*] Waiting for DocString processing... ({attempt}s elapsed)", flush=True)
        
        # Timeout
        print(f"[!] DocString extraction timeout (5 min)", flush=True)
        raise TimeoutError("DocString extraction timeout (5 min)")


def extract_with_docstring_wrapper(
    file_path: str,
    api_key: str,
    use_ocr: bool = False
) -> str:
    """
    Wrapper untuk compatibility dengan existing extract_text_func signature
    
    Auto-select antara sync dan async berdasarkan file size
    CRITICAL: Ini dipanggil dari async context (background task), 
    jadi kita cukup return coroutine yang akan di-await oleh caller
    
    Args:
        file_path: Path ke PDF file
        api_key: DocString API key
        use_ocr: Ignored (untuk backward compatibility)
    
    Returns:
        Extracted text dalam format Markdown (atau coroutine jika async)
    """
    
    # Estimate jumlah halaman dari file size
    # Rough estimate: ~1.5MB per 5 halaman
    file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
    estimated_pages = file_size_mb / 0.3  # ~0.3MB per page average
    
    print(f"[*] File size: {file_size_mb:.2f}MB, Estimated pages: {estimated_pages:.0f}", flush=True)
    
    if estimated_pages > 5:
        # Gunakan async extraction untuk file besar
        print(f"[*] Using async extraction (file > 5 pages)", flush=True)
        return extract_with_docstring_async(file_path, api_key)
    else:
        # Gunakan sync extraction untuk file kecil
        print(f"[*] Using sync extraction (file ≤ 5 pages)", flush=True)
        return extract_with_docstring_sync(file_path, api_key)
