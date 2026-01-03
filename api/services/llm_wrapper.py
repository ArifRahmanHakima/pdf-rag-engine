import os
import asyncio
from dotenv import load_dotenv
import httpx

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")
VISION_MODEL = os.getenv("VISION_MODEL")
MAX_INPUT = int(os.getenv("MAX_INPUT_TOKENS", 800))
MAX_OUTPUT = int(os.getenv("MAX_OUTPUT_TOKENS", 512))

 # ========================================
 # KONFIGURASI ULANG COBA (RETRY) YANG DIOPTIMALKAN UNTUK GROQ
 # ========================================
class RetryConfig:
    """Optimized for Groq's rate limits"""
    MAX_RETRIES = 3  # ← REDUCED from 5
    INITIAL_DELAY = 2
    MAX_DELAY = 30
    TIMEOUT = 90.0
    
    # Pengaturan batas laju (rate limit) untuk Groq
    RATE_LIMIT_DELAY = 5  # ← INCREASED from 3
    RATE_LIMIT_MAX_DELAY = 60
    
    @classmethod
    def get_backoff_delay(cls, attempt: int, is_rate_limit: bool = False) -> float:
        """Hitung jeda mundur eksponensial"""
        if is_rate_limit:
            delay = cls.RATE_LIMIT_DELAY * (2 ** attempt)
            return min(delay, cls.RATE_LIMIT_MAX_DELAY)
        else:
            delay = cls.INITIAL_DELAY * (2 ** attempt)
            return min(delay, cls.MAX_DELAY)

def truncate(text, limit=MAX_INPUT):
    return " ".join(text.split()[:limit]) + "..." if len(text.split()) > limit else text

def _is_json_serializable(value):
    """Cek apakah nilai bisa diserialisasi ke JSON"""
    import json
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False

 # Parameter kwargs yang diizinkan untuk OpenAI API
ALLOWED_KWARGS = {
    'temperature', 'top_p', 'n', 'stream', 'stop', 'max_tokens',
    'presence_penalty', 'frequency_penalty', 'logit_bias', 'user',
    'response_format', 'seed', 'tools', 'tool_choice',
    'reasoning_effort', 'max_completion_tokens'
}

 # Rate limiter global - DITINGKATKAN untuk Groq
_rate_limit_lock = asyncio.Lock()
_last_request_time = 0
_min_request_interval = 1.5  # ← INCREASED from 0.5 to 1.5 seconds

async def _wait_for_rate_limit():
    """Rate limiter global untuk mencegah overload ke Groq API"""
    global _last_request_time
    
    async with _rate_limit_lock:
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - _last_request_time
        
        if time_since_last < _min_request_interval:
            wait_time = _min_request_interval - time_since_last
            await asyncio.sleep(wait_time)
        
        _last_request_time = asyncio.get_event_loop().time()

