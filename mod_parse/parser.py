from fastapi import Request

async def parse_request(request: Request, session_id: str):
    """
    请求解析逻辑
    
    参数：
    - request: FastAPI Request 对象
    - session_id: 来自 X-Session-Id header 的值
    
    返回：
    {
        "body": {...},           # 原始请求体
        "user_msg": "...",       # 用户最后一条消息
        "model_name": "...",     # 使用的模型名称
        "session_id": "..."      # 会话 ID
    }
    """
    body = await request.json()
    user_msg = body['messages'][-1]['content']
    model_name = body.get('model', 'unknown')
    
    return {
        "body": body,
        "user_msg": user_msg,
        "model_name": model_name,
        "session_id": session_id
    }
