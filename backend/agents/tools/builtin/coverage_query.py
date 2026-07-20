"""覆盖率查询工具：全屋/分房间覆盖率、剩余时间预估"""
from typing import Dict, Any, Callable
from backend.agents.tools.base_tool import BaseTool, ToolResult


class CoverageQueryTool(BaseTool):
    """查询清扫覆盖率：全屋或分房间，含剩余时间预估。"""

    name = "coverage_query"
    description = (
        "查询清扫覆盖率。支持全屋和分房间查询，可预估剩余清扫时间。"
        "回答'扫完了吗''客厅扫了多少''还要多久扫完'等问题"
    )
    parameters = {
        "area": {
            "type": "string",
            "description": "房间名（模糊匹配）或 'all'=全屋",
        },
        "detail": {
            "type": "boolean",
            "description": "是否返回分房间详细数据，默认 false",
        },
    }

    def __init__(self, get_coverage_fn: Callable[[], Dict[str, Any]],
                 get_robot_state: Callable[[], Dict[str, Any]] = None):
        self._fn = get_coverage_fn
        self._get_state = get_robot_state

    async def execute(self, area: str = "all", detail: bool = False, **kwargs) -> ToolResult:
        data = self._fn() or {}
        total = data.get("coverage_percent", 0.0)

        if area == "all":
            lines = [f"全屋清扫覆盖率: {total:.1f}%"]
            if total >= 99.5:
                lines.append("已基本清扫完毕")
            elif total >= 80:
                lines.append("大部分区域已清扫")
            elif total > 0:
                lines.append("清扫进行中")

            # 预估剩余时间
            if 0 < total < 99.5 and self._get_state:
                try:
                    state = self._get_state() or {}
                    speed = state.get("velocity", {}).get("linear", 0.3) or 0.3
                    map_size = data.get("map_area", 50.0) or 50.0
                    remaining_area = map_size * (100 - total) / 100.0
                    speed_m2_per_min = speed * 0.6 * 60  # 粗略：速度(m/s) × 扫宽0.6m × 60s
                    if speed_m2_per_min > 0:
                        eta_min = remaining_area / speed_m2_per_min
                        lines.append(f"预估剩余时间: 约 {eta_min:.0f} 分钟")
                except Exception:
                    pass

            # 分房间详情
            if detail:
                room_cov = data.get("room_coverage", {})
                if room_cov:
                    lines.append("\n分房间覆盖率:")
                    for room, cov in sorted(room_cov.items(), key=lambda x: -x[1]):
                        status = "✓" if cov >= 99 else "○" if cov > 0 else "✗"
                        lines.append(f"  {status} {room}: {cov:.1f}%")

            return ToolResult(success=True, data={
                "answer": "\n".join(lines), "coverage": total,
            })

        # 模糊匹配特定房间
        room_cov = data.get("room_coverage", {})
        matched_room, matched_cov = self._match_room(area, room_cov)
        if matched_room:
            return ToolResult(success=True, data={
                "answer": f"{matched_room} 清扫覆盖率: {matched_cov:.1f}%",
                "room": matched_room, "coverage": matched_cov,
            })

        return ToolResult(success=True, data={
            "answer": f"全屋覆盖率 {total:.1f}%（未找到房间 '{area}' 的单独数据）",
            "coverage": total,
        })

    @staticmethod
    def _match_room(query: str, room_cov: Dict[str, float]):
        """模糊匹配房间名"""
        if not room_cov:
            return None, None
        # 直接匹配
        if query in room_cov:
            return query, room_cov[query]
        # 子串匹配
        q = query.lower()
        for room, cov in room_cov.items():
            if q in room.lower() or room.lower() in q:
                return room, cov
        return None, None
