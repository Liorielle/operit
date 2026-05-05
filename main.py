import os
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import StreamingResponse, JSONResponse
from mod_forward.handler import stream_forward

app = FastAPI()

# --- 逻辑 A：模型列表接口（为了让 Operit 这种软件开心） ---
@app.get("/v1/models")
async def list_models():
    # 这里我们随便返回几个主流模型，骗过前端的检查
    models = [
        {"id": "gpt-3.5-turbo", "object": "model", "created": 1677610602, "owned_by": "system"},
        {"id": "gpt-4o", "object": "model", "created": 1677610602, "owned_by": "system"}
    ]
    return JSONResponse(content={"object": "list", "data": models})

# --- 逻辑 B：聊天转发接口（带鉴权锁） ---
@app.post("/v1/chat/completions")
async def main_gateway(request: Request, authorization: str = Header(None)):
    # 1. 鉴权锁逻辑（博主说的防盗刷）
    # 以后在 Operit 的 API Key 处填你自己设的这个 GATEWAY_KEY
    gateway_key = os.getenv("GATEWAY_KEY")
    if authorization != f"Bearer {gateway_key}":
        raise HTTPException(status_code=401, detail="网关密钥错误，请检查你的设置")

    # 2. 接收请求并转发
    body = await request.json()
    return StreamingResponse(
        stream_forward(body), 
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
