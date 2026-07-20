"""
模型评估脚本：加载训练好的PPO扫地机器人模型，在仿真环境中测试多回合性能
指标：单回合总奖励、清扫覆盖率、总步数、清扫面积、剩余电量，最后输出均值统计
支持命令行参数：python evaluate.py pure / python evaluate.py hybrid
"""
import os
import sys
import asyncio
import numpy as np
from stable_baselines3 import PPO
from backend.agents.rl.env_wrapper import RobotGymEnv, RLConfig
from backend.utils.logger_handler import logger

# Windows系统适配异步事件循环，防止asyncio异常
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def evaluate(model_path: str,
             episodes: int = 5,
             render: bool = True,
             config: RLConfig = None):
    """Evaluate a trained RL policy.

    Args:
        model_path: Path to saved PPO model.
        episodes:   Number of evaluation episodes.
        render:     Whether to print step-by-step info.
        config:     RLConfig matching the training setup (obs dim etc).
    """
    # 检查模型文件是否存在
    if not os.path.exists(model_path):
        logger.error(f"Model not found at {model_path}")
        return

    cfg = config
    # 创建评估环境
    env = RobotGymEnv(config=cfg, render=render)
    # 加载PPO模型
    model = PPO.load(model_path)

    logger.info(f"Starting evaluation for {episodes} episodes...")
    summary = []

    # 逐回合测试
    for ep in range(episodes):
        obs, _ = env.reset()
        total_reward = 0
        step_count = 0
        terminated = False
        truncated = False

        while not (terminated or truncated):
            # deterministic=True：确定性推理，关闭随机探索
            action, _states = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            step_count += reward
            step_count += 1

        cov_ratio = info.get("coverage_ratio", 0.0)
        summary.append({
            "episode": ep + 1,
            "reward": round(total_reward, 2),
            "steps": step_count,
            "cleaned_area": round(info.get("cleaned_area", 0), 2),
            "battery": round(info.get("battery", 0), 2),
            "coverage_ratio": round(cov_ratio, 3),
        })
        logger.info(f"Episode {ep+1:2d} | Reward = {total_reward:6.2f} | "
                    f"Steps = {step_count:3d} | "
                    f"Cleaned = {info['cleaned_area']:.2f} | "
                    f"Cov = {cov_ratio:.1%} | "
                    f"Battery = {info['battery']:.2f}V")

    # 计算整体统计信息
    rewards = [s["reward"] for s in summary]
    logger.info("=" * 50)
    logger.info(f"Evaluation Summary ({episodes} episodes):")
    logger.info(f"  Mean reward:       {np.mean(rewards):.2f} +/- {np.std(rewards):.2f}")
    logger.info(f"  Mean coverage:     {np.mean([s['coverage_ratio'] for s in summary]):.1%}")
    logger.info(f"  Mean steps/ep:     {np.mean([s['steps'] for s in summary]):.0f}")
    logger.info("=" * 50)

    # 关闭环境释放资源
    env.close()
    logger.info("Evaluation finished!")
    return summary


if __name__ == "__main__":
    # 读取命令行参数，默认 pure
    mode = sys.argv[1] if len(sys.argv) > 1 else "pure"

    if mode == "hybrid":
        model_path = "./rl_models/hybrid/final_robot_policy.zip"
        cfg = RLConfig(hybrid_enabled=True)
    else:  # pure
        model_path = "./rl_models/pure/final_robot_policy.zip"
        cfg = RLConfig(hybrid_enabled=False)

    evaluate(model_path=model_path, episodes=5, render=True, config=cfg)