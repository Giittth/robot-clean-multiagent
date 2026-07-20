"""摄像头工具：对接网络摄像头查看现场画面"""
from typing import Optional, Dict, Any
from backend.agents.tools.base_tool import BaseTool, ToolResult
from backend.utils.logger_handler import logger


class CameraTool(BaseTool):
    """对接网络摄像头（IP Camera / RTSP / ONVIF），获取实时画面或截图。"""

    name = "camera"
    description = "查看网络摄像头画面，支持获取实时截图和 RTSP 推流地址"
    parameters = {
        "camera_id": {
            "type": "string",
            "description": "摄像头 ID 或名称，如 living_room、front_door",
            "required": True,
        },
        "action": {
            "type": "string",
            "enum": ["snapshot", "stream_url", "status"],
            "description": "操作类型：snapshot=获取截图, stream_url=获取推流地址, status=查看摄像头在线状态",
            "required": True,
        },
    }

    def __init__(self, camera_configs: Optional[Dict[str, Dict[str, str]]] = None):
        """
        Args:
            camera_configs: 摄像头配置字典
        """
        self._camera_configs = camera_configs or {}

    async def execute(self, camera_id: str = "", action: str = "snapshot", **kwargs) -> ToolResult:
        try:
            config = self._camera_configs.get(camera_id)
            simulated = False
            if config is None:
                logger.info(f"[Camera SIM] camera '{camera_id}' not configured, using simulated data")
                config = self._simulate_config(camera_id)
                simulated = True
            if action == "status":
                return await self._check_status(camera_id, config, simulated)
            elif action == "snapshot":
                return await self._take_snapshot(camera_id, config, simulated)
            elif action == "stream_url":
                return self._get_stream_url(camera_id, config, simulated)
            else:
                return ToolResult(success=False, error=f"不支持的操作: {action}")
        except Exception as e:
            logger.error(f"Camera tool failed: {e}")
            return ToolResult(success=False, error=f"摄像头操作失败: {e}")

    async def _check_status(self, camera_id: str, config: dict, simulated: bool) -> ToolResult:
        if simulated:
            return ToolResult(success=True, data={
                "answer": f"摄像头 {camera_id} 状态：在线（模拟数据）",
                "camera_id": camera_id, "online": True, "simulated": True,
            })
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(config.get("snapshot_url", ""), timeout=5) as resp:
                        online = resp.status == 200
                except Exception:
                    online = False
            status = "在线" if online else "离线"
            return ToolResult(success=True, data={
                "answer": f"摄像头 {camera_id} 状态：{status}",
                "camera_id": camera_id, "online": online,
            })
        except Exception as e:
            return ToolResult(success=False, error=f"摄像头状态检查失败: {e}")

    async def _take_snapshot(self, camera_id: str, config: dict, simulated: bool) -> ToolResult:
        if simulated:
            return ToolResult(success=True, data={
                "answer": f"已获取摄像头 {camera_id} 的实时画面（模拟截图）",
                "camera_id": camera_id,
                "image_url": f"https://via.placeholder.com/640x480?text={camera_id}",
                "simulated": True,
            })
        snapshot_url = config.get("snapshot_url", "")
        if not snapshot_url:
            rtsp_url = config.get("url", "")
            if rtsp_url.startswith("rtsp://"):
                return ToolResult(success=True, data={
                    "answer": f"摄像头 {camera_id} 的 RTSP 流地址已就绪，推荐使用 VLC 或 FFmpeg 查看",
                    "camera_id": camera_id, "stream_url": rtsp_url,
                    "note": "RTSP 流需要外部播放器查看",
                })
            return ToolResult(success=False, error=f"摄像头 {camera_id} 未配置截图 URL 或 RTSP 地址")
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                auth = None
                if config.get("username"):
                    from aiohttp import BasicAuth
                    auth = BasicAuth(config["username"], config.get("password", ""))
                async with session.get(snapshot_url, auth=auth, timeout=10) as resp:
                    if resp.status != 200:
                        return ToolResult(success=False, error=f"截图获取失败: HTTP {resp.status}")
                    return ToolResult(success=True, data={
                        "answer": f"已获取摄像头 {camera_id} 的实时画面",
                        "camera_id": camera_id, "image_url": snapshot_url,
                    })
        except ImportError:
            return ToolResult(success=True, data={
                "answer": f"摄像头 {camera_id} 截图 URL 已就绪: {snapshot_url}",
                "camera_id": camera_id, "image_url": snapshot_url,
            })
        except Exception as e:
            return ToolResult(success=False, error=f"截图获取失败: {e}")

    def _get_stream_url(self, camera_id: str, config: dict, simulated: bool) -> ToolResult:
        stream_url = config.get("url", "")
        if simulated:
            stream_url = f"rtsp://192.168.1.100:554/{camera_id}"
            return ToolResult(success=True, data={
                "answer": f"摄像头 {camera_id} 的 RTSP 推流地址: {stream_url}",
                "camera_id": camera_id, "stream_url": stream_url, "simulated": True,
            })
        if not stream_url:
            return ToolResult(success=False, error=f"摄像头 {camera_id} 未配置流地址")
        return ToolResult(success=True, data={
            "answer": f"摄像头 {camera_id} 的流地址: {stream_url}",
            "camera_id": camera_id, "stream_url": stream_url,
        })

    @staticmethod
    def _simulate_config(camera_id: str) -> Dict[str, str]:
        return {
            "url": f"rtsp://192.168.1.100:554/{camera_id}",
            "type": "rtsp",
            "snapshot_url": f"http://192.168.1.100:8080/snapshot/{camera_id}",
        }
