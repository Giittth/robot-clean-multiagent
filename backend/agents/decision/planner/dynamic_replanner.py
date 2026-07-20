"""
动态重规划器：在任务失败时生成补丁图并合并到当前图。
"""

from backend.agents.decision.runtime.task_graph import TaskGraph, EdgeType
from backend.agents.decision.runtime.graph_executor import GraphExecutor
from backend.agents.decision.planner.base_planner import BasePlanner
from backend.agents.decision.planner.planner_context import PlannerContext
from backend.models.task.task import TaskState, TaskType
from backend.agents.core.event.event_router import EventRouter
from backend.utils.logger_handler import logger


class DynamicReplanner:
    def __init__(self, planner: BasePlanner, event_router: EventRouter):
        """
        :param planner: 用于生成补丁图的规划器
        :param event_router: 用于发送重规划完成事件（触发 GraphExecutor 重新调度）
        """
        self.planner = planner
        self.event_router = event_router

    async def on_task_failure(
        self,
        executor: GraphExecutor,
        failed_task_id: str,
        context: PlannerContext
    ) -> bool:
        """
        任务失败时的重规划入口。
        返回 True 表示成功生成补丁并合并，False 表示失败。
        """
        current_graph = executor.graph
        if executor.context.task_status.get(failed_task_id) != TaskState.FAILED:
            logger.warning(f"Task {failed_task_id} is not failed, cannot replan")
            return False

        logger.info(f"Dynamic replan triggered for failed task {failed_task_id}")

        try:
            # 调用规划器的 replan 方法生成补丁图
            patch_graph = await self.planner.replan(current_graph, failed_task_id, context)
            if not patch_graph or not patch_graph.tasks:
                logger.warning("Planner returned empty patch, using fallback recovery")
                patch_graph = self._create_fallback_recovery_graph()
        except NotImplementedError:
            logger.warning("Planner does not support replan, using fallback recovery")
            patch_graph = self._create_fallback_recovery_graph()
        except Exception as e:
            logger.error(f"Replan error: {e}, using fallback")
            patch_graph = self._create_fallback_recovery_graph()

        # 合并补丁图到当前图
        self._merge_graph(current_graph, patch_graph, failed_task_id)

        # 将失败任务标记为 SKIPPED（避免影响依赖任务）
        executor.context.update_task_status(failed_task_id, TaskState.SKIPPED)

        # 通知执行器重新计算就绪任务
        # 方式一：调用 GraphExecutor 新增的公共方法（推荐）
        executor.notify_graph_updated()
        # 方式二：发送一个事件让 GraphExecutor 自己处理（需要 GraphExecutor 订阅）
        # await self.event_router.emit(Event(type="runtime.graph_patched", source="replanner"))

        return True

    def _create_fallback_recovery_graph(self) -> TaskGraph:
        """默认恢复图：插入一个 recovery 任务"""
        graph = TaskGraph()
        recover_task = self._create_recovery_task()
        graph.add_task(recover_task)
        return graph

    def _create_recovery_task(self):
        """创建一个脱困任务（可复用）"""
        from backend.models.task.task import Task
        import uuid
        return Task(
            task_id=f"recover_{uuid.uuid4().hex[:8]}",
            type=TaskType.RECOVER_STUCK,
            params={"method": "backup_and_turn"},
            status=TaskState.PENDING,
            robot_id=self.planner.robot_id,
            required_resources=["motion"],
            max_retries=2,
            retry_delay=1.0,
        )

    def _merge_graph(self, target: TaskGraph, source: TaskGraph, failed_task_id: str):
        """
        将源图的任务和边合并到目标图，并为源图中所有入口任务添加来自失败任务的失败边。
        """
        # 添加所有任务（如果任务ID已存在，跳过）
        for task in source.tasks.values():
            if task.task_id not in target.tasks:
                target.add_task(task)

        # 添加所有边（如果边已存在则跳过）
        existing_edges = {(e.source, e.target, e.type) for e in target.edges}
        for edge in source.edges:
            key = (edge.source, edge.target, edge.type)
            if key not in existing_edges:
                target.add_edge(edge.source, edge.target, edge.type)
                existing_edges.add(key)

        # 找出源图中没有入边的任务（即入口任务），为它们添加从失败任务来的失败边
        source_task_ids = set(source.tasks.keys())
        for tid in source_task_ids:
            if not target.get_incoming_edges(tid):
                # 避免重复添加相同地失败边
                if (failed_task_id, tid, EdgeType.FAILURE) not in existing_edges:
                    target.add_edge(failed_task_id, tid, EdgeType.FAILURE)
                    logger.debug(f"Added failure edge from {failed_task_id} to {tid}")