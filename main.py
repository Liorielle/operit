import os
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from mod_forward.handler import stream_forward
from mod_database.writer import save_chat_to_db

app = FastAPI()

# --- 接口 A：模型列表 ---
@app.get("/v1/models")
async def list_models():
    """返回支持的模型列表"""
    models = [
        {"id": "gpt-3.5-turbo", "object": "model", "created": 1677610602, "owned_by": "system"},
        {"id": "gpt-4o", "object": "model", "created": 1677610602, "owned_by": "system"}
    ]
    return JSONResponse(content={"object": "list", "data": models})

# --- 接口 B：核心网关（深度解耦版本） ---
@app.post("/v1/chat/completions")
async def main_gateway(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str = Header(None),
    x_session_id: str = Header("default")
):
    """
    核心网关接口：
    1. 鉴权检查
    2. 异步存储用户消息
    3. 流式转发 LLM 请求
    4. 异步存储 AI 回复
    """
    
    # ========== 第一步：鉴权 ==========
    gateway_key = os.getenv("GATEWAY_KEY")
    if authorization != f"Bearer {gateway_key}":
        raise HTTPException(status_code=401, detail="网关密钥错误")
    
    # ========== 第二步：解析请求 ==========
    body = await request.json()
    user_msg = body['messages'][-1]['content']
    model_name = body.get('model', 'unknown')
    
    # ========== 第三步：异步存储用户消息 ==========
    background_tasks.add_task(
        save_chat_to_db,
        role="user",
        content=user_msg,
        session_id=x_session_id,
        model_name=model_name,
        nickname="我"
    )
    
    # ========== 第四步：准备 AI 回复容器 ==========
    ai_reply_box = []  # 笔记本方案：用列表存储完整回复
    
    # ========== 第五步：流式转发逻辑 ==========
    async def wrapper():
        """
        包装器：
        1. 调用 handler 进行流式转发
        2. 实时 yield 给客户端
        3. handler 会自动填充 ai_reply_box
        """
        async for chunk in stream_forward(body, ai_reply_box):
            yield chunk
        
        # ========== 第六步：异步存储 AI 回复 ==========
        # 流式结束后，从容器中取出完整回复
        if ai_reply_box:
            full_ai_text = ai_reply_box[0]
            background_tasks.add_task(
                save_chat_to_db,
                role="assistant",
                content=full_ai_text,
                session_id=x_session_id,
                model_name=model_name,
                nickname="Liorielle"
            )
    
    return StreamingResponse(wrapper(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
