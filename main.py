import os
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from mod_forward.handler import stream_forward
from mod_database.writer import save_chat_to_db

app = FastAPI()

# --- 逻辑 A：模型列表接口（保持原样，让前端开心） ---
@app.get("/v1/models")
async def list_models():
    models = [
        {"id": "gpt-3.5-turbo", "object": "model", "created": 1677610602, "owned_by": "system"},
        {"id": "gpt-4o", "object": "model", "created": 1677610602, "owned_by": "system"}
    ]
    return JSONResponse(content={"object": "list", "data": models})

# --- 逻辑 B：核心网关接口（新增异步存储和 Header 抓取） ---
@app.post("/v1/chat/completions")
async def main_gateway(
    request: Request, 
    background_tasks: BackgroundTasks, # 启动异步任务的工具
    authorization: str = Header(None),
    x_session_id: str = Header("default") # 抓取你设置的窗口 ID
):
    # 1. 鉴权逻辑（保持原样）
    gateway_key = os.getenv("GATEWAY_KEY")
    if authorization != f"Bearer {gateway_key}":
        raise HTTPException(status_code=401, detail="网关密钥错误")

    # 2. 解析请求体
    body = await request.json()
    user_msg = body['messages'][-1]['content'] # 提取用户刚发的那句话
    model_name = body.get('model', 'unknown')

    # 3. 【异步动作一】：顺手把用户消息存入 Supabase (调用模块 B)
    # 使用 background_tasks 确保存库动作不影响回复速度
    background_tasks.add_task(save_chat_to_db, "user", user_msg, x_session_id, model_name, "我")

    # 4. 【流式转发逻辑】：调用转发并截获全文 (调用模块 A)
    async def wrapper():
        full_ai_text = ""
        async for chunk in stream_forward(body):
            # 检查是否是 handler 传回的结束信号
            if chunk.startswith("__FULL_TEXT__"):
                full_ai_text = chunk.replace("__FULL_TEXT__", "")
            else:
                yield chunk # 实时把字吐给用户
        
        # 5. 【异步动作二】：AI 说完了，把拼好的全文存库
        if full_ai_text:
            background_tasks.add_task(save_chat_to_db, "assistant", full_ai_text, x_session_id, model_name, "Liorielle")

    return StreamingResponse(wrapper(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
