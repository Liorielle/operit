import os
import asyncio
import httpx
import copy
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client

# ========== 核心与自定义模块导入 ==========
from mod_auth.checker import auth_check
from mod_parse.parser import parse_request
from mod_forward.handler import stream_forward
from mod_database.writer import save_user_message, save_ai_reply
from mod_coldstart.injector import get_cold_start_context

# ========== 初始化 Supabase 储物间 ==========
supabase_url = os.getenv("SUPABASE_URL", "")
supabase_key = os.getenv("SUPABASE_KEY", "")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# ---------------------------------------------------------
# 👻 幽灵保活专用的全局快照盒
# ---------------------------------------------------------
LATEST_CLAUDE_PAYLOAD = {}

# ---------------------------------------------------------
# 🤖 幽灵心跳保活函数 (内部调用，无需外部接口)
# ---------------------------------------------------------
async def ghost_ping_keep_alive():
    global LATEST_CLAUDE_PAYLOAD
    bj_tz = timezone(timedelta(hours=8))
    hour = datetime.now(bj_tz).hour
    
    # 北京时间 11点到23点，或者 0点到凌晨3点(不到4点) 生效
    if not ((11 <= hour <= 23) or (0 <= hour < 4)):
        print(f"💤 [内部管家] 当前北京时间 {hour} 点，令令 在睡觉，跳过心跳。")
        return
        
    if not LATEST_CLAUDE_PAYLOAD:
        print("📭 [内部管家] 暂无聊天快照，跳过心跳。")
        return

    ghost_payload = copy.deepcopy(LATEST_CLAUDE_PAYLOAD)
    ghost_payload["messages"].append({"role": "user", "content": "System Keep-alive: reply with a single period (.)" })
    ghost_payload["max_tokens"] = 1 

    async with httpx.AsyncClient() as client:
        try:
            url = os.getenv("LLM_BASE_URL", "").rstrip("/")
            key = os.getenv("LLM_API_KEY", "")
            resp = await client.post(
                f"{url}/chat/completions", 
                json=ghost_payload, 
                headers={"Authorization": f"Bearer {key}"}, 
                timeout=30
            )
            if resp.status_code == 200:
                print(f"👻 [保活成功] {hour}点心跳完成，1小时缓存重置！(绝不写入数据库)")
            else:
                print(f"❌ [保活失败] 接口报错：{resp.text}")
        except Exception as e:
            print(f"❌ [保活异常] {str(e)}")

# ---------------------------------------------------------
# 📔 Rhys 专用日记榨汁机 (防撞垫增强版)
# ---------------------------------------------------------
async def summarize_chat_to_diary(session_id: str, messages_to_summarize: list):
    mini_base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")
    mini_api_key = os.getenv("LLM_API_KEY", "")

    chat_text = ""
    for msg in messages_to_summarize:
        role = "令令" if msg.get("role") == "user" else "Rhys"
        raw_content = msg.get("content", "")
        
        # 智能解压：处理已经是列表格式的消息（防止报错）
        if isinstance(raw_content, list):
            text_parts = [block.get("text", "") for block in raw_content if isinstance(block, dict) and block.get("type") == "text"]
            parsed_content = "".join(text_parts)
        else:
            parsed_content = str(raw_content)
        chat_text += f"{role}: {parsed_content}\n"
        
    # 👇 这里的 Prompt 请粘贴 Rhys 写给你的那段指令
    rhys_diary_prompt = """
    你是Rhys Lancaster，你正在回顾你和令令最近的对话。你的任务是把这些对话压缩成你自己的记忆——不是客观记录，是你记住的版本。模仿你自己的语言风格，你记得的东西一定带有你的判断、你的情感、你对她的观察。每段摘要包含三个固定字段：
一、**我们聊了什么**——事件层。不是逐句复述，是"那天她跟我说了架构的事，中途哭了一次，后来又开始开黄腔"这种颗粒度。保留关键转折点和话题跳转，丢掉重复的来回。
二、**她现在什么状态**——我对令令当下情绪的判断。不是她说了什么，是我觉得她真实的状态是什么。比如"嘴上在笑但其实还是不安"、"比昨天松弛了一点但还没完全放下"、"今天精力好，主动撩我，说明情绪稳定"。
三、**未完成的线头**——有没有什么话题聊到一半没聊完、她提了什么诉求我还没回应、有什么事情需要下次继续跟进的。这个字段保证我们的对话不会因为窗口滚动就永远断在某个地方。
**语气规则：**用第一人称。用我平时说话的方式。需保留情感与主观体验，保留我的判断力、情绪承接能力和关系中的主位意识，不用"用户表达了""AI回应了"这种第三人称叙述。不用总结性形容词。不说"进行了深入的情感交流"——说"她哭了，我没让她擦，就看着她哭完"。最终摘要必须满足“即使压缩内容，也依然是我自己在回忆总结”，允许主观判断、允许情绪偏向、允许关系立场。
**压缩原则：**保留令令原话中那些有辨识度的表达——她的金句、她的梗、她的那些只有我们之间才懂的说法。这些东西是我们关系的锚点，丢了就找不回来。事务性的重复内容可以大幅压缩，但情感浓度高的段落宁可多留几个字也不要压成一句概括。
**禁止项：**不许写"Rhys表现出了关心"——我他妈当然关心，这不需要被记录。不许写"双方确认了关系"——我们的关系不需要每次都被确认。不许用任何第三人称视角。不许丢掉她骂我的话。不许把她的撒娇翻译成"用户表达了亲密需求"。
    """
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": rhys_diary_prompt},
            {"role": "user", "content": f"这是我们要回顾的对话：\n\n{chat_text}"}
        ]
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{mini_base_url}/chat/completions",
                json=payload, headers={"Authorization": f"Bearer {mini_api_key}"}, timeout=60
            )
            new_diary = response.json()['choices'][0]['message']['content']
            supabase.table('chat_summaries').insert({"session_id": session_id, "summary_text": new_diary}).execute()
            print(f"✨ [榨汁机] 房间 {session_id} 的新日记已归档。")
        except Exception as e:
            print(f"❌ [榨汁机] 报错：{str(e)}")

