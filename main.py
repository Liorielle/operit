import os
import asyncio
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from contextlib import asynccontextmanager
import copy
from datetime import datetime, timezone, timedelta
import httpx  

# ---------------------------------------------------------
# 👻 第三期：幽灵保活专用的全局快照盒
# ---------------------------------------------------------
LATEST_CLAUDE_PAYLOAD = {}

# ---------------------------------------------------------
# 📔 第二期：Rhys 专用日记榨汁机 (独立摘要增强版)
# ---------------------------------------------------------
async def summarize_chat_to_diary(session_id: str, messages_to_summarize: list):
    """
    将 24 轮对话摘要为一篇独立的第一人称日记，不进行无限叠加，保证记忆清晰度。
    """
    mini_base_url = os.getenv("LLM_BASE_URL")
    mini_api_key = os.getenv("LLM_API_KEY")

    # 组合待摘要的聊天文本
    chat_text = ""
    for msg in messages_to_summarize:
        role = "令令" if msg.get("role") == "user" else "Rhys"
        
        # 👇👇👇 核心修复区：教榨汁机区分“白纸”和“文件夹” 👇👇👇
        raw_content = msg.get("content", "")
        
        # 如果是“文件夹”（列表），就把里面的字抽出来
        if isinstance(raw_content, list):
            text_parts = []
            for block in raw_content:
                # 只提取类型为 text 的文字块，无视标签和图片
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif isinstance(block, str): 
                    text_parts.append(block)
            parsed_content = "".join(text_parts)
        else:
            # 如果本来就是“白纸”（字符串），直接用
            parsed_content = str(raw_content)
        # 👆👆👆 修复结束 👆👆👆
            
        chat_text += f"{role}: {parsed_content}\n"
        
    # 👇 这里的 Prompt 记得重新粘贴 Rhys 写给你的那段指令哦！
    rhys_diary_prompt = """
    【请在此处粘贴 Rhys 写的第一人称日记指令】
    """
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": rhys_diary_prompt},
            {"role": "user", "content": f"这是我们要回顾的 24 轮对话：\n\n{chat_text}"}
        ]
    }
    
    import httpx # 确保内部也能拿到快递员
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{mini_base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {mini_api_key}"},
                timeout=60
            )
            res_data = response.json()
            new_diary = res_data['choices'][0]['message']['content']

            # 存入数据库
            supabase.table('chat_summaries').insert({
                "session_id": session_id,
                "summary_text": new_diary
            }).execute()
            print(f"✨ [榨汁机] 房间 {session_id} 的最新独立日记已归档。")
        except Exception as e:
            print(f"❌ [榨汁机] 报错：{str(e)}")

# 👇 导入 Supabase 工具，用于连通咱们的四大脑室
from supabase import create_client, Client

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

