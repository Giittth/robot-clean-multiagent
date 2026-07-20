from backend.agents.rl.trainer import train, train_both, RLConfig
import sys

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "pure"
    if mode == "both":
        train_both()
    elif mode == "hybrid":
        train(RLConfig(hybrid_enabled=True))
    else:
        train()
