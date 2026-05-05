import httpx
import json
import os

async def stream_forward(payload):
    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    full_response = [] 

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", f"{base_url}/chat/completions", json=payload, headers=headers, timeout=60) as response:
            async for chunk in response.aiter_text():
                if not chunk: continue
                yield chunk 
                
                # 悄悄记录每一片叶子，准备拼成一棵树
                for line in chunk.split('\n'):
                    if line.startswith('data: ') and line != 'data: [DONE]':
                        try:
                            data = json.loads(line[6:])
                            content = data['choices'][0]['delta'].get('content', '')
                            full_response.append(content)
                        except: pass
            
    # 特殊标识：告诉 main.py 对话结束了，这是全文
    yield f"__FULL_TEXT__{''.join(full_response)}"
