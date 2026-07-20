"""内置工具模块，集中导出所有内置工具类"""

from backend.agents.tools.builtin.smart_home_tool import SmartHomeTool
from backend.agents.tools.builtin.calendar_tool import CalendarTool
from backend.agents.tools.builtin.cloud_storage_tool import CloudStorageTool
from backend.agents.tools.builtin.camera_tool import CameraTool
from backend.agents.tools.builtin.tts_notify_tool import TTSNotifyTool
from backend.agents.tools.builtin.timer_tool import TimerTool
from backend.agents.tools.builtin.get_user_id_tool import GetUserIdTool
from backend.agents.tools.builtin.get_current_month_tool import GetCurrentMonthTool
from backend.agents.tools.builtin.fetch_external_data_tool import FetchExternalDataTool
from backend.agents.tools.builtin.fill_context_for_report_tool import FillContextForReportTool
from backend.agents.tools.builtin.generate_report_tool import GenerateReportTool

__all__ = [
    "SmartHomeTool",
    "CalendarTool",
    "CloudStorageTool",
    "CameraTool",
    "TTSNotifyTool",
    "TimerTool",
    "GetUserIdTool",
    "GetCurrentMonthTool",
    "FetchExternalDataTool",
    "FillContextForReportTool",
    "GenerateReportTool",
]
