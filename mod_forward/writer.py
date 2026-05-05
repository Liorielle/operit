import os
import httpx
from datetime import datetime, timedelta

async def save_chat_to_db(role, content, session_id, model_name, nickname):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    # 算时区：在代码里手动计算北京时间
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
        "created_at_beijing": beijing_time  # 存入我们在 SQL 里设好的这一列
    }
    
    async with httpx.AsyncClient() as client:
        await client.post(f"{url}/rest/v1/chat_logs", json=data, headers=headers)