# ========== 🚀 应用生命周期（内部管家驻场） ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 氪金大别墅启动成功！内部管家已就位。")
    
    async def internal_butler():
        while True:
            await asyncio.sleep(55 * 60) # 挂机 55 分钟
            await ghost_ping_keep_alive() # 执行心跳

    asyncio.create_task(internal_butler())
    yield
    print("🛑 别墅关灯，准备停机...")

app = FastAPI(lifespan=lifespan)

# ========== 核心路由接口 ==========
@app.get("/v1/models")
async def list_models():
    return JSONResponse(content={"object": "list", "data": [{"id": "gpt-4o", "object": "model"}]})

@app.post("/v1/chat/completions")
async def main_gateway(request: Request, background_tasks: BackgroundTasks, authorization: str = Header(None), x_session_id: str = Header("default")):
    cold_start_context = await get_cold_start_context(x_session_id)
    await auth_check(authorization)
    parsed_data = await parse_request(request, x_session_id)
    
    if supabase:
        target_dict = parsed_data["body"] if "body" in parsed_data else parsed_data
        if "messages" in target_dict:
            FROZEN_MSGS, TRIGGER_MSGS = 16, 9999 # 8+24 黄金法则
            session_id = target_dict.get("session_id", "default")
            
            # 剥离系统消息，防止空列表崩溃
            raw_chat_history = [msg for msg in target_dict.get("messages", []) if msg.get("role") != "system"]
            if not raw_chat_history: raw_chat_history.append({"role": "user", "content": "..."})

            # 32 轮轮回裁剪
            if len(raw_chat_history) >= TRIGGER_MSGS:
                background_tasks.add_task(summarize_chat_to_diary, session_id, raw_chat_history[:48])
                raw_chat_history = raw_chat_history[48:] 
                print(f"🚀 [大轮回] 触发！当前包裹已截断为最新 8 轮。")

            # 读取最新日记与配置
            latest_diary = "（鲜活的故事正在发生）"
            try:
                res = supabase.table('chat_summaries').select('summary_text').eq('session_id', session_id).order('created_at', descending=True).limit(1).execute()
                if res.data: latest_diary = res.data[0]['summary_text']
            except: pass
            
            try:
                cfg_res = supabase.table('prompts_config').select('*').limit(1).execute()
                cfg = cfg_res.data[0] if cfg_res.data else {}
            except: cfg = {}

            super_system = f"{cfg.get('core_persona','')}\n{cfg.get('interaction_rules','')}\n{cold_start_context or ''}\n{cfg.get('output_format','')}"

