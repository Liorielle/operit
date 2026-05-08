import os
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from mod_auth.checker import auth_check
from mod_parse.parser import parse_request
from mod_forward.handler import stream_forward
from mod_database.writer import save_user_message, save_ai_reply
# 新增导入
from mod_calendar.injector import get_calendar_context


app = FastAPI()


@app.get("/v1/models")
async def list_models():
    """返回支持的模型列表"""
    models = [
        {"id": "gpt-3.5-turbo", "object": "model", "created": 1677610602, "owned_by": "system"},
        {"id": "gpt-4o", "object": "model", "created": 1677610602, "owned_by": "system"}
    ]
    return JSONResponse(content={"object": "list", "data": models})


@app.post("/v1/chat/completions")
async def main_gateway(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str = Header(None),
    x_session_id: str = Header("default")
):
    """
    核心网关接口：A → B → C → C1 → D → E
    A: 鉴权
    B: 解析请求
    C: 保存用户消息
    C1: 日历摘要注入 ← 新增
    D: 流式转发
    E: 保存 AI 回复
    """
    
    # ========== A：鉴权 ==========
    await auth_check(authorization)
    
    # ========== B：解析请求 ==========
    parsed_data = await parse_request(request, x_session_id)
    
    # ========== C：保存用户消息 ==========
    background_tasks.add_task(save_user_message, parsed_data)
    
    # ========== C1：日历摘要注入 ========== ← 新增这3行
    calendar_context = await get_calendar_context(parsed_data, x_session_id)
    if calendar_context:
        parsed_data["calendar_context"] = calendar_context
    
    # ========== D + E：流式转发 + 保存 AI 回复 ==========
    ai_reply_box = []
    
    async def wrapper():
        async for chunk in stream_forward(parsed_data, ai_reply_box):
            yield chunk
        
        # E：保存 AI 回复
        background_tasks.add_task(save_ai_reply, parsed_data, ai_reply_box)
    
    return StreamingResponse(wrapper(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
