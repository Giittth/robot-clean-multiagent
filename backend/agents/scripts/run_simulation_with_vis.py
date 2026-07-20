import asyncio
from backend.agents.core.messaging.message_bus import MessageBus
from backend.agents.core.lifecycle.registry import AgentRegistry
from backend.agents.implementations.perception_agent import PerceptionAgent
from backend.agents.implementations.navigation_agent import NavigationAgent
from backend.agents.implementations.execution_agent import ExecutionAgent
from backend.agents.implementations.supervisor_agent import SupervisorAgent
from backend.agents.simulation.environment import SimulationEnvironment
from backend.services.websocket.robot_ws_service import RobotWebSocketService
from backend.utils.logger_handler import logger

async def main():
    # Core components
    bus = MessageBus()
    registry = AgentRegistry()

    # Start message bus
    await bus.start()
    logger.info("MessageBus started successfully")

    # 1. Start simulation environment (physics + sensors + state publishing)
    sim = SimulationEnvironment(bus)
    await sim.start()
    logger.info("Simulation environment started successfully")

    # 2. Start WebSocket state push (real-time frontend display)
    ws = RobotWebSocketService(bus)
    await ws.start()
    logger.info("WebSocket state broadcast service started successfully")

    # 3. Initialize all agents
    perception = PerceptionAgent("perception_1", "perception", bus, registry)
    navigation = NavigationAgent("nav_1", "navigation", bus, registry, map_size=(20, 20))
    execution = ExecutionAgent("exec_1", "execution", bus, registry)
    supervisor = SupervisorAgent("supervisor_1", "supervisor", bus, registry)

    # 4. Start all agents
    await perception.start()
    await navigation.start()
    await execution.start()
    await supervisor.start()
    logger.info("All agents started successfully")

    logger.info("=====================================")
    logger.info("Robot System Fully Started!")
    logger.info("WebSocket: ws://localhost:8765")
    logger.info("Press Ctrl+C to shut down safely")
    logger.info("=====================================")

    # Keep running and wait for shutdown signal
    try:
        await asyncio.Future()  # Run forever

    # Catch shutdown signal
    except KeyboardInterrupt:
        logger.info("Shutting down system safely...")

    finally:
        # Shutdown in reverse order (last started, first stopped)
        await supervisor.stop()
        await execution.stop()
        await navigation.stop()
        await perception.stop()
        logger.info("All agents stopped")

        await ws.stop()
        await sim.stop()
        logger.info("Simulation & WebSocket stopped")

        await bus.stop()
        logger.info("MessageBus stopped")
        logger.info("System shut down safely and completely")

if __name__ == "__main__":
    # Fix asyncio shutdown issues on Windows
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program exited")