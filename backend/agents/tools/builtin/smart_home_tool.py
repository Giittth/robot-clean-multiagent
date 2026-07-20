"""智能家居控制工具：通过 HTTP/MQTT 控制灯、空调等设备"""
import json
from typing import Optional, Dict, Any
from backend.agents.tools.base_tool import BaseTool, ToolResult
from backend.utils.logger_handler import logger


class SmartHomeTool(BaseTool):
    """控制智能家居设备，如灯、空调、窗帘等。支持 HTTP API 和 MQTT 协议。"""

    name = "smart_home"
    description = "控制智能家居设备（灯、空调、窗帘等），支持开关、调温、调亮度等操作"
    parameters = {
        "device_type": {
            "type": "string",
            "enum": ["light", "ac", "curtain", "switch"],
            "description": "设备类型：light=灯, ac=空调, curtain=窗帘, switch=通用开关",
            "required": True,
        },
        "action": {
            "type": "string",
            "enum": ["on", "off", "set_temperature", "set_brightness", "open", "close"],
            "description": "操作指令：on=开启, off=关闭, set_temperature=设定温度(仅空调), set_brightness=调亮度(仅灯), open=打开(窗帘), close=关闭(窗帘)",
            "required": True,
        },
        "device_name": {
            "type": "string",
            "description": "设备名称或位置，如 客厅灯、卧室空调",
        },
        "value": {
            "type": "integer",
            "description": "设定值：set_temperature 时填温度(16-30)，set_brightness 时填亮度(1-100)",
        },
    }

    def __init__(self, http_endpoint: Optional[str] = None, mqtt_client: Optional[Any] = None):
        """
        Args:
            http_endpoint: 智能家居 HTTP API 的基础 URL（可选）
            mqtt_client: 已连接的 MQTT 客户端实例（可选）
        """
        self._http_endpoint = http_endpoint
        self._mqtt_client = mqtt_client

    async def execute(
        self,
        device_type: str = "",
        action: str = "",
        device_name: str = "",
        value: Optional[int] = None,
        **kwargs,
    ) -> ToolResult:
        try:
            if action in ("set_temperature",) and value is None:
                return ToolResult(success=False, error="set_temperature 操作需要提供 value 参数（温度值）")
            if action == "set_brightness" and value is None:
                return ToolResult(success=False, error="set_brightness 操作需要提供 value 参数（亮度值）")
            if action == "set_temperature" and (value < 16 or value > 30):
                return ToolResult(success=False, error="空调温度应在 16-30°C 之间")
            if action == "set_brightness" and (value < 1 or value > 100):
                return ToolResult(success=False, error="亮度应在 1-100 之间")

            if self._mqtt_client is not None:
                return await self._control_via_mqtt(device_type, action, device_name, value)
            elif self._http_endpoint:
                return await self._control_via_http(device_type, action, device_name, value)
            else:
                logger.info(f"[SmartHome SIM] {action} {device_type}({device_name}) value={value}")
                return ToolResult(success=True, data={
                    "answer": f"已{self._action_label(action)} {device_name or device_type}",
                    "simulated": True,
                })

        except Exception as e:
            logger.error(f"SmartHome tool failed: {e}")
            return ToolResult(success=False, error=f"智能家居控制失败: {e}")

    async def _control_via_http(self, device_type: str, action: str, device_name: str, value: Optional[int]) -> ToolResult:
        import aiohttp
        payload: Dict[str, Any] = {
            "device_type": device_type,
            "action": action,
            "device_name": device_name,
        }
        if value is not None:
            payload["value"] = value

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._http_endpoint}/api/device/control",
                json=payload,
                timeout=10,
            ) as resp:
                if resp.status != 200:
                    return ToolResult(success=False, error=f"HTTP 控制失败: HTTP {resp.status}")
                data = await resp.json()
                return ToolResult(success=True, data={
                    "answer": f"已{self._action_label(action)} {device_name or device_type}",
                    "raw": data,
                })

    async def _control_via_mqtt(self, device_type: str, action: str, device_name: str, value: Optional[int]) -> ToolResult:
        topic = f"home/{device_type}/{device_name or 'default'}/command"
        payload: Dict[str, Any] = {"action": action}
        if value is not None:
            payload["value"] = value

        try:
            if hasattr(self._mqtt_client, "publish"):
                if hasattr(self._mqtt_client.publish, "__await__"):
                    await self._mqtt_client.publish(topic, json.dumps(payload))
                else:
                    self._mqtt_client.publish(topic, json.dumps(payload))
            else:
                return ToolResult(success=False, error="MQTT 客户端不支持 publish 方法")

            return ToolResult(success=True, data={
                "answer": f"已通过 MQTT {self._action_label(action)} {device_name or device_type}",
                "topic": topic,
            })
        except Exception as e:
            return ToolResult(success=False, error=f"MQTT 发送失败: {e}")

    @staticmethod
    def _action_label(action: str) -> str:
        labels = {
            "on": "打开", "off": "关闭",
            "set_temperature": "设定温度",
            "set_brightness": "调节亮度",
            "open": "打开", "close": "关闭",
        }
        return labels.get(action, action)
