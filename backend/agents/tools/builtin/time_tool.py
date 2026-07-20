"""时间工具：当前时间查询、上次清扫时间、定时计划"""
from datetime import datetime
from typing import Dict, Any, Callable, Optional
from backend.agents.tools.base_tool import BaseTool, ToolResult


class TimeTool(BaseTool):
    """查询当前时间、上次任务记录和计划信息。"""

    name = "time_query"
    description = (
        "查询当前时间、上次清扫时间、定时计划。"
        "回答'现在几点''上次什么时候扫的''今天有没有计划'等问题"
    )
    parameters = {
        "query_type": {
            "type": "string",
            "enum": ["now", "last_task", "schedule", "all"],
            "description": "查询类型：now=当前时间, last_task=最近一次任务记录, schedule=今日计划, all=全部",
        },
    }

    def __init__(self,
                 get_last_episodic: Optional[Callable[[], str]] = None,
                 get_schedules: Optional[Callable[[], list]] = None):
        self._last_episodic = get_last_episodic
        self._get_schedules = get_schedules

    async def execute(self, query_type: str = "now", **kwargs) -> ToolResult:
        parts = []
        now = datetime.now()

        if query_type in ("now", "all"):
            parts.append(f"当前时间: {now.strftime('%Y年%m月%d日 %H:%M')} ({now.strftime('%A')})")

        if query_type in ("last_task", "all"):
            if self._last_episodic:
                try:
                    record = await self._last_episodic()
                    parts.append(f"最近任务: {record}" if record else "暂无任务记录")
                except Exception:
                    parts.append("最近任务: 查询失败")
            else:
                parts.append("最近任务: 记忆系统未配置")

        if query_type in ("schedule", "all"):
            if self._get_schedules:
                try:
                    schedules = await self._get_schedules()
                    if schedules:
                        today_str = now.strftime("%Y-%m-%d")
                        today_schedules = [s for s in schedules if s.get("date") == today_str]
                        if today_schedules:
                            tasks = [s.get("task", "未知") for s in today_schedules]
                            parts.append(f"今日计划: {', '.join(tasks)}")
                        else:
                            parts.append("今日无定时计划")
                    else:
                        parts.append("今日无定时计划")
                except Exception:
                    parts.append("定时计划: 查询失败")
            else:
                parts.append("定时计划: 未配置")

        return ToolResult(success=True, data={
            "answer": "\n".join(parts),
            "timestamp": now.isoformat(),
        })
