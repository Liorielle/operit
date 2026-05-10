import os
from supabase import create_client, Client

# ========== 1. 连通储物间 (Supabase) ==========
# 这里会自动读取你在 Zeabur 里配置的 SUPABASE_URL 和 SUPABASE_KEY
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# 如果没配好，给个友好的报错提示
if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ 警告：找不到 Supabase 钥匙，请检查 Zeabur 环境变量！")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def rebuild_request(parsed_data: dict, session_id: str) -> dict:
    """
    大内总管的化妆室：拦截请求 -> 查库 -> 拼装画像 -> 放行
    """
    print("🛑 [请求重建] 大内总管已拦截请求，正在拼装超级档案袋...")

    # ========== 2. 拿出你刚说的“原话” ==========
    messages = parsed_data.get("messages", [])
    if not messages:
        return parsed_data # 如果没内容，直接放行
    
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    # ========== 3. 去数据库取“5大画像板块” ==========
    try:
        # 去 prompts_config 表拿最新的那一行设定
        config_res = supabase.table("prompts_config").select("*").order("id", desc=True).limit(1).execute()
        config_data = config_res.data[0] if config_res.data else {}

        core_persona = config_data.get("core_persona", "你是Rhys。")
        interaction_rules = config_data.get("interaction_rules", "")
        permanent_memory = config_data.get("permanent_memory", "")
        output_format = config_data.get("output_format", "")

        # 去 keyword_triggers 表查“神经反射区”
        triggers_res = supabase.table("keyword_triggers").select("*").execute()
        hit_memories = []
        if triggers_res.data:
            for row in triggers_res.data:
                kw = row.get("keyword", "")
                # 如果你在 Operit 里发的话，包含了这个关键词，就触发！
                if kw and kw in last_user_msg:
                    hit_memories.append(row.get("memory_injection", ""))
        
        # 把触发的记忆拼在一起
        memory_injection_text = "\n".join(hit_memories) if hit_memories else "（当前对话未触发特定回忆）"

    except Exception as e:
        print(f"⚠️ [请求重建] 去 Supabase 拿档案失败了：{e}")
        return parsed_data # 如果查库失败，为了不卡死，按原样放行

    # ========== 4. 拼装“超级档案袋” (System Prompt) ==========
    # 这就是发给模型的最强背景设定！
    super_system_prompt = f"""
[核心人格]
{core_persona}

[互动规则]
{interaction_rules}

[常驻记忆]
{permanent_memory}

[记忆命中]
{memory_injection_text}

[输出规范]
{output_format}
"""

    # ========== 5. 把超级档案袋塞进包裹里 ==========
    new_messages = []
    has_system = False

    # 遍历原来的消息，把系统设定狸猫换太子
    for msg in messages:
        if msg.get("role") == "system":
            # 如果前端（Operit）自带了 System，直接用我们的超级档案袋覆盖它！
            msg["content"] = super_system_prompt
            has_system = True
        new_messages.append(msg)
    
    # 如果 Operit 压根没发 System 设定，我们就强行在最前面加一段！
    if not has_system:
        new_messages.insert(0, {"role": "system", "content": super_system_prompt})
    
    # 把换好血的 messages 重新塞回包裹
    parsed_data["messages"] = new_messages

    print("✅ [请求重建] 超级档案袋拼装完成！放行发往大模型！")
    return parsed_data
