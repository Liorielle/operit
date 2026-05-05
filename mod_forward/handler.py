import httpx
import json
import os

async def stream_forward(payload):
    # 从环境变量读取配置
    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY")
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST", 
            f"{base_url}/chat/completions", 
            json=payload, 
            headers=headers,
            timeout=60
        ) as response:
            async for chunk in response.aiter_bytes():
                if chunk:
                    yield chunk
