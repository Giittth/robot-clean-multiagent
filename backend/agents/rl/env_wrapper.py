"""
RobotGymEnv - Gymnasium 扫地机器人全屋清扫强化学习仿真环境
功能：遵循Gymnasium标准接口，支持域随机化、BFS混合导航模式，训练机器人避障+全覆盖清扫任务
观测：360维激光雷达 + 机器人位姿 + 电池信息 + (可选导航方向向量)
动作：2维连续动作 [线速度, 角速度]
奖励：清扫面积奖励 + 新增覆盖栅格奖励 + 完成覆盖率奖励 - 碰撞惩罚 - 耗电惩罚 - 原地低效旋转惩罚
终止条件：电池电压过低 / 达到最大回合步数
"""
import gymnasium as gym
from gymnasium import spaces
import numpy as np
import asyncio
import math
import random
from dataclasses import dataclass
from typing import Optional, Tuple

from backend.agents.simulation.environment import SimulationEnvironment
from backend.agents.core.messaging.message_bus import MessageBus
from backend.agents.schemas.messages import Message, MessageType, Priority
from backend.models.physics.action import Velocity
from backend.agents.schemas.agent_messages import ExecutionCommand
from backend.models.physics.robot_state import Pose
from backend.utils.logger_handler import logger


@dataclass
class RLConfig:
    # 激光雷达最大测距
    max_laser_dist: float = 5.0
    # 地图整体范围
    map_range: float = 10.0
    # 电池满电电压
    max_battery: float = 12.0
    # 最大前进线速度
    max_linear_speed: float = 1.0
    # 最小后退线速度
    min_linear_speed: float = -0.5
    # 最大角速度（转向速度）
    max_angular_speed: float = 1.0
    # 清扫面积奖励系数
    clean_reward_coef: float = 12.0
    # 电量消耗惩罚系数
    battery_penalty_coef: float = 1.5
    # 碰撞惩罚值
    collision_penalty: float = 8.0
    # 新增覆盖栅格奖励系数
    coverage_progress_coef: float = 2.0
    # 原地无效旋转惩罚系数
    efficiency_penalty_coef: float = 0.3
    # 完成清扫大额奖励
    completion_bonus: float = 50.0
    # 清扫完成阈值覆盖率
    completion_threshold: float = 0.85
    # 是否开启域随机化（Domain Randomization）
    dr_enabled: bool = True
    # 随机障碍物最小数量
    dr_num_obstacles_min: int = 5
    # 随机障碍物最大数量
    dr_num_obstacles_max: int = 18
    # 随机障碍物最小半径
    dr_obstacle_radius_min: float = 0.12
    # 随机障碍物最大半径
    dr_obstacle_radius_max: float = 0.4
    # 激光雷达噪声标准差
    dr_laser_noise_std: float = 0.05
    # 机器人初始x坐标随机范围
    dr_start_x_range: Tuple[float, float] = (-1.5, 1.5)
    # 机器人初始y坐标随机范围
    dr_start_y_range: Tuple[float, float] = (-1.5, 1.5)
    # 清扫覆盖网格尺寸（方阵）
    coverage_grid_size: int = 50
    # 单个覆盖栅格尺寸
    coverage_cell_size: float = 0.3
    # 单回合最大步数
    max_steps: int = 500
    # 是否开启混合导航模式（BFS全局导航 + RL局部控制）
    hybrid_enabled: bool = False
    # 混合模式观测维度
    hybrid_obs_dim: int = 367


