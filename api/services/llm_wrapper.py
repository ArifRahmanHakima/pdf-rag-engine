import os
import asyncio
from dotenv import load_dotenv
import httpx

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")  # ← Pakai ini
BASE_URL = os.getenv("OPENROUTER_BASE_URL")  # ← Pakai ini
LLM_MODEL = os.getenv("LLM_MODEL")
VISION_MODEL = os.getenv("VISION_MODEL")
MAX_INPUT = int(os.getenv("MAX_INPUT_TOKENS", 800))
MAX_OUTPUT = int(os.getenv("MAX_OUTPUT_TOKENS", 512))

def truncate(text, limit=MAX_INPUT):
    return " ".join(text.split()[:limit]) + "..." if len(text.split()) > limit else text


def _is_json_serializable(value):
    """Check if a value is JSON serializable"""
    import json
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False

# Allowed kwargs for OpenAI API (including reasoning models)
ALLOWED_KWARGS = {
    'temperature', 'top_p', 'n', 'stream', 'stop', 'max_tokens',
    'presence_penalty', 'frequency_penalty', 'logit_bias', 'user',
    'response_format', 'seed', 'tools', 'tool_choice',
    'reasoning_effort', 'max_completion_tokens'  # For reasoning models like gpt-oss-120b
}

async def openai_complete(
    model: str,
    prompt: str,
    system_prompt: str = None,
    history_messages: list = None,
    api_key: str = None,
    base_url: str = None,
    messages: list = None,
    **kwargs
) -> str:
    """Simple OpenAI-compatible completion function"""
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
    
    # Filter kwargs: only include allowed keys that are JSON serializable
    filtered_kwargs = {
        k: v for k, v in kwargs.items() 
        if k in ALLOWED_KWARGS and v is not None and _is_json_serializable(v)
    }
    
    payload = {
        "model": model,
        "messages": messages,
        **filtered_kwargs
    }
    
    # Retry logic untuk rate limit (429)
    max_retries = 3
    retry_delay = 2  # seconds
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        for attempt in range(max_retries):
            try:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    # Rate limit - tunggu dan retry
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    print(f"⚠️ Rate limit hit, waiting {wait_time}s before retry ({attempt + 1}/{max_retries})...")
                    await asyncio.sleep(wait_time)
                    continue
                raise
        
        # Fallback jika semua retry gagal
        raise Exception("Max retries exceeded for API request")


async def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
    prompt = truncate(prompt)
    
    # Check if using reasoning model (gpt-oss-120b)
    is_reasoning_model = "gpt-oss" in LLM_MODEL or "o1" in LLM_MODEL or "reasoning" in LLM_MODEL.lower()
    
    extra_params = {}
    if is_reasoning_model:
        extra_params = {
            "reasoning_effort": "medium",
            "max_completion_tokens": MAX_OUTPUT * 2,  # Reasoning models need more tokens
        }
    else:
        extra_params = {
            "max_tokens": MAX_OUTPUT,
            "temperature": 0.3,
        }
    
    return await openai_complete(
        LLM_MODEL,
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages[-5:],
        api_key=API_KEY,
        base_url=BASE_URL,
        **extra_params,
        **kwargs,
    )

async def vision_model_func(prompt, system_prompt=None, history_messages=[], image_data=None, messages=None, **kwargs):
    prompt = truncate(prompt)
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
        print(f"[Vision fallback] {e}")
        return await llm_model_func(prompt, system_prompt, history_messages, **kwargs)
