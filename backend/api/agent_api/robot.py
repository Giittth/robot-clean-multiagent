from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from backend.agents.schemas.messages import Message, MessageType, Priority
from backend.schemas.robot import RobotStateResponse, TaskRequest, ControlRequest, PoseModel
from backend.utils.logger_handler import logger

router = APIRouter()


class TTSRequest(BaseModel):
    text: str


class NavModeRequest(BaseModel):
    mode: str  # "rl" | "traditional"


@router.post("/tts")
async def broadcast_tts(request: Request, tts_req: TTSRequest):
    container = request.app.state.container
    tool = container.tool_registry.get("tts_notify")
    if not tool:
        raise HTTPException(status_code=503, detail="TTS tool not ready")
    result = await tool.execute(text=tts_req.text, device="auto")
    msg = result.data.get("answer", "") if result.data else result.error
    return {"success": result.success, "message": msg}


def _get_components(request: Request):
    container = request.app.state.container
    return container.env, container.bus, container.world_model


@router.get("/state", response_model=RobotStateResponse)
async def get_robot_state(request: Request):
    env, _, _ = _get_components(request)
    if env is None:
        raise HTTPException(status_code=503, detail="Environment not ready")
    return RobotStateResponse(
        pose=PoseModel(x=env.pose.x, y=env.pose.y, theta=env.pose.theta),
        battery=env.battery_voltage,
        cleaned_area=env.cleaned_area,
        collision=env.collision_detected,
    )


@router.get("/world")
async def get_world_model(request: Request):
    _, _, world = _get_components(request)
    if world is None:
        raise HTTPException(status_code=503, detail="WorldModel not ready")
    coverage = world.get_coverage_percent()
    grid = world.world_state.environment.grid
    obstacles = world.world_state.environment.obstacles
    return {
        "coverage_percent": coverage,
        "grid": {
            "width": grid.width,
            "height": grid.height,
            "resolution": grid.resolution,
            "occupancy": grid.occupancy,
        },
        "obstacles": [obs.model_dump() for obs in obstacles],
    }


@router.post("/task")
async def send_task(request: Request, task_req: TaskRequest):
    _, bus, _ = _get_components(request)
    if bus is None:
        raise HTTPException(status_code=503, detail="MessageBus not ready")
    logger.info(f"Sending TASK message with text: {task_req.text}")
    msg = Message(
        type=MessageType.TASK,
        source="api",
        payload={"text": task_req.text},
        priority=Priority.HIGH,
    )
    await bus.publish(msg)
    logger.info("TASK message published")
    return {"status": "task sent"}


@router.post("/control")
async def send_control(request: Request, control_req: ControlRequest):
    _, bus, _ = _get_components(request)
    if bus is None:
        raise HTTPException(status_code=503, detail="MessageBus not ready")
    msg = Message(
        type=MessageType.TASK_CONTROL,
        source="api",
        payload={"command": control_req.command},
        priority=Priority.HIGH,
    )
    await bus.publish(msg)
    logger.info(f"TASK_CONTROL command sent: {control_req.command}")
    return {"status": "control command sent"}


@router.post("/reset")
async def reset_robot(request: Request):
    env, _, _ = _get_components(request)
    if env is None:
        raise HTTPException(status_code=503, detail="Environment not ready")
    await env.reset()
    return {"status": "reset success"}


@router.post("/scenario")
async def switch_scenario(request: Request, scenario_name: str):
    env, _, _ = _get_components(request)
    if env is None:
        raise HTTPException(status_code=503, detail="Environment not ready")
    await env.reload_scenario(scenario_name)
    await env._publish_map_metadata()
    return {"status": "scenario switched", "scenario": scenario_name}


@router.get("/obstacles")
async def get_obstacles(request: Request):
    env, _, _ = _get_components(request)
    return {"obstacles": env.scenario.get("obstacles", [])}


