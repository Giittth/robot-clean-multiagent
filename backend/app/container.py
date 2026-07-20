"""System Container: dependency injection and lifecycle management."""

import asyncio
from typing import List, Any

from backend.agents.core.messaging.message_bus import MessageBus
from backend.agents.core.event.event_router import EventRouter
from backend.agents.core.lifecycle.registry import AgentRegistry
from backend.agents.core.runtime.resource_manager import ResourceManager
from backend.agents.simulation.environment import SimulationEnvironment
from backend.hardware.simulated_driver import SimulatedDriver

from backend.agents.implementations.perception_agent import PerceptionAgent
from backend.agents.implementations.navigation_agent import NavigationAgent
from backend.agents.implementations.rl_navigation_agent import RLNavigationAgent
from backend.agents.implementations.execution_agent import ExecutionAgent
from backend.agents.implementations.supervisor_agent import SupervisorAgent
from backend.agents.implementations.world_model_agent import WorldModelAgent

from backend.agents.decision.planner import PlannerManager, RulePlanner
from backend.agents.decision.planner.llm_planner import LLMPlanner
from backend.agents.decision.planner.post_processor import PlanningPostProcessor
from backend.agents.utils.rag_tool import RAGTool

from backend.services.state.frontend_state_builder import FrontendStateBuilder
from backend.services.state.robot_state_aggregator import RobotStateAggregator
from backend.services.websocket.robot_ws_service import RobotWebSocketService

from backend.llm.factory import LLMClientFactory

from backend.utils.logger_handler import logger
from backend.agents.schemas.messages import MessageType
from backend.agents.tools.tool_registry import ToolRegistry
from backend.agents.tools.builtin.room_query import RoomQueryTool
from backend.agents.tools.builtin.coverage_query import CoverageQueryTool
from backend.agents.tools.builtin.knowledge_query import KnowledgeQueryTool
from backend.agents.tools.builtin.memory_tool import MemoryTool
from backend.agents.tools.builtin.confirm_tool import ConfirmTool
from backend.agents.tools.builtin.calc_tool import CalcTool
from backend.agents.tools.builtin.weather_tool import WeatherTool
from backend.agents.tools.builtin.notify_tool import NotifyTool
from backend.agents.tools.builtin import TTSNotifyTool
from backend.agents.tools.builtin.robot_status import RobotStatusTool
from backend.agents.tools.builtin.task_control import TaskControlTool
from backend.agents.tools.builtin.time_tool import TimeTool
from backend.agents.tools.builtin.call_planner import CallPlannerTool
from backend.agents.tools.builtin.search_memory import SearchMemoryTool
from backend.agents.tools.builtin.ask_user import AskUserTool
from backend.agents.tools.builtin.reflect_on_failure import ReflectOnFailureTool
from backend.agents.tools.builtin.update_knowledge import UpdateKnowledgeTool
from backend.agents.tools.builtin.get_user_id_tool import GetUserIdTool
from backend.agents.tools.builtin.get_current_month_tool import GetCurrentMonthTool
from backend.agents.tools.builtin.fetch_external_data_tool import FetchExternalDataTool
from backend.agents.tools.builtin.fill_context_for_report_tool import FillContextForReportTool
from backend.agents.tools.builtin.generate_report_tool import GenerateReportTool
from backend.agents.memory.episodic_memory import EpisodicMemory
from backend.rag.long_term_memory import LongTermMemory
from backend.agents.decision.planner.planner_context import PlannerContext, PlanningPolicy
from backend.agents.memory.agent_memory import AgentMemory
from backend.agents.runtime.agent_runtime import AgentRuntime
from backend.services.scheduler.scheduler_service import SchedulerService

from backend.config import settings


