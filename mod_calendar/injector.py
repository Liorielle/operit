"""
记忆注入器 - 俄罗斯套娃式记忆注入
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
from .supabase_adapter import get_calendar_summaries, get_user_profile


async def get_calendar_context(parsed_data: dict, session_id: str) -> str:
    """
    为当前对话获取日历上下文
    俄罗斯套娃方式：最近几天完整，上周缩略，更早只给高层概括
    """
    user_id = _get_user_id(parsed_data, session_id)
    current_time = datetime.now()
    
    context_parts = []
    
    # 1. 最近3天的完整记忆（日摘要）
    recent_days = await get_calendar_summaries(user_id, "day", _days_ago(3))
    if recent_days:
        day_context = "## 最近几天\n" + "\n".join([
            f"• {item['date']}: {item.get('summary', item.get('content', ''))}"
            for item in recent_days
        ])
        context_parts.append(day_context)
    
    # 2. 上周的缩略版（周摘要）
    last_week = await get_calendar_summaries(user_id, "week", _weeks_ago(1))
    if last_week:
        week_context = "## 上周回顾\n" + "\n".join([
            f"• 第{item['date']}周: {item.get('summary', item.get('content', ''))}"
            for item in last_week
        ])
        context_parts.append(week_context)
    
    # 3. 本月的概括（月摘要）
    this_month = await get_calendar_summaries(user_id, "month", _months_ago(1))
    if this_month:
        month_context = "## 本月概况\n" + this_month[0].get('summary', this_month[0].get('content', ''))
        context_parts.append(month_context)
    
    # 4. 用户画像
    user_profile = await get_user_profile(user_id)
    if user_profile:
        profile_context = "## 用户画像\n" + user_profile.get('profile_summary', '')
        context_parts.append(profile_context)
    
    return "\n\n".join(context_parts) if context_parts else ""


def _get_user_id(parsed_data: dict, session_id: str) -> str:
    """从请求数据中提取用户ID"""
    # 根据你的架构实现
    # 可能的方式：
    # 1. 从消息中提取
    messages = parsed_data.get("messages", [])
    for msg in messages:
        if msg.get("role") == "user" and "user_id" in msg:
            return msg["user_id"]
    
    # 2. 从 parsed_data 中提取
    if "user_id" in parsed_data:
        return parsed_data["user_id"]
    
    # 3. 使用 session_id 作为后备
    return session_id


def _days_ago(days: int) -> str:
    """获取几天前的日期字符串"""
    return (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')


def _weeks_ago(weeks: int) -> str:
    """获取几周前的日期字符串"""
    return (datetime.now() - timedelta(weeks=weeks)).strftime('%Y-%m-%d')


def _months_ago(months: int) -> str:
    """获取几个月前的日期字符串"""
    return (datetime.now() - timedelta(days=30*months)).strftime('%Y-%m-%d')
