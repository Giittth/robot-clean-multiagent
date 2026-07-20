"""P0 端到端综合测试"""
import sys, os, json, asyncio, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0
errors = []

def test(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}  {detail}")
        errors.append((name, detail))

async def main():
    global passed, failed
    print("=" * 50)
    print("P0 端到端综合测试")
    print("=" * 50)

    # ========== 1. task_router 单元测试 ==========
    print("\n--- 1. task_router 路由测试 ---")
    from backend.agents.runtime.task_router import is_simple_query, route

    test("简单查询: 厨房扫完了吗", is_simple_query("厨房扫完了吗") == True)
    test("简单查询: 客厅多大面积", is_simple_query("客厅多大面积") == True)
    test("简单查询: 怎么清理滚刷", is_simple_query("怎么清理滚刷") == True)
    test("简单查询: 确认开始清扫", is_simple_query("确认开始清扫") == True)
    test("简单指令: 清扫客厅", is_simple_query("清扫客厅") == True)
    test("复杂指令: 先扫卧室再去厨房", is_simple_query("先扫卧室再去厨房") == True)
    test("路由: tool", route("厨房扫完了吗") == "tool")
    test("路由: tool", route("清扫客厅") == "tool")

    # ========== 2. ToolRegistry 单元测试 ==========
    print("\n--- 2. ToolRegistry 注册与格式转换 ---")
    from backend.agents.tools.tool_registry import ToolRegistry
    from backend.agents.tools.builtin.room_query import RoomQueryTool
    from backend.agents.tools.builtin.coverage_query import CoverageQueryTool
    from backend.agents.tools.builtin.knowledge_query import KnowledgeQueryTool
    from backend.agents.tools.builtin.memory_tool import MemoryTool
    from backend.agents.tools.builtin.confirm_tool import ConfirmTool

    reg = ToolRegistry()
    reg.register(RoomQueryTool(lambda: [{"name":"living_room","polygon":[{"x":0,"y":0},{"x":4,"y":0},{"x":4,"y":4},{"x":0,"y":4}]}]))
    reg.register(CoverageQueryTool(lambda: {"coverage_percent": 75.0}))
    reg.register(KnowledgeQueryTool(query_fn=lambda q: "这是测试答案"))
    reg.register(MemoryTool())
    reg.register(ConfirmTool())

    test("5 个工具注册", len(reg.list_tools()) == 5)
    test("list_names", set(reg.list_names()) == {"room_query","coverage_query","knowledge_query","memory","confirm"})
    test("to_openai_tools 格式", len(reg.to_openai_tools()) == 5)
    test("to_openai_tools 含 function", "function" in reg.to_openai_tools()[0])

    # 测试工具执行
    result = await reg.execute("room_query", {"query": "最大房间"})
    test("tool execute 成功", result.success == True)
    test("tool execute 含数据", result.data is not None)
    test("tool execute 含 answer", "answer" in (result.data or {}))

    # ========== 3. memory/working_memory 测试 ==========
    print("\n--- 3. WorkingMemory 测试 ---")
    from backend.agents.memory.working_memory import WorkingMemory, TurnRecord

    wm = WorkingMemory()
    wm.set_task("测试指令")
    test("set_task", wm.user_command == "测试指令")
    wm.update_state(robot_state={"battery": {"voltage": 12.5}})
    summary = wm.get_summary()
    test("get_summary 含电量", "12.5" in summary)
    wm.add_turn(TurnRecord(action="test_tool", action_input={}, observation="ok"))
    test("add_turn 记录历史", len(wm.history) == 1)
    test("get_recent_turns", len(wm.get_recent_turns(3)) == 1)
    test("last_action", wm.last_action() == "test_tool")

    # ========== 4. AgentRuntime ReAct 循环集成测试 ==========
    print("\n--- 4. AgentRuntime ReAct 循环测试 (需 Ollama) ---")
    from backend.llm.factory import LLMClientFactory

    factory = LLMClientFactory({
        "provider": "openai",
        "api_url": "http://localhost:11434/v1/chat/completions",
        "api_key": "",
        "model": "qwen3:8b",
        "timeout": 60, "max_retries": 2,
        "temperature": 0.3, "max_tokens": 4096,
    })
    llm = factory.get_client()

    from backend.agents.memory.agent_memory import AgentMemory
    from backend.agents.runtime.agent_runtime import AgentRuntime

    memory = AgentMemory(user_id=0)
    runtime = AgentRuntime(llm=llm, tools=reg, memory=memory)

    # 测试 1: 简单查询 - "厨房扫完了吗"
    print("\n  Test 4a: run_simple(厨房扫完了吗)")
    try:
        result = await runtime.run_simple("厨房扫完了吗")
        test("4a: run_simple 返回内容", len(result) > 0, f"result={result[:60]}")
        print(f"      回复: {result[:80]}")
    except Exception as e:
        test(f"4a: run_simple 异常", False, str(e)[:80])

    # 测试 2: 测试 run() 返回 AgentResult
    print("\n  Test 4b: run(厨房扫完了吗)")
    try:
        result = await runtime.run("厨房扫完了吗", tool_choice="auto")
        test("4b: action 是 direct_answer", result.action == "direct_answer")
        test("4b: answer 非空", len(result.answer) > 0, f"answer={result.answer[:50]}")
        print(f"      回复: {result.answer[:80]}")
    except Exception as e:
        test(f"4b: run 异常", False, str(e)[:80])

    # ========== 5. react_prompt 测试 ==========
    print("\n--- 5. react_prompt 生成测试 ---")
    from backend.agents.runtime.react_prompt import build_with_tools

    prompt = build_with_tools(["room_query: 查房间", "coverage_query: 查覆盖率"])
    test("prompt 含系统指令", "智能扫地机器人管家" in prompt)
    test("prompt 含工具说明", "room_query" in prompt)
    test("prompt 含 coverage_query", "coverage_query" in prompt)

    # ========== 6. memory_injector 测试 ==========
    print("\n--- 6. memory_injector 测试 ---")
    from backend.agents.memory.memory_injector import build_relevant_context, format_context_block

    memory.working.set_task("厨房扫完了吗")
    memory.working.add_turn(TurnRecord(action="coverage_query", action_input={"area": "kitchen"}, observation="覆盖率75%"))
    ctx = build_relevant_context(memory)
    test("build_relevant_context 含状态", "厨房扫完了吗" in ctx)
    test("build_relevant_context 含历史", "coverage_query" in ctx)
    block = format_context_block("测试", "内容")
    test("format_context_block", "测试" in block and "内容" in block)

    # ========== 7. 5 个工具实例化测试 ==========
    print("\n--- 7. 工具实例化测试 ---")
    try:
        t1 = RoomQueryTool(lambda: [])
        t2 = CoverageQueryTool(lambda: {})
        t3 = KnowledgeQueryTool(query_fn=lambda q: "test")
        t4 = MemoryTool()
        t5 = ConfirmTool()
        test("5 个工具实例化", all([t1, t2, t3, t4, t5]))
    except Exception as e:
        test("5 个工具实例化", False, str(e)[:60])

    # ========== 8. 容器导入测试 ==========
    print("\n--- 8. 容器导入测试 ---")
    try:
        from backend.app.container import SystemContainer
        test("container 导入", True)
        # 不实例化（依赖数据库），只验证导入
    except Exception as e:
        test("container 导入", False, str(e)[:60])

    # ========== 结果汇总 ==========
    print("\n" + "=" * 50)
    total = passed + failed
    print(f"测试结果: {passed}/{total} 通过, {failed} 失败")
    if errors:
        print("\n失败详情:")
        for name, detail in errors:
            print(f"  - {name}: {detail[:100]}")
    print("=" * 50)
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
