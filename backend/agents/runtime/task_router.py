"""指令路由：区分查询类和操作类指令"""
# 查询类关键词 → 走 ReAct 循环（LLM 调工具回答）
_QUERY_PATTERNS = [
    "几点了", "时间", "今天", "天气", "面积", "多大", "平方",
    "扫完", "覆盖率", "进度", "最大", "最小", "哪个", "怎么", "如何",
    "偏好", "习惯", "记住", "确认", "确定", "房间", "计算", "算一下",
    "估计", "多少", "等于",
]

# 动作类关键词 → 直接走 Planner（不经过 ReAct，避免不必要的 LLM 往返）
_ACTION_PATTERNS = ["清扫", "导航", "回充", "停止", "清洁", "打扫"]


def is_simple_query(cmd: str) -> bool:
    """判断是否为查询类指令（应走 ReAct 工具链）"""
    c = cmd.lower()
    return any(p in c for p in _QUERY_PATTERNS)


def is_action_command(cmd: str) -> bool:
    """判断是否为操作类指令（应直接走 Planner，跳过 ReAct）"""
    c = cmd.lower()
    return any(p in c for p in _ACTION_PATTERNS)


def route(cmd: str) -> str:
    """路由决策：tool=走ReAct | planner=直接规划"""
    if is_action_command(cmd):
        return "planner"
    if is_simple_query(cmd):
        return "tool"
    return "planner"  # 默认走 Planner