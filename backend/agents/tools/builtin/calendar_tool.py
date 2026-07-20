"""日历工具：通过 CalDAV/Google API 查询日程"""
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from backend.agents.tools.base_tool import BaseTool, ToolResult
from backend.utils.logger_handler import logger


class CalendarTool(BaseTool):
    """查询日历日程信息，支持 CalDAV 和 Google Calendar API。"""

    name = "calendar"
    description = "查询日历日程，支持今天、明天、本周或指定日期的日程查看"
    parameters = {
        "query_type": {
            "type": "string",
            "enum": ["today", "tomorrow", "this_week", "date_range", "all"],
            "description": "查询类型：today=今天, tomorrow=明天, this_week=本周, date_range=指定日期范围, all=近期所有日程",
            "required": True,
        },
        "start_date": {
            "type": "string",
            "description": "起始日期（date_range 时必填），格式 YYYY-MM-DD",
        },
        "end_date": {
            "type": "string",
            "description": "结束日期（date_range 时必填），格式 YYYY-MM-DD",
        },
        "max_results": {
            "type": "integer",
            "description": "最大返回条数，默认 10",
        },
    }

    def __init__(
        self,
        caldav_url: Optional[str] = None,
        caldav_user: Optional[str] = None,
        caldav_password: Optional[str] = None,
        google_creds: Optional[Any] = None,
    ):
        """
        Args:
            caldav_url: CalDAV 服务器 URL（可选）
            caldav_user: CalDAV 用户名
            caldav_password: CalDAV 密码
            google_creds: Google Calendar 认证凭据（可选）
        """
        self._caldav_url = caldav_url
        self._caldav_user = caldav_user
        self._caldav_password = caldav_password
        self._google_creds = google_creds

    async def execute(
        self,
        query_type: str = "today",
        start_date: str = "",
        end_date: str = "",
        max_results: int = 10,
        **kwargs,
    ) -> ToolResult:
        try:
            now = datetime.now()
            today = now.date()

            if query_type == "today":
                start = today
                end = today
            elif query_type == "tomorrow":
                start = today + timedelta(days=1)
                end = start
            elif query_type == "this_week":
                start = today - timedelta(days=today.weekday())
                end = start + timedelta(days=6)
            elif query_type == "date_range":
                if not start_date or not end_date:
                    return ToolResult(success=False, error="date_range 查询需要提供 start_date 和 end_date")
                start = date.fromisoformat(start_date)
                end = date.fromisoformat(end_date)
            elif query_type == "all":
                start = today
                end = today + timedelta(days=14)
            else:
                return ToolResult(success=False, error=f"不支持的查询类型: {query_type}")

            if self._google_creds is not None:
                return await self._query_google_calendar(start, end, max_results)
            elif self._caldav_url:
                return await self._query_caldav(start, end, max_results)
            else:
                return self._simulate_query(start, end, query_type)

        except Exception as e:
            logger.error(f"Calendar tool failed: {e}")
            return ToolResult(success=False, error=f"日历查询失败: {e}")

    async def _query_google_calendar(self, start: date, end: date, max_results: int) -> ToolResult:
        try:
            from googleapiclient.discovery import build

            service = build("calendar", "v3", credentials=self._google_creds)
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=datetime.combine(start, datetime.min.time()).isoformat() + "Z",
                    timeMax=datetime.combine(end, datetime.max.time()).isoformat() + "Z",
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])

            if not events:
                return ToolResult(success=True, data={"answer": f"{start} 至 {end} 暂无日程安排", "events": []})

            lines: List[str] = []
            for e in events:
                summary = e.get("summary", "无标题")
                start_time = e["start"].get("dateTime", e["start"].get("date", ""))
                lines.append(f"- {start_time} {summary}")

            return ToolResult(success=True, data={
                "answer": f"{start} 至 {end} 共 {len(events)} 项日程:\n" + "\n".join(lines),
                "events": events,
                "count": len(events),
            })

        except ImportError:
            return ToolResult(success=False, error="Google Calendar API 库未安装 (pip install google-api-python-client)")
        except Exception as e:
            return ToolResult(success=False, error=f"Google Calendar 查询失败: {e}")

    async def _query_caldav(self, start: date, end: date, max_results: int) -> ToolResult:
        try:
            import caldav

            client = caldav.DAVClient(
                url=self._caldav_url,
                username=self._caldav_user,
                password=self._caldav_password,
            )
            principal = client.principal()
            calendars = principal.calendars()

            if not calendars:
                return ToolResult(success=True, data={"answer": "未找到日历", "events": []})

            cal = calendars[0]
            events = cal.date_search(start=start, end=end)
            results = events[:max_results]

            lines: List[str] = []
            for ev in results:
                lines.append(f"- {ev.data}")

            return ToolResult(success=True, data={
                "answer": f"{start} 至 {end} 共 {len(results)} 项日程:\n" + "\n".join(lines),
                "events": results,
                "count": len(results),
            })

        except ImportError:
            return ToolResult(success=False, error="CalDAV 库未安装 (pip install caldav)")
        except Exception as e:
            return ToolResult(success=False, error=f"CalDAV 查询失败: {e}")

    def _simulate_query(self, start: date, end: date, query_type: str) -> ToolResult:
        period_label = f"{start} ~ {end}"
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        events: List[Dict[str, str]] = []
        current = start
        while current <= end:
            if current.weekday() < 5:
                events.append({
                    "date": current.isoformat(),
                    "time": "10:00",
                    "summary": "待办事项",
                    "weekday": weekday_names[current.weekday()],
                })
            current += timedelta(days=1)

        if not events:
            return ToolResult(success=True, data={
                "answer": f"{period_label} 暂无日程安排",
                "events": [],
                "simulated": True,
            })

        lines = [f"{period_label} 共 {len(events)} 项日程（模拟数据）:"]
        for ev in events:
            lines.append(f"- {ev['date']}({ev['weekday']}) {ev['time']} {ev['summary']}")

        return ToolResult(success=True, data={
            "answer": "\n".join(lines),
            "events": events,
            "count": len(events),
            "simulated": True,
        })
