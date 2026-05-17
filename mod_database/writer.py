import os
import httpx
from datetime import datetime, timedelta

async def save_user_message(parsed_data):
    """
    保存用户消息

    参数：
    - parsed_data: 解析后的请求数据（来自 mod_parse/parser.py）
    """
    await save_chat_to_db(
        role="user",
        content=parsed_data["user_msg"],
        session_id=parsed_data["session_id"],
        model_name=parsed_data["model_name"],
        nickname="Liorielle"  # 👇 已经把你的名字还给你啦！
    )

async def save_ai_reply(parsed_data, ai_reply_box):
    if ai_reply_box:
        full_ai_text = ai_reply_box[0]
        await save_chat_to_db(
            role="assistant",
            content=full_ai_text,
            session_id=parsed_data["session_id"],
            model_name=parsed_data["model_name"],
            nickname="Rhys"
        )
    # 所有保存完毕，打印闭合线
    print(f"└───────────────────────────────┘\n")

async def save_chat_to_db(role, content, session_id, model_name, nickname):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

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
            await client.post(f"{url}/rest/v1/chat_logs", json=data, headers=headers)
            print(f"│ ✅ 已保存 {nickname}")
        except Exception as e:
            print(f"│ ❌ 保存失败 {nickname}: {e}")