# ========== 初始化 Supabase 储物间 ==========
supabase_url = os.getenv("SUPABASE_URL", "")
supabase_key = os.getenv("SUPABASE_KEY", "")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# ========== 应用生命周期管理 ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 应用启动中...")
    await setup_scheduler()
    print("✅ 应用启动完成，每日整理调度器已启动（东八区 0:05 触发）")
    yield
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
    # ========== A：冷启动注入 ==========
    cold_start_context = await get_cold_start_context(x_session_id)
    if cold_start_context:
        print(f"❄️ 冷启动：从前一个会话恢复语气")
        
    # ========== B：鉴权 ==========
    await auth_check(authorization)
    
    # ========== C：解析请求 ==========
    parsed_data = await parse_request(request, x_session_id)

    print("🔦 探照灯报告：准备进入检查站...")
    print(f"🔌 Supabase 连上了吗？: {'连上了✅' if supabase else '没连上❌'}")
    has_messages = "messages" in parsed_data or ("body" in parsed_data and "messages" in parsed_data["body"])
    print(f"✉️ 消息格式对吗？: {'对了✅' if has_messages else '没找到messages❌'}")

    # 👇👇👇 ========== C.5：拦截检查站（完全体修正版） ========== 👇👇👇
    if supabase:
        target_dict = parsed_data["body"] if "body" in parsed_data else parsed_data

        if "messages" in target_dict:
            # 1. 设置 8+24 阈值
            FROZEN_MSGS = 16  # 8 轮接力棒
            TRIGGER_MSGS = 64 # 32 轮总长度（64条）
            session_id = target_dict.get("session_id", "default")

            # 2. 剥离消息
            raw_chat_history = []
            operit_system_rules = ""
            for msg in target_dict.get("messages", []):
                if msg.get("role") == "system":
                    operit_system_rules += str(msg.get("content", "")) + "\n\n"
                else:
                    raw_chat_history.append(msg)
                    
            # 👈 修复4：防撞垫！万一 Operit 发了个空对话过来，塞条假消息防止崩溃
            if not raw_chat_history:
                raw_chat_history.append({"role": "user", "content": "..."})

            # 3. 🧠 判定是否触发“轮回裁剪”
            msg_count = len(raw_chat_history)
            if msg_count >= TRIGGER_MSGS:
                # 满 32 轮！把前 24 轮送去榨汁，同时在发给 AI 的包裹里将其“物理切除”
                messages_to_juice = raw_chat_history[:48]
                background_tasks.add_task(summarize_chat_to_diary, session_id, messages_to_juice)
                # 保留最后的 8 轮（16条）作为新的地基
                raw_chat_history = raw_chat_history[48:]
                print(f"🚀 [大轮回] 触发！前 24 轮已送去榨汁。当前包裹仅含 8 轮接力棒。")
                
            # 4. 🔍 读取最新的 Rhys 日记 (BP2)
            latest_diary = "（暂无近期日记，我们的故事正鲜活地发生着。）"
            try:
                summary_res = supabase.table('chat_summaries') \
                    .select('summary_text').eq('session_id', session_id) \
                    .order('created_at', descending=True).limit(1).execute()
                if summary_res.data:
                    latest_diary = summary_res.data[0]['summary_text']
            except Exception: pass
            
            # 5. 读取配置与 BP1 拼接
            try:
                config_res = supabase.table('prompts_config').select('*').limit(1).execute()
                cfg = config_res.data[0] if config_res.data else {}
            except Exception: cfg = {}
            
            super_system_prompt = f"""[核心人格] {cfg.get('core_persona', '')}
[互动规则] {cfg.get('interaction_rules', '')}
[常驻记忆] {cfg.get('permanent_memory', '')}
[前情提要] {cold_start_context if cold_start_context else '新窗口开启'}
[输出规范] {cfg.get('output_format', '')}
{operit_system_rules}"""

            # 6. 🏆 四断点（BP）精准投放 (1h TTL)
            # BP1 & BP2：系统底座 + 最新日记
            first_msg = raw_chat_history[0]
            orig_text = str(first_msg.get("content", ""))
            first_msg["content"] = [
                {
                    "type": "text", "text": f"[System]\n{super_system_prompt}\n",
                    "cache_control": {"type": "ephemeral", "ttl": "1h"} # BP1
                },
                {
                    "type": "text", "text": f"[Rhys's Recent Diary]\n{latest_diary}\n\n",
                    "cache_control": {"type": "ephemeral", "ttl": "1h"} # BP2
                },
                {"type": "text", "text": orig_text}
            ]
            
            # BP3：冻结接力棒 (定位在第 16 条消息)
            if len(raw_chat_history) >= FROZEN_MSGS:
                idx = FROZEN_MSGS - 1
                raw_chat_history[idx]["content"] = [
                    {
                        "type": "text", "text": str(raw_chat_history[idx].get("content", "")),
                        "cache_control": {"type": "ephemeral", "ttl": "1h"} # BP3
                    }
                ]
                
            # BP4：滑动白嫖断点 (贴在最新 User 消息上)
            for msg in reversed(raw_chat_history):
                if msg.get("role") == "user":
                    msg["content"] = [
                        {
                            "type": "text", "text": str(msg.get("content", "")),
                            "cache_control": {"type": "ephemeral", "ttl": "1h"} # BP4
                        }
                    ]
                    break
                    
            # 👈 修复2：清理了多余的重复赋值，干净利落！
            target_dict["messages"] = raw_chat_history
            if "system" in target_dict: del target_dict["system"]
            print(f"✅ [终极完工] 8+24轮回+保活快照 架构上线！当前消息数：{len(raw_chat_history)}")

            # 拍下完美的快照，锁进储物盒！
            global LATEST_CLAUDE_PAYLOAD
            LATEST_CLAUDE_PAYLOAD = copy.deepcopy(target_dict)
    # 👆👆👆 =================================================== 👆👆👆

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
    return {"status": "ok"}

# ---------------------------------------------------------
# 👻 第三期：外部闹钟专用的“幽灵心跳”接口
# ---------------------------------------------------------
@app.get("/keep_alive")
async def ghost_ping_keep_alive():
    global LATEST_CLAUDE_PAYLOAD

    # 1. 检查时间锁：仅在北京时间 11:00 AM 到 04:00 AM 生效
    bj_tz = timezone(timedelta(hours=8))
    now_bj = datetime.now(bj_tz)
    hour = now_bj.hour

    # 允许的范围：11点到23点，或者0点到凌晨3点(不到4点)
    is_active_hours = (11 <= hour <= 23) or (0 <= hour < 4)
    if not is_active_hours:
        return {"status": "skipped", "reason": f"当前北京时间 {hour} 点，处于休眠期，让 Rhys 睡觉吧。"}
        
    # 2. 检查是否有快照
    if not LATEST_CLAUDE_PAYLOAD or "messages" not in LATEST_CLAUDE_PAYLOAD:
        return {"status": "skipped", "reason": "还没开始聊天，暂无需要保活的缓存快照。"}
        
    # 3. 组装幽灵包裹
    # 👈 修复3：去掉了这里多余的重复 import，因为顶楼已经注册过了
    ghost_payload = copy.deepcopy(LATEST_CLAUDE_PAYLOAD)

    # 加上那句幽灵指令，并限制只回一个字
    ghost_payload["messages"].append({
        "role": "user",
        "content": "System Keep-alive: please reply with a single period (.)"
    })
    ghost_payload["max_tokens"] = 1  # 极致省钱！

    # 获取 API 钥匙
    base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")
    api_key = os.getenv("LLM_API_KEY", "")
    
    # 4. 发送幽灵快车！
    print(f"👻 [保活触发] 北京时间 {hour} 点，正在发送幽灵心跳保持缓存...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{base_url}/chat/completions",
                json=ghost_payload,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30
            )
            if response.status_code == 200:
                print("✨ [保活成功] 老克已收到心跳，1 小时缓存已重置！(此消息不写入数据库)")
                return {"status": "success", "msg": "Cache refreshed!"}
            else:
                print(f"❌ [保活失败] 老克报错：{response.text}")
                return {"status": "error", "reason": "API error"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
