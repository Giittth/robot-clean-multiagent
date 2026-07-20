"""房间查询工具：模糊匹配、面积排序、房间搜索"""
from typing import Dict, Any, List, Callable
from backend.agents.tools.base_tool import BaseTool, ToolResult


class RoomQueryTool(BaseTool):
    """查询房间信息：模糊匹配、面积排序、详细信息。"""

    name = "room_query"
    description = (
        "查询房间信息。支持：列出所有房间、查找特定房间（模糊匹配）、"
        "找最大/最小的房间、查房间面积和位置。"
        "回答'最大的卧室''厨房在哪''几个房间''客厅多大'等问题"
    )
    parameters = {
        "query": {
            "type": "string",
            "description": "查询内容，如：最大的房间、厨房面积、几个房间、客厅在哪、所有房间",
            "required": True,
        },
    }

    def __init__(self, get_rooms_fn: Callable[[], List[Dict[str, Any]]]):
        self._get_rooms = get_rooms_fn

    async def execute(self, query: str = "", **kwargs) -> ToolResult:
        rooms = self._get_rooms()
        if not rooms:
            return ToolResult(success=True, data={"answer": "当前没有加载房间数据，请先加载场景"})

        parsed = [self._parse_room(r) for r in rooms]

        q = query.lower()

        # "最大" / "最小" 的房间
        if "最大" in q:
            largest = max(parsed, key=lambda r: r["area"])
            return ToolResult(success=True, data={
                "answer": f"最大的房间是 {largest['name']}，面积约 {largest['area']:.1f} 平方米",
                "rooms": parsed,
            })
        if "最小" in q:
            smallest = min(parsed, key=lambda r: r["area"])
            return ToolResult(success=True, data={
                "answer": f"最小的房间是 {smallest['name']}，面积约 {smallest['area']:.1f} 平方米",
                "rooms": parsed,
            })

        # "几个" / "多少" 房间
        if "几个" in q or "多少" in q:
            return ToolResult(success=True, data={
                "answer": f"共有 {len(parsed)} 个房间",
                "rooms": parsed,
            })

        # 模糊匹配特定房间名
        matched = self._fuzzy_match(parsed, q)
        if matched:
            if len(matched) == 1:
                r = matched[0]
                return ToolResult(success=True, data={
                    "answer": f"{r['name']}：面积约 {r['area']:.1f} 平方米，中心位置 {r['center']}",
                    "room": r,
                })
            else:
                lines = [f"找到 {len(matched)} 个匹配房间："]
                for r in matched:
                    lines.append(f"  - {r['name']}: {r['area']:.1f} 平方米")
                return ToolResult(success=True, data={"answer": "\n".join(lines)})

        # 默认：列出所有房间
        lines = [f"共有 {len(parsed)} 个房间："]
        for r in parsed:
            lines.append(f"  - {r['name']}: {r['area']:.1f} 平方米, 中心{r['center']}")
        return ToolResult(success=True, data={"answer": "\n".join(lines), "rooms": parsed})

    @staticmethod
    def _parse_room(room: Dict[str, Any]) -> Dict[str, Any]:
        name = room.get("name") or room.get("room_id", "未知")
        polygon = room.get("polygon", [])
        center = room.get("center") or room.get("entry_point", {})
        area = RoomQueryTool._calc_area(polygon) if polygon else 0.0
        return {
            "name": name,
            "area": area,
            "center": center,
            "polygon": polygon,
        }

    @staticmethod
    def _fuzzy_match(rooms: List[Dict], query: str) -> List[Dict]:
        """模糊匹配房间名：支持中英文、部分匹配"""
        name_map = {
            "客厅": ["living_room", "livingroom", "客厅"],
            "厨房": ["kitchen", "厨房"],
            "卧室": ["bedroom", "bed_room", "主卧", "次卧"],
            "主卧": ["master_bedroom", "主卧", "master"],
            "次卧": ["guest_bedroom", "次卧", "guest"],
            "卫生间": ["bathroom", "toilet", "卫生间", "厕所"],
            "走廊": ["hallway", "corridor", "走廊", "过道"],
            "书房": ["study", "书房"],
            "阳台": ["balcony", "阳台"],
            "楼梯": ["stairs", "楼梯"],
        }

        results = []
        for r in rooms:
            name = r["name"].lower()
            for cn_key, aliases in name_map.items():
                if cn_key in query:
                    if any(a in name for a in aliases):
                        results.append(r)
                        break
            if "北室" in query or "北屋" in query:
                if "north" in name:
                    results.append(r)
            elif "南室" in query or "南屋" in query:
                if "south" in name:
                    results.append(r)
            elif "东室" in query or "东屋" in query:
                if "east" in name:
                    results.append(r)
            elif "西室" in query or "西屋" in query:
                if "west" in name:
                    results.append(r)

        # 如果模糊匹配失败，尝试直接子串匹配
        if not results:
            for r in rooms:
                name = r["name"].lower()
                if any(w in name for w in query.split()):
                    results.append(r)

        return results

    @staticmethod
    def _calc_area(polygon: List) -> float:
        if not polygon or len(polygon) < 3:
            return 0.0
        pts = [(p["x"], p["y"]) if isinstance(p, dict) else (p[0], p[1]) if isinstance(p, (list, tuple)) else p for p in polygon]
        n = len(pts)
        area = 0.0
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            area += x1 * y2 - x2 * y1
        return abs(area) / 2.0
