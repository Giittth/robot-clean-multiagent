import os, sys, ast

# === 1. Add obstacle methods to environment.py ===
env_p = "backend/agents/simulation/environment.py"
with open(env_p, "r", encoding="utf-8") as f:
    t = f.read()

obstacle_methods = '''
    def add_obstacle(self, x: float, y: float, radius: float = 0.3):
        """添加一个动态障碍物（圆形）"""
        from backend.models.physics.environment import Obstacle, ObstacleType
        obs = Obstacle(type=ObstacleType.CIRCLE, center=(x, y), radius=radius, is_dynamic=True)
        self.scenario.setdefault("obstacles", []).append(obs.model_dump())

    def add_obstacles(self, positions: list, radius: float = 0.3):
        """批量添加障碍物: positions = [[x1,y1], [x2,y2], ...]"""
        for x, y in positions:
            self.add_obstacle(x, y, radius)

    def remove_obstacles(self, positions: list, tolerance: float = 0.5):
        """移除指定位置的障碍物"""
        remaining = []
        for obs_dict in self.scenario.get("obstacles", []):
            cx, cy = obs_dict.get("center", (0, 0))
            keep = True
            for px, py in positions:
                if abs(cx - px) < tolerance and abs(cy - py) < tolerance:
                    keep = False
                    break
            if keep:
                remaining.append(obs_dict)
        self.scenario["obstacles"] = remaining

    def clear_obstacles(self):
        """清除所有非墙体障碍物（保留四面墙壁）"""
        walls = []
        for obs in self.scenario.get("obstacles", []):
            if not obs.get("is_dynamic", False):
                walls.append(obs)
        self.scenario["obstacles"] = walls
'''

# Insert before _publish_map_metadata
idx = t.find("async def _publish_map_metadata")
if idx > 0:
    t = t[:idx] + obstacle_methods + "\n" + t[idx:]
    with open(env_p, "w", encoding="utf-8") as f:
        f.write(t)
    print("1. environment.py - obstacle methods added")
else:
    print("1. Insert point not found!")

# === 2. Add API endpoints to robot.py ===
robo_p = "backend/api/agent_api/robot.py"
with open(robo_p, "r", encoding="utf-8") as f:
    t = f.read()

obstacle_routes = '''
@router.get("/obstacles")
async def get_obstacles(request: Request):
    """获取当前障碍物列表"""
    env, _, _ = _get_components(request)
    return {"obstacles": env.scenario.get("obstacles", [])}

@router.post("/obstacles")
async def add_obstacles(request: Request):
    """添加动态障碍物"""
    env, _, world_model = _get_components(request)
    body = await request.json()
    positions = body.get("positions", [])
    radius = body.get("radius", 0.3)
    env.add_obstacles(positions, radius)
    # Also update WorldModelAgent's obstacle list for navigation & display
    from backend.models.physics.environment import Obstacle, ObstacleType
    for x, y in positions:
        world_model.world_state.environment.obstacles.append(
            Obstacle(type=ObstacleType.CIRCLE, center=(x, y), radius=radius, is_dynamic=True)
        )
    await env._publish_map_metadata()
    return {"status": "added", "count": len(positions)}

@router.delete("/obstacles")
async def remove_obstacles(request: Request):
    """移除障碍物"""
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
    # Also remove from WorldModelAgent
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
        o for o in world_model.world_state.environment.obstacles
        if not o.is_dynamic
    ] + dyn_obstacles
    await env._publish_map_metadata()
    return {"status": "removed", "count": len(positions)}
'''

# Insert before @router.get("/confirm/pending") (before custom endpoints)
idx = t.find('@router.get("/confirm/pending")')
if idx > 0:
    t = t[:idx] + obstacle_routes + "\n\n" + t[idx:]
    with open(robo_p, "w", encoding="utf-8") as f:
        f.write(t)
    print("2. robot.py - obstacle API endpoints added")
else:
    print("2. Insert point not found!")

# === 3. Verify syntax ===
sys.path.insert(0, ".")
ast.parse(open(env_p, encoding="utf-8").read())
print("3. environment.py syntax OK")
ast.parse(open(robo_p, encoding="utf-8").read())
print("   robot.py syntax OK")

# Verify imports
from backend.models.physics.environment import Obstacle, ObstacleType
print("   Obstacle imports OK")

print("ALL DONE")