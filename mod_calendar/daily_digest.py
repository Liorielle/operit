"""
kiwi-mem 每日记忆整理模块 - 原版适配
每天自动把碎片记忆合并为事件条目
================================================================
保持 kiwi-mem 原逻辑，只替换数据库接口为 Supabase
"""

import os
import json
import asyncio
import httpx
from datetime import datetime, timedelta, timezone


# ============================================================
# API 配置 —— 记忆整理用独立 key，避免和聊天抢额度
# ============================================================


MEMORY_API_KEY = os.getenv("MEMORY_API_KEY", "") or os.getenv("API_KEY", "")
_RAW_BASE_URL = os.getenv("MEMORY_API_BASE_URL", "") or os.getenv("API_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")


# 确保 URL 以 /chat/completions 结尾
MEMORY_API_BASE_URL = _RAW_BASE_URL if _RAW_BASE_URL.rstrip("/").endswith("/chat/completions") else f"{_RAW_BASE_URL.rstrip('/')}/chat/completions"


DIGEST_MODEL = os.getenv("MEMORY_MODEL", "anthropic/claude-haiku-4")


# 东八区（北京 / 上海 / 台北）
TZ_CST = timezone(timedelta(hours=8))


# ============================================================
# 整理 Prompt
# ============================================================


DIGEST_PROMPT = """你是记忆整理专家。以下是用户在 {date} 这一天的碎片记忆，请将它们按事件主题合并整理。


## 整理规则
- 按主题分类合并（如"前端开发""饮食记录""情绪状态""作息""角色扮演""理财"等）
- 每条是一个独立事件，不要把不相关的事硬合在一起
- 保留关键细节（时间、数值、具体内容），去掉重复和琐碎的部分
- 如果某条碎片本身已经很完整独立，保持原样即可
- 标题用 4-10 个字概括主题
- 内容用 1-3 句话总结这个事件的要点
- importance 根据事件对用户的重要程度打分：9-10 核心事件 / 7-8 重要 / 5-6 普通


## 可用的分类列表
{categories_list}


## 今天的碎片记忆
{fragments}


## 输出格式
只输出 JSON 数组，不要其他内容：
[
  {"title": "简短标题", "content": "整理后的内容", "importance": 7, "category": "分类名"},
  {"title": "简短标题", "content": "整理后的内容", "importance": 5, "category": "分类名"}
]


category 字段从上面的分类列表中选择最合适的一个，如果都不合适就填空字符串。"""


# 防止同一日期被并发整理（定时器 + 手动 API 同时触发）
_digest_running: set = set()
_digest_lock = asyncio.Lock()




async def run_daily_digest(target_date: str = None, model_override: str = None, prompt_override: str = None):
    """
    执行每日记忆整理


    Args:
        target_date: 要整理的日期，格式 "2026-03-02"，默认为昨天
        model_override: 覆盖默认整理模型
        prompt_override: 覆盖默认整理提示词
    """
    # 替换 kiwi-mem 的数据库调用为 Supabase
    from .supabase_adapter import get_supabase_pool, save_memory, get_embedding, get_all_categories, match_category_by_name
    from datetime import date as date_cls


    now_cst = datetime.now(TZ_CST)


    if target_date:
        # 校验格式，避免后续 fromisoformat 直接抛 ValueError 让接口 500
        try:
            date_cls.fromisoformat(target_date)
        except (ValueError, TypeError):
            return {"error": f"无效日期格式: {target_date!r}，需要 YYYY-MM-DD"}
        date_str = target_date
    else:
        yesterday = now_cst - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")


    # 防止同一日期被并发整理（定时器 + 手动触发可能同时进来）
    async with _digest_lock:
        if date_str in _digest_running:
            print(f"⚠️ {date_str} 正在整理中，跳过重复请求")
            return {"date": date_str, "fragments": 0, "digests": 0, "skipped": "already running"}
        _digest_running.add(date_str)
    try:
        return await _run_daily_digest_impl(date_str, now_cst, model_override, prompt_override)
    finally:
        _digest_running.discard(date_str)


async def _run_daily_digest_impl(date_str: str, now_cst: datetime, model_override: str, prompt_override: str):
    """每日记忆整理的内部实现"""
    from .supabase_adapter import get_supabase_pool, save_memory, get_all_categories


    # 获取前一天的碎片记忆
    yesterday_start = (now_cst - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = yesterday_start + timedelta(days=1)


    # 使用 Supabase 查询碎片记忆
    fragments = await get_yesterday_fragments(yesterday_start, yesterday_end)
    
    if not fragments:
        print(f"📭 {date_str} 没有碎片记忆可整理")
        return {"date": date_str, "fragments": 0, "digests": 0, "skipped": "no fragments"}


    print(f"📝 {date_str} 开始整理 {len(fragments)} 条碎片记忆")


    # 获取分类列表
    categories = await get_all_categories()
    categories_list = "\n".join([f"- {cat}" for cat in categories])


    # 调用 LLM 整理记忆
    model = model_override or DIGEST_MODEL
    prompt = prompt_override or DIGEST_PROMPT


    fragments_text = "\n".join([
        f"[{i+1}] {fragment['content']}" 
        for i, fragment in enumerate(fragments)
    ])


    try:
        response = await _call_llm_for_digest(
            model=model,
            prompt=prompt.format(
                date=date_str,
                categories_list=categories_list,
                fragments=fragments_text
            )
        )


        if not response:
            return {"error": "LLM 响应为空"}


        # 解析 LLM 响应
        digests = _parse_digest_response(response)
        
        if not digests:
            return {"error": "无法解析 LLM 响应"}


        print(f"✅ {date_str} 生成 {len(digests)} 条摘要")


        # 保存摘要到数据库
        for digest in digests:
            await save_memory({
                "title": digest["title"],
                "content": digest["content"],
                "importance": digest["importance"],
                "category": digest["category"],
                "memory_type": "daily_digest",
                "date": date_str
            })


        # 标记碎片为已整理
        await mark_fragments_digested([f["id"] for f in fragments])


        return {
            "date": date_str,
            "fragments": len(fragments),
            "digests": len(digests),
            "summary": f"{date_str} 生成 {len(digests)} 条摘要"
        }


    except Exception as e:
        print(f"❌ {date_str} 整理失败: {e}")
        return {"error": str(e)}


async def get_yesterday_fragments(start_time: datetime, end_time: datetime):
    """获取昨天的碎片记忆 - 适配 Supabase"""
    from .supabase_adapter import query_fragments_by_time_range
    return await query_fragments_by_time_range(start_time, end_time)


async def mark_fragments_digested(fragment_ids: list):
    """标记碎片为已整理 - 适配 Supabase"""
    from .supabase_adapter import update_fragments_digested
    return await update_fragments_digested(fragment_ids)


async def _call_llm_for_digest(model: str, prompt: str) -> str:
    """调用 LLM 进行记忆整理"""
    headers = {
        "Authorization": f"Bearer {MEMORY_API_KEY}",
        "Content-Type": "application/json"
    }


    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 4000
    }


    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(MEMORY_API_BASE_URL, headers=headers, json=data)
        
        if response.status_code != 200:
            raise Exception(f"LLM API 错误: {response.status_code} - {response.text}")
        
        result = response.json()
        return result["choices"][0]["message"]["content"]


def _parse_digest_response(response: str) -> list:
    """解析 LLM 的摘要响应"""
    try:
        # 尝试提取 JSON 数组
        lines = response.strip().split('\n')
        json_start = None
        json_end = None
        
        for i, line in enumerate(lines):
            if line.strip().startswith('['):
    
