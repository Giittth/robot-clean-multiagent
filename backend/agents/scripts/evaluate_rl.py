from backend.agents.rl.eval import evaluate, RLConfig
import sys

if __name__ == "__main__":
    model_path = sys.argv[1] if len(sys.argv) > 1 else "./rl_models/pure/final_robot_policy.zip"
    mode = "hybrid" if "hybrid" in model_path.replace("\\", "/") else "pure"
    cfg = RLConfig(hybrid_enabled=(mode == "hybrid"))
    evaluate(model_path=model_path, episodes=5, render=True, config=cfg)
