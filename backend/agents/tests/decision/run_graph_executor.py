import asyncio
from backend.agents.decision.runtime.graph_context import GraphContext
from backend.agents.decision.runtime.task_graph import TaskGraph, EdgeType
from backend.agents.decision.runtime.graph_executor import GraphExecutor
from backend.agents.core.runtime.resource_manager import ResourceManager
from backend.models.task.task import Task, TaskType

async def main():
    graph = TaskGraph("test")
    t1 = Task(task_id="task1", type=TaskType.NAVIGATE_TO, params={}, robot_id="r1", max_retries=0,
              required_resources=["motion"])
    t2 = Task(task_id="task2", type=TaskType.CLEANING, params={}, robot_id="r1",
              required_resources=["motion", "camera"])
    t3 = Task(task_id="fallback", type=TaskType.RETURN_TO_CHARGE, params={}, robot_id="r1",
              required_resources=["motion"])

    graph.add_task(t1)
    graph.add_task(t2)
    graph.add_task(t3)

    graph.add_edge("task1", "task2", EdgeType.SUCCESS)
    graph.add_edge("task1", "fallback", EdgeType.FAILURE)

    def condition_checker(task: Task, ctx) -> bool:
        if task.task_id == "task2":
            return ctx.get_shared_state("battery", 100) > 20
        return True

    async def exec_cb(task: Task) -> bool:
        print(f"Running {task.task_id}")
        if task.task_id == "task1":
            return False
        return True

    ctx = GraphContext("test")
    ctx.update_shared_state({"battery": 85, "coverage": 30})

    resource_manager = ResourceManager()
    resource_manager.register("motion")
    resource_manager.register("camera")

    executor = GraphExecutor(graph, context=ctx, condition_checker=condition_checker,
                             resource_manager=resource_manager)
    asyncio.create_task(executor.run(exec_cb, max_concurrent=1))
    await executor.wait_completion()
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())