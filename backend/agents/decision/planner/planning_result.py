"""
规划器（Planner）返回的结果封装类，用于统一规划输出格式
让 PlannerManager 可以统一处理不同规划器的输出，并支持 fallback 逻辑（例如 LLM 规划失败时自动切换到规则规划器）
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from backend.agents.decision.runtime.task_graph import TaskGraph

@dataclass
class PlanningResult:
    graph: TaskGraph        # 生成的TaskGraph任务图
    planner_name: str       # 生成该图的规划器名称（如"rule"、"llm"）
    success: bool = True    # 规划是否成功（True / False）
    warnings: List[str] = field(default_factory=list)       # 规划过程中的警告信息列表（如忽略未知任务类型、部分依赖缺失等）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据（如使用的意图、LLM原始输出等）