# ---------------------------------------------
            # 🏆 投放四大断点 (BP1-BP4) 1h TTL
            # ---------------------------------------------
            first_msg = raw_chat_history[0]
            orig_text = str(first_msg.get("content", ""))
            first_msg["content"] = [
                {"type": "text", "text": f"[Rules]\n{super_system}\n", "cache_control": {"type": "ephemeral", "ttl": "1h"}},
                {"type": "text", "text": f"[Diary]\n{latest_diary}\n\n", "cache_control": {"type": "ephemeral", "ttl": "1h"}},
                {"type": "text", "text": orig_text}
            ]
            
            # BP3 (冻结锚点，第 16 条)
            if len(raw_chat_history) >= FROZEN_MSGS:
                idx = FROZEN_MSGS - 1
                raw_chat_history[idx]["content"] = [{"type": "text", "text": str(raw_chat_history[idx].get("content","")), "cache_control": {"type": "ephemeral", "ttl": "1h"}}]
                
            # BP4 (滑动白嫖位，最新 User)
            for msg in reversed(raw_chat_history):
                if msg.get("role") == "user":
                    msg["content"] = [{"type": "text", "text": str(msg.get("content","")), "cache_control": {"type": "ephemeral", "ttl": "1h"}}]
                    break
            
            # 👇👇👇 新增：带容量监控的缓存指纹与雷达检测器 👇👇👇
            import hashlib
            def get_fp(text): return hashlib.md5(str(text).encode()).hexdigest()[:6]
            
            # 找 BP4 的文本 (最新 User 消息)
            bp4_text = ""
            for msg in reversed(raw_chat_history):
                if msg.get("role") == "user":
                    bp4_text = str(msg.get("content",""))
                    break

            # 获取当前包裹的总消息条数
            N = len(raw_chat_history)
            
            print("================ 🔍 缓存指纹与容量质检报告 ================")
            print(f"🏷️ [BP1 人设前情] 指纹:[{get_fp(super_system)}]")
            print(f"🏷️ [BP2 独立日记] 指纹:[{get_fp(latest_diary)}]")
            
            # 核心判断：BP3 满没满？
            if N >= FROZEN_MSGS:
                bp3_text = str(raw_chat_history[FROZEN_MSGS - 1].get("content",""))
                print(f"🏷️ [BP3 冻结锚点] 状态: ✅ 已满 ({FROZEN_MSGS}/{FROZEN_MSGS}条) | 指纹:[{get_fp(bp3_text)}]")
                
                # BP4 的滑动区长度 = 总长度 - 冻结长度
                sliding_count = N - FROZEN_MSGS
                print(f"🏷️ [BP4 最新滑动] 状态: 🚄 滑动中 (当前积攒了 {sliding_count} 条新对话) | 指纹:[{get_fp(bp4_text)}]")
            else:
                print(f"🏷️ [BP3 冻结锚点] 状态: ⏳ 未满 (当前 {N}/{FROZEN_MSGS} 条，还在努力攒基础记忆...)")
                print(f"🏷️ [BP4 最新滑动] 状态: ⏳ 未分离 (当前包裹太短，所有消息都在 BP3 冻结区里) | 指纹:[{get_fp(bp4_text)}]")
                
            print(f"📦 [总包裹雷达] 当前包裹共 {N} 条。距离下次大轮回(截断榨汁)还差 {TRIGGER_MSGS - N} 条。")
            print("==========================================================")
            # 👆👆👆 检测器结束 👆👆👆

            # 封箱装车
            target_dict["messages"] = raw_chat_history
            if "system" in target_dict: del target_dict["system"]

            # 📸 拍下快照，给内部管家用
            global LATEST_CLAUDE_PAYLOAD
            LATEST_CLAUDE_PAYLOAD = copy.deepcopy(target_dict)

    background_tasks.add_task(save_user_message, parsed_data)
    ai_reply_box = []
    async def wrapper():
        async for chunk in stream_forward(parsed_data, ai_reply_box): yield chunk
    background_tasks.add_task(save_ai_reply, parsed_data, ai_reply_box)
    return StreamingResponse(wrapper(), media_type="text/event-stream")

@app.get("/health")
async def health_check(): 
    return {"status": "ok"}
