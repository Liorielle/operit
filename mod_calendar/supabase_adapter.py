"""
Supabase 适配器 - 将 kiwi-mem 的数据库调用适配到你的 Supabase
这是唯一需要修改的部分，保持 kiwi-mem 原逻辑不变
"""

import os
from datetime import datetime
from typing import List, Dict, Optional


# Supabase 客户端（需要你配置）
class SupabaseClient:
    """Supabase 客户端模拟，你需要替换为真实的客户端"""
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        # 这里需要初始化真实的 supabase 客户端
        # from supabase import create_client
        # self.client = create_client(self.url, self.key)


# 全局 Supabase 客户端实例
_supabase_client = None


def get_supabase_pool():
    """获取 Supabase 连接池"""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
    return _supabase_client


async def save_memory(memory_data: Dict):
    """保存记忆到 Supabase - 适配 kiwi-mem 的 save_memory 接口"""
    client = get_supabase_pool()
    
    # 映射 kiwi-mem 字段到你的 Supabase 表结构
    supabase_data = {
        "user_id": memory_data.get("user_id", "default"),
        "title": memory_data["title"],
        "content": memory_data["content"],
        "importance": memory_data.get("importance", 5),
        "category": memory_data.get("category", ""),
        "memory_type": memory_data["memory_type"],
        "date": memory_data.get("date"),
        "created_at": datetime.now().isoformat()
    }
    
    # 插入到你的 memories 表
    # result = client.table("memories").insert(supabase_data).execute()
    print(f"💾 保存记忆: {supabase_data['title']}")
    return {"id": "mock_id"}


async def get_embedding(text: str):
    """获取文本嵌入 - 如果你需要向量搜索"""
    # 这里可以实现文本嵌入生成
    # 或者使用 Supabase 的 pgvector 功能
    return [0.1] * 1536  # 模拟嵌入


async def get_all_categories():
    """获取所有分类列表"""
    # 从你的分类表或配置中获取
    return [
        "前端开发", "饮食记录", "情绪状态", "作息", 
        "角色扮演", "理财", "学习", "工作", "健康", "娱乐"
    ]


async def match_category_by_name(category_name: str):
    """根据名称匹配分类"""
    categories = await get_all_categories()
    for cat in categories:
        if category_name in cat or cat in category_name:
            return cat
    return ""


async def query_fragments_by_time_range(start_time: datetime, end_time: datetime):
    """查询时间范围内的碎片记忆"""
    client = get_supabase_pool()
    
    # 查询你的 conversations 表
    # result = client.table("conversations") \
    #     .select("*") \
    #     .gte("created_at", start_time.isoformat()) \
    #     .lt("created_at", end_time.isoformat()) \
    #     .execute()
    
    # 模拟数据
    return [
        {
            "id": "frag_1",
            "content": "用户提到了喜欢喝咖啡",
            "created_at": start_time.isoformat()
        },
        {
            "id": "frag_2", 
            "content": "用户说最近在学习编程",
            "created_at": start_time.isoformat()
        }
    ]


async def update_fragments_digested(fragment_ids: List[str]):
    """标记碎片为已整理"""
    # 在你的表中标记这些记录为已处理
    # client.table("conversations") \
    #     .update({"processed": True}) \
    #     .in_("id", fragment_ids) \
    #     .execute()
    print(f"✅ 标记 {len(fragment_ids)} 条碎片为已整理")


async def get_calendar_summaries(user_id: str, level: str, start_date: str, limit: int = 10):
    """获取日历摘要"""
    client = get_supabase_pool()
    
    # 查询 calendar_summaries 表
    # result = client.table("calendar_summaries") \
    #     .select("*") \
    #     .eq("user_id", user_id) \
    #     .eq("level", level) \
    #     .gte("date", start_date) \
    #     .order("date", desc=True) \
    #     .limit(limit) \
    #     .execute()
    
    return []


async def get_user_profile(user_id: str):
    """获取用户画像"""
    client = get_supabase_pool()
    
    # 查询 user_profiles 表
    # result = client.table("user_profiles") \
    #     .select("*") \
    #     .eq("user_id", user_id) \
    #     .execute()
    
    return None


# 数据初始化函数
async def initialize_existing_data():
    """初始化现有数据 - 处理你的70MB历史对话"""
    print("🚀 开始初始化现有数据...")
    
    # 1. 检查最新摘要日期
    latest_date = await get_latest_summary_date()
    
    # 2. 从最新日期开始处理
    if latest_date:
        print(f"📅 从最新日期 {latest_date} 开始增量处理")
    else:
        print("🆕 首次运行，处理所有历史数据")
    
    # 3. 按时间顺序生成摘要
    # 这里需要实现批量处理逻辑
    
    print("✅ 数据初始化完成")


async def get_latest_summary_date():
    """获取最新的摘要日期"""
    # 查询 calendar_summaries 表的最新日期
    return None
