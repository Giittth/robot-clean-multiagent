"""报告生成工具：一站式生成个人使用报告"""
from datetime import datetime
from backend.agents.tools.base_tool import BaseTool, ToolResult
from backend.utils.prompt_loader import load_report_prompts
from backend.llm.base import BaseLLMClient
from typing import Optional, Callable


class GenerateReportTool(BaseTool):
    """为用户生成扫地/拖地机器人个人使用报告与保养建议"""

    name = "generate_report"
    description = "生成个人使用报告：查询用户在某个月份的机器人使用数据，生成完整的使用情况报告与保养建议"
    parameters = {
        "month": {
            "type": "string",
            "description": "月份，严格遵循 YYYY-MM 格式，如不传则默认当前月份",
            "required": False,
        },
    }

    def __init__(
        self,
        llm_client: BaseLLMClient,
        query_usage_fn: Optional[Callable] = None,
        get_user_id_fn: Optional[Callable[[], str]] = None,
        get_context_fn: Optional[Callable[[], str]] = None,
        get_memory_fn: Optional[Callable[[], str]] = None,
    ):
        self._llm = llm_client
        self._query_usage = query_usage_fn
        self._get_user_id = get_user_id_fn or (lambda: "0")
        self._get_context = get_context_fn or (lambda: "")
        self._get_memory = get_memory_fn or (lambda: "")

    async def execute(self, month: str = "", **kwargs) -> ToolResult:
        try:
            # 1. 确定用户 ID
            user_id = self._get_user_id()

            # 2. 确定月份
            if not month:
                month = datetime.now().strftime("%Y-%m")

            # 3. 查询使用数据
            usage_data = None
            if self._query_usage:
                usage_data = await self._query_usage(user_id, month)
            else:
                usage_data = self._mock_data(user_id, month)

            # 4. 获取对话上下文
            history = self._get_context()
            memory = self._get_memory()

            # 5. 加载 report prompt 模板并填充
            report_template = load_report_prompts()
            filled_prompt = report_template.format(
                history=history,
                memory=memory,
                input=f"请为用户 {user_id} 生成 {month} 月的使用报告",
            )

            # 6. 将使用数据附加到 prompt 尾部
            import json
            data_str = json.dumps(usage_data, ensure_ascii=False, indent=2)
            filled_prompt += f"\n\n### 用户使用数据\n```json\n{data_str}\n```"

            # 7. 调用 LLM 生成报告
            system = "你是一份专业的扫地/拖地机器人方面的报告写手。请根据提供的数据，生成一份完整的使用报告和保养建议。"
            report = await self._llm.generate(filled_prompt, system=system)

            return ToolResult(success=True, data={
                "answer": report,
                "report": report,
                "user_id": user_id,
                "month": month,
            })

        except Exception as e:
            return ToolResult(success=False, error=f"报告生成失败: {e}")

    @staticmethod
    def _mock_data(user_id: str, month: str) -> dict:
        """模拟使用数据（query_usage_fn 未配置时使用）"""
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
