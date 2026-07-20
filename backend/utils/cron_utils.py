"""定时任务服务：Cron 解析 + 下次运行时间计算"""
from datetime import datetime, timedelta
from typing import List, Optional


# ── Cron 解析 ──
def matches_cron(expr: str, dt: Optional[datetime] = None) -> bool:
    """
    检查当前时间是否匹配 cron 表达式。
    支持格式: minute hour day month weekday
    weekday: 0=Sunday ~ 6=Saturday（Cron 标准）
    支持 */N 步进语法: "*/5 * * * *" = 每5分钟
    """
    if dt is None:
        dt = datetime.now()
    parts = expr.strip().split()
    if len(parts) != 5:
        return False

    # Cron weekday: 0=Sunday, 6=Saturday
    # datetime.weekday(): 0=Monday, 6=Sunday
    # 转换: cron_weekday → (cron_weekday + 1) % 7 for Monday-based
    cron_wday = parts[4]
    py_wday = (dt.weekday() + 1) % 7  # Monday=0 → Sunday=0, Monday=1, ..., Saturday=6

    values = {
        "minute": dt.minute,
        "hour": dt.hour,
        "day": dt.day,
        "month": dt.month,
        "weekday": py_wday,
    }

    for field, value in zip(["minute", "hour", "day", "month", "weekday"], parts):
        if value == "*":
            continue
        if value.startswith("*/"):
            step = int(value[2:])
            if step <= 0:
                return False
            actual = values[field]
            if actual % step != 0:
                return False
        elif "," in value:
            # 逗号分隔: "1,3,5"
            try:
                allowed = {int(x.strip()) for x in value.split(",")}
            except ValueError:
                return False
            if values[field] not in allowed:
                return False
        elif "-" in value:
            # 范围: "1-5"
            try:
                start, end = value.split("-")
                if values[field] < int(start) or values[field] > int(end):
                    return False
            except ValueError:
                return False
        else:
            try:
                if int(value) != values[field]:
                    return False
            except ValueError:
                return False
    return True


def compute_next_run(expr: str, from_dt: Optional[datetime] = None) -> Optional[datetime]:
    """
    计算 cron 表达式的下一个触发时间。
    从 from_dt 开始（不含），向后逐分钟搜索，最多搜 366 天。
    """
    if from_dt is None:
        from_dt = datetime.now()
    dt = from_dt + timedelta(minutes=1)
    max_iterations = 366 * 24 * 60  # 一年
    for _ in range(max_iterations):
        if matches_cron(expr, dt):
            return dt
        dt += timedelta(minutes=1)
    return None


def validate_cron(expr: str) -> Optional[str]:
    """验证 cron 表达式，返回错误信息或 None"""
    parts = expr.strip().split()
    if len(parts) != 5:
        return "Cron 表达式必须包含 5 个字段: 分 时 日 月 周"
    try:
        for part in parts:
            if part == "*":
                continue
            if part.startswith("*/"):
                int(part[2:])
            elif "," in part:
                for x in part.split(","):
                    int(x.strip())
            elif "-" in part:
                start, end = part.split("-")
                int(start); int(end)
            else:
                int(part)
    except ValueError:
        return f"Cron 字段格式错误: {part}"
    # 检查是否能找到下次运行时间
    next_run = compute_next_run(expr)
    if next_run is None:
        return "无法计算下次运行时间，请检查 cron 表达式"
    return None
