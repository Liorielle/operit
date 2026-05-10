import os
import asyncio
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from contextlib import asynccontextmanager

# ========== 核心模块导入 ==========
from mod_auth.checker import auth_check
from mod_parse.parser import parse_request
from mod_forward.handler import stream_forward
from mod_database.writer import save_user_message, save_ai_reply

# ========== 新增模块导入 ==========
from mod_coldstart.injector import get_cold_start_context
from kiwi_daily_digest import (
    setup_scheduler,
    shutdown_scheduler,
)

# ========== 应用生命周期管理 ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用启动和关闭的生命周期管理
    """
    # 启动：初始化每日整理调度器
    print("🚀 应用启动中...")
    await setup_scheduler()
    print("✅ 应用启动完成，每日整理调度器已启动（东八区 0:05 触发）")
    
    yield
    
    # 关闭：优雅停止调度器
    print("🛑 应用关闭中...")
    await shutdown_scheduler()
    print("✅ 应用关闭完成")

app = FastAPI(lifespan=lifespan)

# ========== A：模型列表接口 ==========
@app.get("/v1/models")
async def list_models():
    """返回支持的模型列表"""
    models = [
        {"id": "gpt-3.5-turbo", "object": "model", "created": 1677610602, "owned_by": "system"},
        {"id": "gpt-4o", "object": "model", "created": 1677610602, "owned_by": "system"}
    ]
    return JSONResponse(content={"object": "list", "data": models})

# ========== B：核心网关接口 ==========
@app.post("/v1/chat/completions")
async def main_gateway(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str = Header(None),
    x_session_id: str = Header("default")
):
    """
    核心网关接口：A → B → C → D → E → F
    
    A: 冷启动注入（从前一个会话恢复语气）
    B: 鉴权
    C: 解析请求
    D: 保存用户消息
    E: 流式转发
    F: 保存 AI 回复
    """
    
    # ========== A：冷启动注入 ==========
    cold_start_context = await get_cold_start_context(x_session_id)
    if cold_start_context:
        print(f"❄️ 冷启动：从前一个会话恢复语气")
    
    # ========== B：鉴权 ==========
    await auth_check(authorization)
    
    # ========== C：解析请求 ==========
    parsed_data = await parse_request(request, x_session_id)
    
    # 如果有冷启动上下文，注入到系统提示词中
    if cold_start_context:
        if "messages" in parsed_data:
            # 在系统消息前插入冷启动上下文
            for msg in parsed_data["messages"]:
                if msg.get("role") == "system":
                    msg["content"] = cold_start_context + "\n\n" + msg["content"]
                    break
    
    # ========== D：保存用户消息 ==========
    background_tasks.add_task(save_user_message, parsed_data)
    
    # ========== E + F：流式转发 + 保存 AI 回复 ==========
    ai_reply_box = []
    
    async def wrapper():
        async for chunk in stream_forward(parsed_data, ai_reply_box):
            yield chunk
        
        # F：保存 AI 回复
        background_tasks.add_task(save_ai_reply, parsed_data, ai_reply_box)
    
    return StreamingResponse(wrapper(), media_type="text/event-stream")

# ========== 健康检查接口 ==========
@app.get("/health")
async def health_check():
    """健康检查接口"""
    return JSONResponse(content={"status": "ok", "message": "Liorhys Gateway is running"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
