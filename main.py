from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from mod_forward.handler import stream_forward

app = FastAPI()

@app.post("/v1/chat/completions")
async def main_gateway(request: Request):
    # 1. 接收原始请求
    body = await request.json()
    
    # 2. 调度逻辑（目前只有 A 模块：转发）
    # 以后你可以在这里加：body = mod_memory.apply(body)
    
    return StreamingResponse(
        stream_forward(body), 
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
