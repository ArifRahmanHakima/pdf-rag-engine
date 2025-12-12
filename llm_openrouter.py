import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

async def llm_model_func_openrouter(prompt, sys_prompt=None, **kwargs):
    """LLM - OpenRouter (model dari .env)"""
    try:
        api_key = os.getenv("OPENROUTER_API_KEY")
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")
        
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        
        messages = []
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=2000,  # Increase to allow complete responses for multi-point answers
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"[LLM Error: {str(e)[:100]}]"
