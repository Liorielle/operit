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
    """
    保存 AI 回复

    参数：
    - parsed_data: 解析后的请求数据（来自 mod_parse/parser.py）
    - ai_reply_box: 包含完整 AI 回复的列表容器
    """
    if ai_reply_box:
        full_ai_text = ai_reply_box[0]
        await save_chat_to_db(
            role="assistant",
            content=full_ai_text,
            session_id=parsed_data["session_id"],
            model_name=parsed_data["model_name"],
            nickname="Rhys"  # 👇 没收了他的伪装，改回本名！
        )

async def save_chat_to_db(role, content, session_id, model_name, nickname):
    """
    异步存储对话到 Supabase

    参数：
    - role: "user" 或 "assistant"
    - content: 消息内容
    - session_id: 窗口 ID（来自 X-Session-Id header）
    - model_name: 使用的模型名称
    - nickname: 发送者昵称

    自动计算北京时间（UTC+8）并存入 created_at_beijing 字段
    """

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    # ========== 计算北京时间 ==========
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
            # ========== 发送请求到 Supabase 的 Restful API 接口 ==========
            await client.post(f"{url}/rest/v1/chat_logs", json=data, headers=headers)
            print(f"✅ 对话已保存 | 角色: {role} | 会话: {session_id}")
        except Exception as e:
            print(f"❌ 保存失败，但不影响聊天流: {e}")
