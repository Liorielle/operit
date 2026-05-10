import os
import httpx

async def get_cold_start_context(current_session_id):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    headers = {
        "apikey": key, 
        "Authorization": f"Bearer {key}"
    }

    async with httpx.AsyncClient() as client:
        # 1. 查询：除了当前窗口，上一个最近聊天的窗口叫什么？
        res1 = await client.get(
            f"{url}/rest/v1/chat_logs?select=session_id&session_id=neq.{current_session_id}&order=id.desc&limit=1",
            headers=headers
        )
        if res1.status_code != 200 or not res1.json():
            return None
        last_session_id = res1.json()[0]['session_id']

        # 2. 提取：拿到上一个窗口的最后 10 条消息（5轮原文）
        res2 = await client.get(
            f"{url}/rest/v1/chat_logs?select=role,content&session_id=eq.{last_session_id}&order=id.desc&limit=10",
            headers=headers
        )
        if res2.status_code != 200 or not res2.json():
            return None

        history = res2.json()
        history.reverse() # 数据库拿出来是倒序的，我们给它翻转成正常的时间顺序

        # 3. 核心：组装“记忆隔离罩” (防混淆 Prompt)
        shield_prompt = "\n\n【系统隐藏提示：记忆隔离罩】\n"
        shield_prompt += "以下是你与Liorielle在另一个聊天窗口中的最后几轮对话回顾。\n"
        shield_prompt += "【你的任务】：请仔细体会并完美继承你在这段对话中的说话语气、情感状态和专属称呼。\n"
        shield_prompt += "【严厉警告】：Liorielle现在已经开启了一个全新的聊天窗口。除非她问起，否则请勿强行延续旧话题或表现出疑惑，只需用你当前的语气，极其自然地回应用户刚发出的新消息。\n"
        shield_prompt += "---过去语气参考开始---\n"
        
        for msg in history:
            role_name = "User" if msg['content'] == 'user' else "Rhys"
            shield_prompt += f"{role_name}: {msg['content']}\n" 
            
        shield_prompt += "---过去语气参考结束---\n"

        return shield_prompt
