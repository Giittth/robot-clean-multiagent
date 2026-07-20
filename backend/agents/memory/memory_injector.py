"""记忆注入工具：把记忆格式化成 LLM prompt 片段"""
from backend.agents.memory.agent_memory import AgentMemory


def build_relevant_context(memory: AgentMemory) -> str:
    """从 AgentMemory 提取相关记忆，格式化为 prompt 片段"""
    working = memory.working
    if not working.user_command:
        return ""
    parts = ["[当前状态]"]
    parts.append(working.get_summary())
    recent = working.get_recent_turns(3)
    if recent:
        parts.append("")
        for t in recent:
            obs = t.observation[:60] if t.observation else ""
            parts.append(f"  step {t.step}: {t.action} -> {obs}")
    return "\n".join(parts)


def format_context_block(title: str, content: str) -> str:
    """格式化一个上下文块"""
    if not content:
        return ""
    return f"\n{title}\n{content}\n"