@router.post("/obstacles")
async def add_obstacles(request: Request):
    env, _, world_model = _get_components(request)
    body = await request.json()
    positions = body.get("positions", [])
    radius = body.get("radius", 0.3)
    env.add_obstacles(positions, radius)
    from backend.models.physics.environment import Obstacle, ObstacleType
    for x, y in positions:
        world_model.world_state.environment.obstacles.append(
            Obstacle(type=ObstacleType.CIRCLE, center=(x, y), radius=radius, is_dynamic=True)
        )
    await env._publish_map_metadata()
    return {"status": "added", "count": len(positions)}


@router.delete("/obstacles")
async def remove_obstacles(request: Request):
    env, _, world_model = _get_components(request)
    body = await request.json()
    if body.get("all"):
        env.clear_obstacles()
        world_model.world_state.environment.obstacles = [
            o for o in world_model.world_state.environment.obstacles if not o.is_dynamic
        ]
        await env._publish_map_metadata()
        return {"status": "cleared"}
    positions = body.get("positions", [])
    env.remove_obstacles(positions)
    dyn_obstacles = []
    for obs in world_model.world_state.environment.obstacles:
        keep = True
        for px, py in positions:
            if abs(obs.center[0] - px) < 0.5 and abs(obs.center[1] - py) < 0.5:
                keep = False
                break
        if keep:
            dyn_obstacles.append(obs)
    world_model.world_state.environment.obstacles = [
        o for o in world_model.world_state.environment.obstacles if not o.is_dynamic
    ] + dyn_obstacles
    await env._publish_map_metadata()
    return {"status": "removed", "count": len(positions)}


@router.get("/ask/pending")
async def get_pending_questions(request: Request):
    from backend.agents.tools.question_manager import question_manager
    return {"pending": question_manager.get_pending()}


@router.post("/ask")
async def answer_question(request: Request):
    from backend.agents.tools.question_manager import question_manager
    body = await request.json()
    qid = body.get("id")
    answer = body.get("answer", "")
    if not qid:
        raise HTTPException(status_code=400, detail="Missing question id")
    ok = question_manager.answer(qid, answer)
    if not ok:
        raise HTTPException(status_code=404, detail="Question not found or expired")
    return {"status": "answered", "answer": answer}


@router.post("/confirm")
async def confirm_action(request: Request):
    from backend.agents.tools.confirmation_manager import confirm_manager
    body = await request.json()
    cid = body.get("id")
    approved = body.get("approved", False)
    if not cid:
        raise HTTPException(status_code=400, detail="Missing confirm id")
    ok = confirm_manager.resolve(cid, approved)
    if not ok:
        raise HTTPException(status_code=404, detail="Confirm request not found or expired")
    return {"status": "confirmed", "approved": approved}


@router.get("/tasks/recent")
async def get_recent_tasks(request: Request, user_id: int = 0, limit: int = 20):
    from backend.db.database import get_db_connection
    from backend.db.task_service import get_recent_tasks as _get_recent
    db = get_db_connection()
    try:
        tasks = _get_recent(db, user_id=user_id, limit=limit)
        return {"tasks": tasks}
    finally:
        db.close()


@router.get("/tasks/stats")
async def get_task_statistics(request: Request, user_id: int = 0, days: int = 7):
    from backend.db.database import get_db_connection
    from backend.db.task_service import get_task_stats
    db = get_db_connection()
    try:
        stats = get_task_stats(db, user_id=user_id, days=days)
        return stats
    finally:
        db.close()


@router.get("/missions")
async def list_missions(request: Request, user_id: int = 0, limit: int = 30):
    from backend.db.database import get_db_connection
    from backend.db.task_service import get_missions
    db = get_db_connection()
    try:
        return get_missions(db, user_id=user_id, limit=limit)
    finally:
        db.close()


@router.get("/missions/{mission_id}")
async def get_mission_detail(request: Request, mission_id: int):
    from backend.db.database import get_db_connection
    from backend.db.task_service import get_mission
    db = get_db_connection()
    try:
        m = get_mission(db, mission_id)
        if not m:
            raise HTTPException(status_code=404, detail="Mission not found")
        return m
    finally:
        db.close()


