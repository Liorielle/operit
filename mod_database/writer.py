import os
import httpx
from datetime import datetime, timedelta

async def save_chat_to_db(role, content, session_id, model_name, nickname):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    # 核心：手动计算北京时间 (UTC+8)
    beijing_time = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    data = {
        "role": role,
        "content": content,
        "session_id": session_id,
        "model_name": model_name,
        "nickname": nickname,
        "created_at_beijing": beijing_time 
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # 发送请求到 Supabase 的 Restful API 接口
            await client.post(f"{url}/rest/v1/chat_logs", json=data, headers=headers)
        except Exception as e:
            print(f"写入数据库失败，但不影响聊天流: {e}")