class SystemContainer:
    def __init__(self):
        # ----- Infrastructure -----
        self.bus = MessageBus()
        self.event_router = EventRouter()
        self.registry = AgentRegistry()
        self.resource_manager = ResourceManager()
        self.resource_manager.register("motion")

        # ----- LLM client factory -----
        llm_config = {
            "provider": "openai",
            "api_url": f"{settings.base_url}/v1/chat/completions",
            "api_key": "",
            "model": settings.model_name,
            "timeout": 60,
            "max_retries": 2,
            "temperature": 0.1,
            "max_tokens": 4096,
        }
        self.llm_factory = LLMClientFactory(llm_config)
        self.llm_client = self.llm_factory.get_client()

        # ----- RAG tool -----
        self.rag_tool = RAGTool(user_id=0, kb_id=1, llm_client=self.llm_client)

        # ----- Planners -----
        self.rule_planner = RulePlanner(robot_id="robot_001")
        self.llm_planner = LLMPlanner(llm_client=self.llm_client)
        post_processor = PlanningPostProcessor(battery_threshold=11.0)
        self.planner_manager = PlannerManager(
            planners=[self.llm_planner, self.rule_planner],
            post_processor=post_processor,
        )

        # ----- Agent tools (ReAct) -----
        _shared_ltm = LongTermMemory(user_id=0)

        self.tool_registry = ToolRegistry()
        self.tool_registry.register_many(
            RoomQueryTool(get_rooms_fn=lambda: getattr(self.supervisor, 'room_names', [])),
            CoverageQueryTool(get_coverage_fn=lambda: self.supervisor.latest_world_model if hasattr(self.supervisor, 'latest_world_model') else {}),
            KnowledgeQueryTool(query_fn=self.rag_tool.query if hasattr(self.rag_tool, 'query') else None),
            MemoryTool(
                save_fn=lambda c: self.agent_memory.save_preference(c) if hasattr(self, 'agent_memory') else None,
                query_fn=lambda q: self.agent_memory.query_knowledge(q) if hasattr(self, 'agent_memory') else None,
            ),
            ConfirmTool(),
            SearchMemoryTool(episodic_memory=self.agent_memory.episodic if hasattr(self, 'agent_memory') and hasattr(self.agent_memory, 'episodic') else None),
            AskUserTool(),
            ReflectOnFailureTool(llm_client=self.llm_client),
            UpdateKnowledgeTool(long_term_memory=_shared_ltm),
            CalcTool(),
            RobotStatusTool(
                get_robot_state=lambda: getattr(self.supervisor, 'latest_robot_state', {}),
                get_power_state=lambda: getattr(self.execution, 'power_state', 'OFF').value if hasattr(getattr(self, 'execution', None), 'power_state') else 'OFF',
            ),
            TaskControlTool(
                send_control=lambda action: self.bus.publish(
                    type=MessageType.TASK_CONTROL, source="agent_runtime",
                    payload={"command": action},
                ) if hasattr(self, 'bus') else None,
            ),
            TimeTool(
                get_last_episodic=None,
                get_schedules=None,
            ),
            WeatherTool(),
            CallPlannerTool(
                planner_manager=self.planner_manager,
                make_context_fn=lambda cmd: PlannerContext(
                    robot_id="robot_001",
                    user_command=cmd,
                    world_state=getattr(getattr(self, "supervisor", None), "latest_world_model", {}),
                    robot_state=getattr(getattr(self, "supervisor", None), "latest_robot_state", {}),
                    rooms=getattr(getattr(self, "supervisor", None), "room_names", []),
                ),
            ),
        )
        self.tool_registry.register(NotifyTool(broadcast_fn=None))
        self.tool_registry.register(TTSNotifyTool(
            edge_tts_voice=None,
            broadcast_fn=None,
        ))

        # ----- Report generation tools -----
        self.tool_registry.register_many(
            GetUserIdTool(get_user_id_fn=lambda: str(getattr(getattr(self, "agent_runtime", None), "current_user_id", "0"))),
            GetCurrentMonthTool(),
            FetchExternalDataTool(query_usage_fn=None),  # 注入 DB 查询函数后可接入真实数据
            FillContextForReportTool(),
        )
        self.tool_registry.register(GenerateReportTool(
            llm_client=self.llm_client,
            query_usage_fn=None,
            get_user_id_fn=lambda: str(getattr(getattr(self, "agent_runtime", None), "current_user_id", "0")),
            get_context_fn=lambda: getattr(getattr(self, "agent_memory", None), "working", None).get_history_summary() if hasattr(getattr(self, "agent_memory", None), "working") else "",
            get_memory_fn=lambda: getattr(getattr(self, "agent_memory", None), "query_knowledge", lambda q: "")("report_context") if hasattr(self, "agent_memory") else "",
        ))

        self.agent_memory = AgentMemory(
            user_id=0,
            rag_tool=self.rag_tool,
            episodic_memory=EpisodicMemory(long_term_memory=_shared_ltm),
        )
        self.agent_runtime = AgentRuntime(
            llm=self.llm_client,
            tools=self.tool_registry,
            memory=self.agent_memory,
        )

        # Wire up TimeTool callbacks
        _time_tool = self.tool_registry.get("time_query")
        if _time_tool:
            _time_tool._last_episodic = lambda: self.agent_memory.episodic.query_similar("最近任务") if hasattr(self.agent_memory, 'episodic') and self.agent_memory.episodic else None

        # ----- Simulation -----
        self.env = SimulationEnvironment(bus=self.bus)
        # 默认使用 SimulatedDriver 包装仿真环境，可直接替换为 Ros2Driver 等真实硬件驱动
        self.sim_driver = SimulatedDriver(self.env)
        # 向后兼容：API 路由和 Legacy 代码通过此引用访问仿真环境
        self._hardware_driver = self.sim_driver

        # ----- Agents -----
        self.world_model = WorldModelAgent("world_model_1", "world_model", self.bus, self.registry)
        self.perception = PerceptionAgent("perception_1", "perception", self.bus, self.registry)
        if settings.use_rl_navigation:
            self.navigation = RLNavigationAgent(
                "nav_1", "navigation", self.bus, self.registry,
                event_router=self.event_router,
                rag_tool=self.rag_tool,
                map_size=(100, 100), resolution=0.2,
                model_path=settings.rl_model_path,
                hybrid_mode=settings.rl_hybrid_mode,
            )
        else:
            self.navigation = NavigationAgent(
                "nav_1", "navigation", self.bus, self.registry,
                event_router=self.event_router,
                rag_tool=self.rag_tool,
                map_size=(100, 100), resolution=0.2,
            )
        self.execution = ExecutionAgent(
            "exec_1", "execution", self.bus, self.registry,
            event_router=self.event_router,
            robot_driver=self.sim_driver,
        )

        # ----- Supervisor -----
        self.supervisor = SupervisorAgent(
            agent_id="supervisor_1",
            agent_type="supervisor",
            message_bus=self.bus,
            registry=self.registry,
            planner_manager=self.planner_manager,
            dispatcher=None,
            resource_manager=self.resource_manager,
            event_router=self.event_router,
            agent_runtime=self.agent_runtime,
        )
        # Wire up task history saving
        from backend.db.database import get_db_connection
        from backend.db.task_service import save_task
        def _save_task(command, task_type, result):
            try:
                _db = get_db_connection()
                try:
                    save_task(_db, command=command, task_type=task_type, result=result)
                finally:
                    _db.close()
            except Exception:
                pass
        self.supervisor._save_task_fn = _save_task

        # ----- State aggregation & WebSocket -----
        self.state_builder = FrontendStateBuilder()
        self.state_aggregator = RobotStateAggregator(self.bus, self.state_builder)
        self.ws_service = RobotWebSocketService(self.state_aggregator, self.bus)
        from backend.db.database import get_db_connection
        self.scheduler = SchedulerService(self.bus, get_db_connection)

        # Wire up NotifyTool's broadcast_fn
        notify = self.tool_registry.get("notify")
        if notify:
            notify._broadcast = self.ws_service.manager.broadcast

        # Wire up TTSNotifyTool's broadcast_fn
        tts = self.tool_registry.get("tts_notify")
        if tts:
            tts._broadcast_fn = self.ws_service.manager.broadcast

        # Wire up SupervisorAgent broadcast_fn for task visualization
        self.supervisor._broadcast_fn = self.ws_service.on_supervisor_broadcast

        # ----- Startup order -----
        self._components = [
            self.bus,
            self.event_router,
            self.env,
            self.world_model,
            self.perception,
            self.navigation,
            self.execution,
            self.supervisor,
            self.state_aggregator,
            self.ws_service,
            self.scheduler,
        ]

        self._running = False

    async def start(self):
        """Start all components in order."""
        for comp in self._components:
            if hasattr(comp, "start") and asyncio.iscoroutinefunction(comp.start):
                await comp.start()
        self._running = True
        logger.info("SystemContainer started")

    async def stop(self):
        """Stop all components in reverse order."""
        self._running = False
        for comp in reversed(self._components):
            if hasattr(comp, "stop") and asyncio.iscoroutinefunction(comp.stop):
                await comp.stop()
                logger.info(f"{comp.__class__.__name__} stopped")