@router.get("/missions/{mission_id}/replay")
async def get_mission_replay(request: Request, mission_id: int, limit: int = 2000):
    from backend.db.database import get_db_connection
    from backend.db.task_service import get_replay
    db = get_db_connection()
    try:
        return get_replay(db, mission_id, limit=limit)
    finally:
        db.close()


@router.delete("/tasks/{task_id}")
async def delete_single_task(request: Request, task_id: int):
    from backend.db.database import get_db_connection
    from backend.db.task_service import delete_task
    db = get_db_connection()
    try:
        ok = delete_task(db, task_id)
        if not ok:
            raise HTTPException(status_code=500, detail="Delete failed")
        return {"status": "deleted", "id": task_id}
    finally:
        db.close()


@router.delete("/missions/{mission_id}")
async def delete_single_mission(request: Request, mission_id: int):
    from backend.db.database import get_db_connection
    from backend.db.task_service import delete_mission
    db = get_db_connection()
    try:
        ok = delete_mission(db, mission_id)
        if not ok:
            raise HTTPException(status_code=500, detail="Delete failed")
        return {"status": "deleted", "id": mission_id}
    finally:
        db.close()


@router.delete("/history")
async def clear_history(request: Request, user_id: int = 0):
    from backend.db.database import get_db_connection
    from backend.db.task_service import clear_all_user_history
    db = get_db_connection()
    try:
        ok = clear_all_user_history(db, user_id=user_id)
        if not ok:
            raise HTTPException(status_code=500, detail="Clear failed")
        return {"status": "cleared"}
    finally:
        db.close()


@router.get("/chat-for-task")
async def get_chat_for_task(request: Request, command: str = ""):
    if not command:
        raise HTTPException(status_code=400, detail="Missing command parameter")
    from backend.db.database import get_db_connection
    db = get_db_connection()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT * FROM chat_history WHERE user_msg = %s ORDER BY create_time DESC LIMIT 1",
                (command,)
            )
            row = cur.fetchone()
            if not row:
                return {"ai_msg": "", "found": False}
            return {"ai_msg": row["ai_msg"], "found": True}
    finally:
        db.close()


@router.get("/rooms")
async def get_rooms(request: Request):
    env, _, _ = _get_components(request)
    if env is None:
        raise HTTPException(status_code=503, detail="Environment not ready")
    rooms_data = env.scenario.get("rooms", [])
    rooms_dict = {}
    for room in rooms_data:
        name = room["name"]
        rooms_dict[name] = {
            "polygon": room["polygon"],
            "center": room.get("center"),
            "entry_point": room.get("entry_point"),
        }
    return rooms_dict


@router.post("/navigation/mode")
async def switch_nav_mode(request: Request, nav_req: NavModeRequest):
    from backend.agents.implementations.rl_navigation_agent import RLNavigationAgent
    from backend.agents.implementations.navigation_agent import NavigationAgent
    from backend.config import settings
    container = request.app.state.container
    await container.navigation.stop()
    if nav_req.mode == "rl":
        container.navigation = RLNavigationAgent(
            "nav_1", "navigation", container.bus, container.registry,
            event_router=container.event_router,
            rag_tool=container.rag_tool,
            map_size=(100, 100), resolution=0.2,
            model_path=settings.rl_model_path,
            hybrid_mode=settings.rl_hybrid_mode,
        )
    elif nav_req.mode == "traditional":
        container.navigation = NavigationAgent(
            "nav_1", "navigation", container.bus, container.registry,
            event_router=container.event_router,
            rag_tool=container.rag_tool,
            map_size=(100, 100), resolution=0.2,
        )
    else:
        raise HTTPException(status_code=400, detail="mode must be 'rl' or 'traditional'")
    await container.navigation.start()
    return {"mode": nav_req.mode}
