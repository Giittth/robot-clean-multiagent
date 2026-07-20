"""Agent Runtime：ReAct 循环 Think -> Act -> Observe -> Remember"""
import json
import asyncio
from typing import Optional
from backend.llm.base import BaseLLMClient
from backend.agents.tools.tool_registry import ToolRegistry
from backend.agents.memory.agent_memory import AgentMemory
from backend.agents.memory.working_memory import TurnRecord
from backend.agents.runtime.react_prompt import build_with_tools
from backend.utils.logger_handler import logger


class AgentResult:
    def __init__(self, action="direct_answer", answer="", graph=None, messages=None):
        self.action = action
        self.answer = answer
        self.graph = graph
        self.messages = messages or []


class AgentRuntime:
    """ReAct 循环"""

    MAX_STEPS = 8
    MAX_TOOLS_PER_STEP = 3  # 单步最多调用的工具数，防止 LLM 一次全调导致系统过载
    LLM_RETRIES = 2

    def __init__(self, llm: BaseLLMClient, tools: ToolRegistry, memory: AgentMemory):
        self.llm = llm
        self.tools = tools
        self.memory = memory

    async def run(self, cmd: str, tool_choice: str = "auto") -> AgentResult:
        self.memory.working.set_task(cmd)
        ctx = await self.memory.build_context(cmd)

        descs = [f"{t.name}: {t.description}" for t in self.tools.list_tools()]
        system = build_with_tools(descs)
        if ctx:
            system += f"\n\n参考信息:\n{ctx}"

        msgs = [
            {"role": "system", "content": system},
            {"role": "user", "content": cmd},
        ]
        td = self.tools.to_openai_tools() if self.tools.list_tools() else None

        for step in range(self.MAX_STEPS):
            logger.info(f"ReAct step {step}")

            resp = await self._chat_with_retry(msgs, td, step)
            if resp is None:
                return AgentResult(action="error", answer="LLM调用多次失败，请稍后重试")

            tool_calls = resp.get("tool_calls") or []
            if tool_calls:
                if len(tool_calls) > self.MAX_TOOLS_PER_STEP:
                    logger.warning(
                        f"LLM requested {len(tool_calls)} tools, limiting to {self.MAX_TOOLS_PER_STEP}"
                    )
                    tool_calls = tool_calls[:self.MAX_TOOLS_PER_STEP]

                for call in tool_calls:
                    r = await self._execute_one_call(call, msgs, step)
                    if r is not None:
                        return r  # call_planner returned a graph
                continue

            # LLM 直接回答（无 tool_call）
            answer = resp.get("content", "")
            await self._store_episode(True, answer[:100])
            return AgentResult(action="direct_answer", answer=answer, messages=msgs)

        await self._store_episode(False, "max_steps")
        return AgentResult(action="max_steps", answer="已达到最大思考步数，请简化指令")

    async def _chat_with_retry(self, msgs, tools, step):
        """LLM 调用带重试"""
        last_error = ""
        for attempt in range(self.LLM_RETRIES + 1):
            try:
                kwargs = {"temperature": 0.3, "max_tokens": 2048}
                if tools:
                    kwargs["tools"] = tools
                return await self.llm.chat(msgs, **kwargs)
            except Exception as e:
                last_error = str(e)
                logger.warning(f"LLM step {step} attempt {attempt+1} failed: {last_error}")
                if attempt < self.LLM_RETRIES:
                    await asyncio.sleep(1.0)
        logger.error(f"LLM step {step} all retries exhausted: {last_error}")
        return None

    async def _execute_one_call(self, call, msgs, step):
        """执行单个 tool call，返回 AgentResult 或 None"""
        func = call.get("function", {})
        name = func.get("name", "unknown")

        # 安全解析参数
        raw_args = func.get("arguments", "{}")
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args if isinstance(raw_args, dict) else {})
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Tool args parse failed for {name}: {str(raw_args)[:100]}")
            args = {}

        # 执行工具
        try:
            r = await self.tools.execute(name, args)
        except Exception as e:
            logger.error(f"Tool {name} execution error: {e}")
            r = None

        # 提取 observation（安全处理 data=None）
        if r is not None:
            if r.data and isinstance(r.data, dict):
                obs = r.data.get("answer", str(r.data))
            elif r.data:
                obs = str(r.data)
            else:
                obs = r.error or ""
        else:
            obs = f"工具 {name} 执行失败"

        msgs.append({"role": "assistant", "content": None, "tool_calls": [call]})
        msgs.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": obs})

        self.memory.working.add_turn(
            TurnRecord(action=name, action_input=args, observation=obs, step=step)
        )

        # call_planner 返回 graph 时直接退出
        if name == "call_planner" and r and r.success and r.data and isinstance(r.data, dict) and r.data.get("graph"):
            return AgentResult(
                action="execute_graph",
                answer=r.data.get("answer", ""),
                graph=r.data["graph"],
                messages=msgs,
            )
        return None

    async def _store_episode(self, success: bool, summary: str):
        """安全存储情景记忆"""
        if hasattr(self.memory, 'episodic') and self.memory.episodic:
            try:
                await self.memory.episodic.store_task(
                    self.memory.working.user_command, success, summary
                )
            except Exception:
                pass

    async def run_simple(self, cmd: str) -> str:
        result = await self.run(cmd, tool_choice="auto")
        return result.answer