async def openai_complete(
    model: str,
    prompt: str,
    system_prompt: str = None,
    history_messages: list = None,  # ← FIXED: was =[] (mutable default bug)
    api_key: str = None,
    base_url: str = None,
    messages: list = None,
    **kwargs
) -> str:
    """
    Komplet OpenAI yang dioptimalkan untuk Groq
    """
    if messages is None:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history_messages:
            messages.extend(history_messages)
        if prompt:
            messages.append({"role": "user", "content": prompt})
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # Filter kwargs
    filtered_kwargs = {
        k: v for k, v in kwargs.items() 
        if k in ALLOWED_KWARGS and v is not None and _is_json_serializable(v)
    }
    
    payload = {
        "model": model,
        "messages": messages,
        **filtered_kwargs
    }
    
    # Wait for global rate limit
    await _wait_for_rate_limit()
    
    # Logika ulang coba (retry) dioptimalkan untuk Groq
    async with httpx.AsyncClient(timeout=RetryConfig.TIMEOUT) as client:
        last_error = None
        consecutive_rate_limits = 0
        
        for attempt in range(RetryConfig.MAX_RETRIES):
            try:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                
                # Reset rate limit counter on success
                consecutive_rate_limits = 0
                
                return data["choices"][0]["message"]["content"]
                
            except httpx.HTTPStatusError as e:
                last_error = e
                
                # Penanganan rate limit (429)
                if e.response.status_code == 429:
                    consecutive_rate_limits += 1
                    
                    if attempt < RetryConfig.MAX_RETRIES - 1:
                        wait_time = RetryConfig.get_backoff_delay(consecutive_rate_limits - 1, is_rate_limit=True)
                        
                        # Coba parsing header retry-after
                        retry_after = e.response.headers.get('retry-after')
                        if retry_after:
                            try:
                                wait_time = max(wait_time, float(retry_after))
                            except ValueError:
                                pass
                        
                        print(f"⚠️ Rate limit (429) - Waiting {wait_time:.1f}s [{attempt + 1}/{RetryConfig.MAX_RETRIES}]")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ Rate limit exceeded after {RetryConfig.MAX_RETRIES} retries")
                        raise
                
                # Penanganan error server (5xx)
                elif e.response.status_code >= 500:
                    if attempt < RetryConfig.MAX_RETRIES - 1:
                        wait_time = RetryConfig.get_backoff_delay(attempt)
                        print(f"⚠️ Server error ({e.response.status_code}) - Waiting {wait_time:.1f}s [{attempt + 1}/{RetryConfig.MAX_RETRIES}]")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise
                
                # Tidak melakukan ulang coba pada error klien (4xx kecuali 429)
                else:
                    print(f"❌ Client error ({e.response.status_code})")
                    raise
                
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                
                if attempt < RetryConfig.MAX_RETRIES - 1:
                    wait_time = RetryConfig.get_backoff_delay(attempt)
                    print(f"⚠️ Connection/timeout - Waiting {wait_time:.1f}s [{attempt + 1}/{RetryConfig.MAX_RETRIES}]")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise
        
                # Semua ulang coba gagal
        if last_error:
            raise last_error
        raise Exception("Max retries exceeded")


async def llm_model_func(prompt, system_prompt=None, history_messages=None, **kwargs):  # ← FIXED
    """Komplet LLM yang dioptimalkan untuk Groq"""
    prompt = truncate(prompt)
    
    # Cek apakah menggunakan model reasoning
    is_reasoning_model = "gpt-oss" in LLM_MODEL or "o1" in LLM_MODEL or "reasoning" in LLM_MODEL.lower()
    
    extra_params = {}
    if is_reasoning_model:
        extra_params = {
            "reasoning_effort": "medium",
            "max_completion_tokens": MAX_OUTPUT * 2,
        }
    else:
        extra_params = {
            "max_tokens": MAX_OUTPUT,
            "temperature": 0.3,
        }
    
    # Penanganan jika history_messages None
    if history_messages:
        history_messages = history_messages[-5:]
    else:
        history_messages = []
    
    return await openai_complete(
        LLM_MODEL,
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        api_key=API_KEY,
        base_url=BASE_URL,
        **extra_params,
        **kwargs,
    )

async def vision_model_func(prompt, system_prompt=None, history_messages=None, image_data=None, messages=None, **kwargs):  # ← FIXED
    """Komplet model vision dengan fallback"""
    prompt = truncate(prompt)
    
    # Penanganan jika history_messages None
    if history_messages is None:
        history_messages = []
    
    try:
        if messages:
            return await openai_complete(
                VISION_MODEL, "", messages=messages,
                api_key=API_KEY, base_url=BASE_URL,
                max_tokens=MAX_OUTPUT, **kwargs
            )
        elif image_data:
            return await openai_complete(
                VISION_MODEL, "", messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                    ]
                }],
                api_key=API_KEY, base_url=BASE_URL,
                max_tokens=MAX_OUTPUT, **kwargs
            )
        else:
            return await llm_model_func(prompt, system_prompt, history_messages, **kwargs)
    except Exception as e:
        print(f"[Fallback Vision] {e}")
        return await llm_model_func(prompt, system_prompt, history_messages, **kwargs)

 # ========================================
 # PROSES BATCH DENGAN RATE LIMIT KETAT
 # ========================================
async def batch_llm_requests(prompts: list, max_concurrent: int = 2, **kwargs):
    """
    Proses banyak permintaan dengan rate limit ketat untuk Groq
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_semaphore(prompt):  # Proses dengan pembatasan concurrency
        async with semaphore:
            try:
                return await llm_model_func(prompt, **kwargs)
            except Exception as e:
                print(f"Batch request error: {e}")
                return None
    
    tasks = [process_with_semaphore(prompt) for prompt in prompts]
    return await asyncio.gather(*tasks, return_exceptions=True)