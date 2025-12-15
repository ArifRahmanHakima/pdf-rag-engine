import os
from dotenv import load_dotenv
from lightrag.llm.openai import openai_complete_if_cache

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
BASE_URL = os.getenv("GROQ_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")
VISION_MODEL = os.getenv("VISION_MODEL")
MAX_INPUT = int(os.getenv("MAX_INPUT_TOKENS", 800))
MAX_OUTPUT = int(os.getenv("MAX_OUTPUT_TOKENS", 512))

def truncate(text, limit=MAX_INPUT):
    return " ".join(text.split()[:limit]) + "..." if len(text.split()) > limit else text

def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
    prompt = truncate(prompt)
    return openai_complete_if_cache(
        LLM_MODEL,
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages[-5:],
        api_key=API_KEY,
        base_url=BASE_URL,
        max_tokens=MAX_OUTPUT,
        temperature=0.3,
        **kwargs,
    )

def vision_model_func(prompt, system_prompt=None, history_messages=[], image_data=None, messages=None, **kwargs):
    prompt = truncate(prompt)
    try:
        if messages:
            return openai_complete_if_cache(
                VISION_MODEL, "", messages=messages,
                api_key=API_KEY, base_url=BASE_URL,
                max_tokens=MAX_OUTPUT, **kwargs
            )
        elif image_data:
            return openai_complete_if_cache(
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
            return llm_model_func(prompt, system_prompt, history_messages, **kwargs)
    except Exception as e:
        print(f"[Vision fallback] {e}")
        return llm_model_func(prompt, system_prompt, history_messages, **kwargs)
