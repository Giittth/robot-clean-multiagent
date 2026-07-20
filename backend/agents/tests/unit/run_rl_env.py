import numpy as np
from backend.agents.rl.env_wrapper import RobotGymEnv

def test_env():
    """测试环境的基本功能：reset、step、随机动作"""
    env = RobotGymEnv(max_steps=50, render=True)
    obs = env.reset()
    print(f"Initial observation shape: {obs.shape}")
    total_reward = 0
    for step in range(20):
        action = env.action_space.sample()  # 随机动作
        obs, reward, done, info = env.step(action)
        total_reward += reward
        print(f"Step {step+1}: action={action}, reward={reward:.2f}, cleaned={info['cleaned_area']:.2f}")
        if done:
            print(f"Episode finished at step {step+1}")
            break
    print(f"Total reward: {total_reward:.2f}")
    env.close()

def test_model_loading(model_path="./rl_models/final_robot_policy.zip"):
    """测试模型加载和推理"""
    from stable_baselines3 import PPO
    import os
    if not os.path.exists(model_path):
        print(f"Model not found at {model_path}, skipping model test.")
        return
    env = RobotGymEnv(max_steps=100, render=False)
    model = PPO.load(model_path)
    obs = env.reset()
    action, _ = model.predict(obs, deterministic=True)
    print(f"Model loaded successfully, action: {action}")
    env.close()

if __name__ == "__main__":
    print("=== Testing environment ===")
    test_env()
    print("\n=== Testing model loading (if available) ===")
    test_model_loading()