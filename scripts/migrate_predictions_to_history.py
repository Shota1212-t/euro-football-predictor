from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATCHES_PATH = ROOT / "data" / "predictions" / "matches.json"
HISTORY_PATH = ROOT / "data" / "predictions" / "prediction_history.json"
TEMP_HISTORY_PATH = HISTORY_PATH.with_suffix(".json.tmp")
BACKUP_PATH = ROOT / "data" / "predictions" / "matches_before_real_predictions.json"


def load_json_safe(path: Path) -> list[dict] | dict:
    """Safely load JSON file."""
    if not path.exists():
        return [] if path.name.endswith("s.json") else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [] if path.name.endswith("s.json") else {}


def write_json(path: Path, payload: list | dict) -> None:
    """Write JSON file safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())


def convert_prediction_to_history(prediction: dict) -> dict | None:
    """Convert prediction dict to history record format."""
    if not isinstance(prediction, dict):
        return None
    
    required = {
        "id",
        "league_id",
        "league_name",
        "kickoff",
        "home_team",
        "away_team",
        "home_win_probability",
        "draw_probability",
        "away_win_probability",
        "predicted_result",
        "confidence",
        "data_quality",
        "model_version",
    }
    
    if not required.issubset(set(prediction.keys())):
        return None
    
    return {
        "id": str(prediction["id"]),
        "league_id": prediction["league_id"],
        "league_name": prediction["league_name"],
        "kickoff": prediction["kickoff"],
        "home_team": prediction["home_team"],
        "away_team": prediction["away_team"],
        "home_win_probability": prediction["home_win_probability"],
        "draw_probability": prediction["draw_probability"],
        "away_win_probability": prediction["away_win_probability"],
        "predicted_result": prediction["predicted_result"],
        "confidence": prediction["confidence"],
        "data_quality": prediction["data_quality"],
        "history_source": "initial_prediction",
        "model_version": prediction["model_version"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    # Load existing history
    existing_history = load_json_safe(HISTORY_PATH)
    if not isinstance(existing_history, list):
        existing_history = []
    
    existing_ids = {str(item.get("id")) for item in existing_history}
    print(f"既存の予測履歴: {len(existing_history)}件")
    
    # Load current predictions from matches.json
    current_predictions = load_json_safe(MATCHES_PATH)
    if not isinstance(current_predictions, list):
        current_predictions = []
    
    print(f"現在の予測: {len(current_predictions)}件")
    
    # Load backup predictions if available
    backup_predictions = load_json_safe(BACKUP_PATH)
    if not isinstance(backup_predictions, list):
        backup_predictions = []
    
    print(f"バックアップ予測: {len(backup_predictions)}件")
    
    # Merge: backup takes precedence, then current predictions
    all_predictions = {}
    for pred in backup_predictions:
        match_id = str(pred.get("id"))
        if match_id:
            all_predictions[match_id] = pred
    for pred in current_predictions:
        match_id = str(pred.get("id"))
        if match_id and match_id not in all_predictions:
            all_predictions[match_id] = pred
    
    print(f"統合後の予測: {len(all_predictions)}件")
    
    # Convert new predictions
    added_count = 0
    for match_id, prediction in all_predictions.items():
        if match_id in existing_ids:
            continue
        
        history_record = convert_prediction_to_history(prediction)
        if history_record:
            existing_history.append(history_record)
            added_count += 1
    
    print(f"新しく追加: {added_count}件")
    
    # Sort by kickoff (descending)
    existing_history.sort(key=lambda x: x.get("kickoff", ""), reverse=True)
    
    # Atomic write
    TEMP_HISTORY_PATH.unlink(missing_ok=True)
    try:
        with TEMP_HISTORY_PATH.open("w", encoding="utf-8") as f:
            json.dump(existing_history, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        
        # Verify
        written = json.loads(TEMP_HISTORY_PATH.read_text(encoding="utf-8"))
        if not isinstance(written, list):
            raise ValueError("History must be a list")
        
        # Replace
        os.replace(TEMP_HISTORY_PATH, HISTORY_PATH)
        print(f"予測履歴を保存: {HISTORY_PATH}")
        print(f"合計件数: {len(existing_history)}件")
    except Exception as e:
        TEMP_HISTORY_PATH.unlink(missing_ok=True)
        if HISTORY_PATH.exists():
            print(f"保存失敗。既存ファイルを保持: {e}", file=sys.stderr)
        else:
            raise


if __name__ == "__main__":
    import sys
    main()
