"""
PPO强化学习训练&评估脚本
功能：
    1. 训练两种模式扫地机器人模型：纯端到端(pure) / BFS混合导航(hybrid)
    2. 使用Stable-Baselines3 PPO算法，设置检查点保存、评估回调、Tensorboard日志
    3. 模型保存至rl_models目录，日志保存至rl_logs目录
    4. 评估脚本加载训练好的模型，统计多回合平均奖励、清扫覆盖率、耗电等指标
    5. Windows系统异步事件循环适配，保证仿真环境正常运行
"""
import os
import asyncio
import random
import numpy as np
from dataclasses import dataclass

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from stable_baselines3.common.vec_env import DummyVecEnv

from backend.agents.rl.env_wrapper import RobotGymEnv, RLConfig

# Windows系统适配异步事件循环，防止asyncio异常
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def train(config: RLConfig = None, seed: int = 42, total_timesteps: int = 100_000):
    """Config-driven RL training with reproducibility.

    Args:
        config:  Override specific RLConfig fields or use defaults.
        seed:    Random seed for reproducibility.
        total_timesteps: Total training steps.
    """
    if config is None:
        config = RLConfig()

    # 设置随机种子，保证实验可复现
    random.seed(seed)
    np.random.seed(seed)

    # 根据是否混合导航模式区分文件夹
    prefix = "hybrid" if config.hybrid_enabled else "pure"
    log_dir = f"./rl_logs/{prefix}/"
    model_dir = f"./rl_models/{prefix}/"
    # 创建日志和模型保存目录
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(model_dir, exist_ok=True)

    # 构建强化学习环境
    env = RobotGymEnv(config=config, render=False)

    # 检查点回调：定期保存模型
    checkpoint_callback = CheckpointCallback(
        save_freq=20000,                # 每20000步保存一次模型
        save_path=model_dir,            # 模型保存路径
        name_prefix=f"robot_ppo_{prefix}",
    )

    # 评估环境和评估回调
    eval_env = RobotGymEnv(config=config, render=False)
    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path=model_dir, # 保存最优模型
        log_path=log_dir,
        eval_freq=10000,                # 每10000步评估一次
        deterministic=True,
    )

    # PPO模型初始化：MLP全连接策略网络
    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        tensorboard_log=None,
        learning_rate=3e-4,             # 学习率
        n_steps=2048,                   # 每轮收集轨迹步数
        batch_size=64,                 # mini-batch大小
        n_epochs=10,                   # 每批样本迭代训练轮数
        gamma=0.99,                    # 回报折扣因子
        gae_lambda=0.95,               # GAE广义优势估计参数
        clip_range=0.2,                # PPO裁剪参数
        ent_coef=0.01,                 # 熵正则系数，鼓励探索
        seed=seed,
    )

    # 开始训练，绑定回调函数
    model.learn(
        total_timesteps=total_timesteps,
        callback=[checkpoint_callback, eval_callback],
    )

    # 保存最终训练完成模型
    model.save(os.path.join(model_dir, "final_robot_policy"))
    print(f"[Train] {prefix.upper()} model saved to {model_dir}final_robot_policy")

    # 关闭环境释放资源
    env.close()
    eval_env.close()


def train_both(seed: int = 42, total_timesteps: int = 100_000):
    """Convenience: train pure (365-dim) and hybrid (367-dim) models."""
    # 纯端到端模式配置（仅激光雷达+基础观测）
    pure_cfg = RLConfig(hybrid_enabled=False)
    # 混合导航模式配置（增加BFS目标方向观测）
    hybrid_cfg = RLConfig(hybrid_enabled=True)

    print("=" * 60)
    print("Training PURE model (365-dim obs, reactive)")
    print("=" * 60)
    train(pure_cfg, seed=seed, total_timesteps=total_timesteps)

    print("=" * 60)
    print("Training HYBRID model (367-dim obs, goal-conditioned)")
    print("=" * 60)
    train(hybrid_cfg, seed=seed + 1, total_timesteps=total_timesteps)


if __name__ == "__main__":
    import sys
    # 读取命令行参数，默认pure纯模型训练
    mode = sys.argv[1] if len(sys.argv) > 1 else "pure"
    if mode == "both":
        train_both()
    elif mode == "hybrid":
        train(RLConfig(hybrid_enabled=True))
    else:
        train()