class RobotGymEnv(gym.Env):
    # 渲染配置
    metadata = {"render_modes": ["human"], "render_fps": 10}

    def __init__(self, config: Optional[RLConfig] = None, render: bool = False):
        # 调用Gym父类初始化
        super().__init__()
        # 加载配置参数
        self.config = config or RLConfig()
        self.max_steps = self.config.max_steps
        self.enable_render = render
        self.step_count = 0  # 当前回合步数计数
        cfg = self.config

        # 计算观测总维度
        obs_dim = 365 + (2 if cfg.hybrid_enabled else 0)
        self.obs_dim = obs_dim

        # 构造观测空间下界
        obs_low = np.concatenate([
            np.zeros(360),  # 360维激光雷达下限
            np.array([-1.0, -1.0, -1.0, -1.0]),  # x/y/sinθ/cosθ 位姿下限
            np.array([0.0]),  # 电池归一化下限
        ])
        # 混合模式追加导航方向2维
        if cfg.hybrid_enabled:
            obs_low = np.concatenate([obs_low, np.array([-1.0, -1.0])])

        # 构造观测空间上界
        obs_high = np.concatenate([
            np.ones(360),  # 360维激光雷达上限
            np.array([1.0, 1.0, 1.0, 1.0]),  # x/y/sinθ/cosθ 位姿上限
            np.array([1.0]),  # 电池归一化上限
        ])
        # 混合模式追加导航方向2维
        if cfg.hybrid_enabled:
            obs_high = np.concatenate([obs_high, np.array([1.0, 1.0])])

        # 定义观测空间 Box连续向量
        self.observation_space = spaces.Box(
            low=obs_low.astype(np.float32),
            high=obs_high.astype(np.float32),
            dtype=np.float32,
        )

        # 定义动作空间：线速度、角速度 连续控制
        self.action_space = spaces.Box(
            low=np.array([cfg.min_linear_speed, -cfg.max_angular_speed], dtype=np.float32),
            high=np.array([cfg.max_linear_speed, cfg.max_angular_speed], dtype=np.float32),
            dtype=np.float32,
        )

        # 创建异步事件循环，用于和仿真引擎异步交互
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        except Exception:
            self.loop = asyncio.get_event_loop()

        # 初始化消息总线和仿真环境
        self.bus = MessageBus()
        self.sim = SimulationEnvironment(self.bus)
        self.loop.run_until_complete(self.bus.start())
        self.loop.run_until_complete(self.sim.start())

        # 上一步清扫总面积
        self.last_cleaned_area = 0.0
        # 上一步电池电压
        self.last_battery = 12.0
        # 记录上一步执行的动作
        self._last_action = np.array([0.0, 0.0], dtype=np.float32)
        # 是否已经发放完成清扫奖励
        self._bonus_given = False

        # 全覆盖栅格标记矩阵
        self._cov_grid = np.zeros(
            (cfg.coverage_grid_size, cfg.coverage_grid_size), dtype=bool
        )
        # 栅格原点偏移（用于世界坐标转栅格索引）
        self._cov_origin_offset = cfg.coverage_grid_size // 2
        # 可通行单元格总数
        self._reachable_cells = 1
        # 当前回合累计覆盖单元格数量
        self._cov_cells_by_episode = 0

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        # Gym环境重置，初始化回合状态
        super().reset(seed=seed)
        self.step_count = 0
        # 开启域随机化则随机生成地图和初始位姿
        if self.config.dr_enabled:
            self._domain_randomize()
        # 重置仿真环境
        self.loop.run_until_complete(self.sim.reset())
        # 重置统计变量
        self.last_cleaned_area = self.sim.cleaned_area
        self.last_battery = self.sim.battery_voltage
        self._last_action = np.array([0.0, 0.0], dtype=np.float32)
        self._bonus_given = False
        self._cov_grid.fill(False)
        # 标记初始位置栅格
        self._mark_coverage()
        self._cov_cells_by_episode = 1
        # 计算整张地图可通行单元格总数
        self._reachable_cells = self._estimate_reachable_cells()
        # 混合模式更新导航方向
        if self.config.hybrid_enabled:
            self._update_goal_direction()
        # 返回初始观测和附加信息
        return self._get_obs(), {}

    def _domain_randomize(self):
        # 域随机化：随机障碍物布局 + 机器人起始位置朝向，提升泛化能力
        cfg = self.config
        self.sim.clear_obstacles()
        # 随机生成障碍物数量
        num_obs = random.randint(cfg.dr_num_obstacles_min, cfg.dr_num_obstacles_max)
        for _ in range(num_obs):
            x = random.uniform(-4.0, 4.0)
            y = random.uniform(-4.0, 4.0)
            r = random.uniform(cfg.dr_obstacle_radius_min, cfg.dr_obstacle_radius_max)
            # 避免障碍物堵死起始中心区域
            if abs(x) < 1.5 and abs(y) < 1.5:
                x = random.uniform(2.0, 4.0) * random.choice([-1, 1])
                y = random.uniform(2.0, 4.0) * random.choice([-1, 1])
            self.sim.add_obstacle(x, y, r)
        # 随机起始坐标和朝向
        sx = random.uniform(*cfg.dr_start_x_range)
        sy = random.uniform(*cfg.dr_start_y_range)
        stheta = random.uniform(-math.pi, math.pi)
        self.sim.pose = Pose(x=sx, y=sy, theta=stheta)

    def _estimate_reachable_cells(self) -> int:
        # 遍历栅格，统计非障碍物可通行单元格总数
        cfg = self.config
        half = cfg.coverage_grid_size // 2
        total = 0
        for gx in range(cfg.coverage_grid_size):
            for gy in range(cfg.coverage_grid_size):
                wx = (gx - half) * cfg.coverage_cell_size
                wy = (gy - half) * cfg.coverage_cell_size
                if not self._is_point_occupied(wx, wy):
                    total += 1
        return max(total, 1)

    def _is_point_occupied(self, wx: float, wy: float) -> bool:
        # 判断世界坐标点是否被障碍物占据（不可通行）
        robot_r = getattr(self.sim, 'robot_radius', 0.2)
        for obs in self.sim.scenario.get("obstacles", []):
            otype = obs.get("type")
            cx, cy = obs.get("center", (0, 0))
            if otype == "circle":
                r = obs.get("radius", 0.2)
                if math.hypot(wx - cx, wy - cy) < r + robot_r:
                    return True
            elif otype == "rect":
                w = obs.get("width", 0.2)
                h = obs.get("height", 0.2)
                left = cx - w / 2
                right = cx + w / 2
                bottom = cy - h / 2
                top = cy + w / 2
                closest_x = max(left, min(wx, right))
                closest_y = max(bottom, min(wy, top))
                if math.hypot(wx - closest_x, wy - closest_y) < robot_r:
                    return True
        return False

    def step(self, action):
        # 单步仿真交互：接收动作，执行仿真，返回观测/奖励/结束标记/信息
        self.step_count += 1
        linear_vel, angular_vel = action
        # 构造速度指令消息发送给仿真引擎，执行0.1秒
        cmd = ExecutionCommand(target_velocity=Velocity(linear=linear_vel, angular=angular_vel), duration=0.1)
        msg = Message(
            type=MessageType.EXECUTION, source="rl_agent", target=None,
            payload=cmd.model_dump(), priority=Priority.NORMAL
        )
        self.loop.run_until_complete(self.sim.handle_exec_command(msg))
        # 标记当前栅格为已清扫
        self._mark_coverage()
        # 混合模式更新BFS导航方向
        if self.config.hybrid_enabled:
            self._update_goal_direction()
        # 获取当前观测向量
        obs = self._get_obs()
        # 计算单步奖励
        reward = self._compute_reward(linear_vel, angular_vel)
        # 统计当前总覆盖单元格
        covered = int(np.sum(self._cov_grid))
        if covered > self._cov_cells_by_episode:
            self._cov_cells_by_episode = covered
        # 附加信息字典，用于日志和监控
        info = {
            "cleaned_area": self.sim.cleaned_area,
            "battery": self.sim.battery_voltage,
            "collision": self.sim.collision_detected,
            "coverage_cells": covered,
            "reachable_cells": self._reachable_cells,
            "coverage_ratio": covered / max(self._reachable_cells, 1),
        }
        # 控制台简易渲染
        if self.enable_render:
            self.render()
        self._last_action = np.array([linear_vel, angular_vel], dtype=np.float32)
        # 异常终止：电池电压过低
        terminated = self.sim.battery_voltage < 9.0
        # 截断终止：达到回合最大步数
        truncated = self.step_count >= self.max_steps
        return obs, reward, terminated, truncated, info

    def _get_obs(self):
        # 构造RL模型输入观测向量
        cfg = self.config
        # 获取激光雷达数据并归一化到0~1
        laser = np.array(self.sim.last_laser, dtype=np.float32)
        laser = np.clip(laser / cfg.max_laser_dist, 0.0, 1.0)
        pose = self.sim.pose
        # 归一化位姿 + sin/cos朝向表示
        pose_vec = np.array([
            pose.x / cfg.map_range, pose.y / cfg.map_range,
            math.sin(pose.theta), math.cos(pose.theta),
        ], dtype=np.float32)
        # 归一化电池电压
        battery_vec = np.array([self.sim.battery_voltage / cfg.max_battery], dtype=np.float32)
        parts = [laser, pose_vec, battery_vec]
        # 混合模式追加导航方向向量
        if cfg.hybrid_enabled and hasattr(self, '_goal_direction'):
            parts.append(self._goal_direction.astype(np.float32))
        elif cfg.hybrid_enabled:
            parts.append(np.array([0.0, 0.0], dtype=np.float32))
        return np.concatenate(parts).astype(np.float32)

    def set_goal_direction(self, dx: float, dy: float):
        # 设置BFS计算得到的目标导航方向向量
        if self.config.hybrid_enabled:
            self._goal_direction = np.array([dx, dy], dtype=np.float32)

    def _update_goal_direction(self):
        # BFS广度优先搜索查找最近未清扫栅格，生成导航方向向量
        if not self.config.hybrid_enabled:
            return
        cfg = self.config
        half = cfg.coverage_grid_size // 2
        # 当前机器人位置转为栅格索引
        gx = int(self.sim.pose.x / cfg.coverage_cell_size) + self._cov_origin_offset
        gy = int(self.sim.pose.y / cfg.coverage_cell_size) + self._cov_origin_offset
        from collections import deque
        visited = set()
        q = deque()
        q.append((gx, gy))
        visited.add((gx, gy))
        # BFS遍历查找第一个未覆盖、可通行栅格
        while q:
            cx, cy = q.popleft()
            wx = (cx - self._cov_origin_offset) * cfg.coverage_cell_size
            wy = (cy - self._cov_origin_offset) * cfg.coverage_cell_size
            if not self._cov_grid[cy, cx] and not self._is_point_occupied(wx, wy):
                dx = wx - self.sim.pose.x
                dy = wy - self.sim.pose.y
                norm = math.hypot(dx, dy)
                # 归一化方向向量
                self.set_goal_direction(dx / norm, dy / norm) if norm > 0.01 else self.set_goal_direction(0.0, 0.0)
                return
            # 遍历上下左右4邻域栅格
            for ndx, ndy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                nx_g, ny_g = cx + ndx, cy + ndy
                if (0 <= nx_g < cfg.coverage_grid_size and 0 <= ny_g < cfg.coverage_grid_size and (nx_g,
                                                                                                   ny_g) not in visited):
                    visited.add((nx_g, ny_g))
                    q.append((nx_g, ny_g))
        # 全区域清扫完成，导航方向置零
        self.set_goal_direction(0.0, 0.0)

    def _compute_reward(self, linear_vel: float, angular_vel: float) -> float:
        # 计算单步奖励函数
        cfg = self.config
        reward = 0.0
        # 新增清扫面积奖励
        clean_delta = self.sim.cleaned_area - self.last_cleaned_area
        reward += clean_delta * cfg.clean_reward_coef
        # 电量消耗惩罚
        battery_delta = self.last_battery - self.sim.battery_voltage
        reward -= battery_delta * cfg.battery_penalty_coef
        # 碰撞惩罚
        if self.sim.collision_detected:
            reward -= cfg.collision_penalty
        # 新增覆盖栅格奖励
        covered_now = int(np.sum(self._cov_grid))
        new_cells = covered_now - self._cov_cells_by_episode
        if new_cells > 0:
            reward += new_cells * cfg.coverage_progress_coef
            self._cov_cells_by_episode = covered_now
        # 原地低效旋转惩罚（低速前进+大幅度转向）
        if abs(linear_vel) < 0.05 and abs(angular_vel) > 0.3:
            reward -= abs(angular_vel) * cfg.efficiency_penalty_coef
        # 达到清扫覆盖率阈值，一次性大额完成奖励
        if self._reachable_cells > 0:
            ratio = covered_now / self._reachable_cells
            if ratio >= cfg.completion_threshold and not self._bonus_given:
                reward += cfg.completion_bonus
                self._bonus_given = True
        # 更新历史统计值
        self.last_cleaned_area = self.sim.cleaned_area
        self.last_battery = self.sim.battery_voltage
        return reward

    def _mark_coverage(self):
        # 将机器人当前所在栅格标记为已清扫覆盖
        cfg = self.config
        pose = self.sim.pose
        gx = int(pose.x / cfg.coverage_cell_size) + self._cov_origin_offset
        gy = int(pose.y / cfg.coverage_cell_size) + self._cov_origin_offset
        if 0 <= gx < cfg.coverage_grid_size and 0 <= gy < cfg.coverage_grid_size:
            self._cov_grid[gy, gx] = True

    def _check_done(self) -> bool:
        # 旧版Gym结束判断（保留兼容）
        if self.sim.battery_voltage < 9.0:
            return True
        if self.step_count >= self.max_steps:
            return True
        return False

    def render(self):
        # 控制台文本简易渲染，打印当前状态信息
        ratio = int(np.sum(self._cov_grid)) / max(self._reachable_cells, 1)
        s = '[RL] Step ' + str(self.step_count).rjust(3) + ' | '
        s += 'Pose (' + f'{self.sim.pose.x:5.2f}, {self.sim.pose.y:5.2f}) | '
        s += 'Cleaned ' + f'{self.sim.cleaned_area:5.2f} | '
        s += 'Cov ' + f'{ratio:.1%} | '
        s += 'Battery ' + f'{self.sim.battery_voltage:5.2f}V'
        print(s)

    def close(self):
        # 关闭仿真、消息总线和异步循环，释放资源
        try:
            self.loop.run_until_complete(self.sim.stop())
            self.loop.run_until_complete(self.bus.stop())
        except Exception as e:
            logger.error(f"Env close error: {e}")