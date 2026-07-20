"""天气查询工具（可选，需配置 API key）"""
from typing import Optional
from backend.agents.tools.base_tool import BaseTool, ToolResult

class WeatherTool(BaseTool):
    """查询指定城市的天气。需要配置 WEATHER_API_KEY 环境变量。"""

    name = "weather"
    description = "查询天气信息，需要城市名"
    parameters = {
        "city": {
            "type": "string",
            "description": "城市名，如 北京、上海、London",
            "required": True,
        }
    }

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key

    async def execute(self, city: str = "", **kw) -> ToolResult:
        if not self._api_key:
            return ToolResult(success=False, error="天气服务未配置（需要 WEATHER_API_KEY）")
        try:
            import aiohttp
            url = f"http://api.openweathermap.org/data/2.5/weather"
            params = {"q": city, "appid": self._api_key, "units": "metric", "lang": "zh_cn"}
            async with aiohttp.ClientSession() as s:
                async with s.get(url, params=params, timeout=10) as r:
                    if r.status != 200:
                        return ToolResult(success=False, error=f"天气查询失败: HTTP {r.status}")
                    data = await r.json()
                    temp = data["main"]["temp"]
                    desc = data["weather"][0]["description"]
                    humidity = data["main"]["humidity"]
                    return ToolResult(success=True, data={
                        "answer": f"{city} 当前天气: {desc}, 温度 {temp}°C, 湿度 {humidity}%",
                        "temperature": temp, "description": desc,
                    })
        except Exception as e:
            return ToolResult(success=False, error=f"天气查询失败: {e}")