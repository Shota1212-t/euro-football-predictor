import json
from .config import REPORT_DIR

def run():
    scores = {}
    for name, file in [("LightGBM", "lightgbm_metrics.json"), ("PyTorch MLP", "neural_network_metrics.json")]:
        path = REPORT_DIR / file
        if path.exists():
            scores[name] = json.loads(path.read_text(encoding="utf-8"))
    if not scores:
        raise FileNotFoundError("評価結果がありません。先にモデルを学習してください。")
    print("\nモデル比較")
    for name, metrics in scores.items():
        print(f"{name:15} Accuracy={metrics['accuracy']:.4f} F1={metrics['macro_f1']:.4f} LogLoss={metrics['log_loss']:.4f} Brier={metrics['brier_score']:.4f}")
    best = min(scores, key=lambda name: scores[name]["log_loss"])
    print(f"\nLog Loss基準の採用候補: {best}")
    return scores

if __name__ == "__main__":
    run()
