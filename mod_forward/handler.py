import httpx
import json
import os

async def stream_forward(payload, response_container: list):
    """
    流式转发函数（笔记本方案）
    
    参数：
    - payload: 原始请求体
    - response_container: 列表容器，用于存储完整回复
    
    流程：
    1. 从环境变量读取 LLM 服务配置
    2. 流式请求 LLM API
    3. 实时 yield 每个数据块给客户端
    4. 同时拼凑完整回复
    5. 流式结束时，将完整回复存入 response_container
    """
    
    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    full_response = []  # 本地拼凑完整回复
    
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60
        ) as response:
            async for chunk in response.aiter_text():
                if not chunk:
                    continue
                
                # ========== 实时转发给客户端 ==========
                yield chunk
                
                # ========== 后台拼凑完整回复 ==========
                for line in chunk.split('\n'):
                    if line.startswith('data: ') and line != 'data: [DONE]':
                        try:
                            data = json.loads(line[6:])
                            content = data['choices'][0]['delta'].get('content', '')
                            full_response.append(content)
                        except:
                            pass
    
    # ========== 流式结束：存入容器 ==========
    response_container.append(''.join(full_response))
