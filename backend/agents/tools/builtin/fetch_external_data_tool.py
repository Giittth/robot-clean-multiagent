"""获取用户使用记录的工具：查询数据库汇总用户某月的机器人使用数据"""
from backend.agents.tools.base_tool import BaseTool, ToolResult
from typing import Callable, Optional


class FetchExternalDataTool(BaseTool):
    """查询指定用户在某个月份的扫地/拖地机器人使用记录"""

    name = "fetch_external_data"
    description = "查询指定用户在某个月份的扫地/拖地机器人完整使用记录，包含清洁效率、耗材状态、使用对比等核心报告数据"
    parameters = {
        "user_id": {
            "type": "string",
            "description": "用户ID，数字字符串（如'1001'）",
            "required": True,
        },
        "month": {
            "type": "string",
            "description": "月份，严格遵循 YYYY-MM 格式（如'2026-07'）",
            "required": True,
        },
    }

    def __init__(self, query_usage_fn: Optional[Callable] = None):
        self._query_usage = query_usage_fn

    async def execute(self, user_id: str = "", month: str = "", **kwargs) -> ToolResult:
        if not user_id or not month:
            return ToolResult(success=False, error="缺少必填参数 user_id 或 month")
        try:
            if self._query_usage:
                data = await self._query_usage(user_id, month)
            else:
                data = {"note": "数据库查询函数未配置，使用模拟数据"}
                data.update(self._mock_data(user_id, month))
            return ToolResult(success=True, data={
                "answer": f"用户 {user_id} {month} 的使用数据已获取",
                "usage_data": data,
            })
        except Exception as e:
            return ToolResult(success=False, error=f"查询使用记录失败: {e}")

    @staticmethod
    def _mock_data(user_id: str, month: str) -> dict:
        return {
            "user_id": user_id,
            "month": month,
            "total_missions": 28,
            "successful_missions": 25,
            "failed_missions": 3,
            "coverage_percent_avg": 92.5,
            "total_cleaning_area_sqm": 185.0,
            "total_runtime_hours": 34.5,
            "rooms_cleaned": ["living_room", "bedroom", "kitchen"],
            "errors": [
                {"type": "stuck", "count": 2},
                {"type": "low_battery", "count": 1},
            ],
            "consumable_status": {
                "main_brush_hours": 120,
                "side_brush_hours": 85,
                "filter_hours": 200,
                "sensor_cleanliness": "good",
            },
            "compared_to_last_month": {
                "missions_change_percent": 12,
                "coverage_change_percent": 3.2,
            },
        }
