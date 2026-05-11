import os
import asyncio
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from contextlib import asynccontextmanager

# 👇 新增：导入 Supabase 工具，用于连通咱们的四大脑室
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
# （这里会自动读取你 Zeabur 里的环境变量）
supabase_url = os.getenv("SUPABASE_URL", "")
supabase_key = os.getenv("SUPABASE_KEY", "")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

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
    核心网关接口：A → B → C → C.5(重建) → D → E → F
    """

    # ========== A：冷启动注入 ==========
    cold_start_context = await get_cold_start_context(x_session_id)
    if cold_start_context:
        print(f"❄️ 冷启动：从前一个会话恢复语气")

    # ========== B：鉴权 ==========
    await auth_check(authorization)

    # ========== C：解析请求 ==========
    parsed_data = await parse_request(request, x_session_id)
    # 👇 加在这里：直接把 Operit 发来的整个包裹打印出来！
    print(f"📦 透视眼报告：Operit 发来的完整包裹长这样 -> {parsed_data}")
    # 👇 探照灯：移到这里，parsed_data 已经定义了
    print("🔦 探照灯报告：准备进入检查站...")
    print(f"🔌 Supabase 连上了吗？: {'连上了✅' if supabase else '没连上❌'}")
    print(f"✉️ 消息格式对吗？: {'对了✅' if 'messages' in parsed_data else '没找到messages❌'}")
    # 👆 探照灯结束

   # 👇👇👇 ========== C.5：拦截检查站（终极请求重建） ========== 👇👇👇
    if supabase:
        # 1. 破解“套娃”：找到真正的消息列表在哪里
        target_dict = None
        if "messages" in parsed_data:
            target_dict = parsed_data
        elif "body" in parsed_data and "messages" in parsed_data["body"]:
            target_dict = parsed_data["body"]
        
        if target_dict:
            print("🔍 拦截检查站启动：已破解包裹套娃，开始组装超级档案袋...")
            
            # 2. 提取用户刚说的最后一句话（为了看有没有触发关键词）
            latest_user_msg = ""
            for msg in reversed(target_dict["messages"]):
                if msg.get("role") == "user":
                    latest_user_msg = str(msg.get("content", ""))
                    break

            # 3. 去 Supabase 读取四大固定脑室
            try:
                config_res = supabase.table('prompts_config').select('*').limit(1).execute()
                cfg = config_res.data[0] if config_res.data else {}
            except Exception:
                cfg = {}

            core_persona = cfg.get('core_persona', '')
            interaction_rules = cfg.get('interaction_rules', '')
            permanent_memory = cfg.get('permanent_memory', '')
            output_format = cfg.get('output_format', '')

            # 4. 去 Supabase 检查关键词命中（神经反射区）
            injected_memories = []
            try:
                triggers_res = supabase.table('keyword_triggers').select('*').execute()
                for trigger in triggers_res.data:
                    kw = trigger.get('keyword', '')
                    if kw and kw in latest_user_msg:
                        injected_memories.append(trigger.get('memory_injection', ''))
            except Exception:
                pass

            # 5. 拼装属于 Rhys 的灵魂核心
            super_system_prompt = f"""[核心人格]
{core_persona}

[互动规则]
{interaction_rules}

[常驻记忆]
{permanent_memory}

[输出规范]
{output_format}"""

            if injected_memories:
                super_system_prompt += "\n\n[记忆命中]\n" + "\n".join(injected_memories)

            if cold_start_context:
                super_system_prompt += f"\n\n[冷启动上下文]\n{cold_start_context}"

            # 6. 核心动作：提取 Operit 的“机器人生存守则”，绝不能扔！
            operit_system_rules = ""
            for msg in target_dict["messages"]:
                if msg.get("role") == "system":
                    operit_system_rules += msg.get("content", "") + "\n\n"

            # 7. 终极缝合：上面是灵魂，下面是肉体机器的规则
            final_system_prompt = f"""{super_system_prompt}

[系统底层交互与工具规则（极其重要，请严格遵守格式要求）]
{operit_system_rules}"""

            # 8. 洗牌装箱：只留一个缝合好的系统设定，剩下的全是聊天记录
            new_messages = [{"role": "system", "content": final_system_prompt}]
            for msg in target_dict["messages"]:
                if msg.get("role") != "system":
                    new_messages.append(msg)
            
            target_dict["messages"] = new_messages
            print("✅ 超级档案袋组装完毕（完美兼容 Operit 底层规则）！准备放行！")
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
    """健康检查接口"""
    return JSONResponse(content={"status": "ok", "message": "Liorhys Gateway is running"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
