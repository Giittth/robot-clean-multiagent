from typing import Dict, Any
import re

from backend.utils.logger_handler import logger


class IntentParser:
    @staticmethod
    def parse(command: str) -> Dict[str, Any]:
        """返回标准化意图，例如 {'intent': 'clean_area', 'area': 'living_room'}"""
        cmd_lower = command.lower()
        logger.info(f"IntentParser received command: '{command}' (repr: {repr(command)})")
        # 清扫意图
        if "清扫" in cmd_lower:
            area = "unknown"
            # 注意顺序：更具体的词放在前面，避免误匹配
            if "客厅" in cmd_lower:
                area = "living_room"
            elif "客餐厅" in cmd_lower:
                area = "living_dining"
            elif "主卧" in cmd_lower:
                area = "master_bedroom"
            elif "卧室1" in cmd_lower:
                area = "bedroom1"
            elif "卧室2" in cmd_lower:
                area = "bedroom2"
            elif "卧室" in cmd_lower:
                area = "bedroom"
            elif "厨房" in cmd_lower:
                area = "kitchen"
            elif "卫生间" in cmd_lower:
                area = "bathroom"
            elif "餐厅" in cmd_lower:
                area = "dining_room"
            elif "门厅" in cmd_lower:
                area = "foyer"
            # 北室1-4
            if "北室1" in cmd_lower:
                area = "room_north_1"
            elif "北室2" in cmd_lower:
                area = "room_north_2"
            elif "北室3" in cmd_lower:
                area = "room_north_3"
            elif "北室4" in cmd_lower:
                area = "room_north_4"
            # 南室1-4
            elif "南室1" in cmd_lower:
                area = "room_south_1"
            elif "南室2" in cmd_lower:
                area = "room_south_2"
            elif "南室3" in cmd_lower:
                area = "room_south_3"
            elif "南室4" in cmd_lower:
                area = "room_south_4"
            # 楼梯
            elif "楼梯" in cmd_lower:
                area = "stairs"
            # 厕所
            elif "厕所" in cmd_lower:
                area = "toilet"
            # 走廊
            elif "走廊" in cmd_lower:
                area = "hallway"

            return {"intent": "clean_area", "area": area}
        # 回充意图
        if "回充" in cmd_lower or "返回充电" in cmd_lower:
            return {"intent": "return_to_charge"}
        # 停止意图
        if "停止" in cmd_lower:
            return {"intent": "stop"}
        # 导航意图
        # 简单正则提取坐标
        match = re.search(r"去\s*[([]?(\d+\.?\d*)\s*,\s*(\d+\.?\d*)[)\]]?", cmd_lower)
        if match:
            x = float(match.group(1))
            y = float(match.group(2))
            return {"intent": "navigate_to", "target": {"x": x, "y": y}}
        # 默认探索
        return {"intent": "explore"}