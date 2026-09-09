from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "data" / "processed" / "current_season_results.json"
HISTORY_PATH = ROOT / "data" / "predictions" / "prediction_history.json"
OUTPUT_PATH = ROOT / "data" / "predictions" / "completed_matches.json"
TEMP_OUTPUT_PATH = OUTPUT_PATH.with_suffix(".json.tmp")

LEAGUE_NAMES = {
    "pl": "Premier League",
    "laliga": "La Liga",
    "seriea": "Serie A",
    "bundesliga": "Bundesliga",
    "ligue1": "Ligue 1",
}


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"JSONを読み込めません: {path}: {error}") from error
    if not isinstance(payload, list):
        raise RuntimeError(f"JSONのルートが配列ではありません: {path}")
    return [item for item in payload if isinstance(item, dict)]


def actual_result_label(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "Home Win"
    if home_score < away_score:
        return "Away Win"
    return "Draw"


def build_completed_match(result: dict[str, Any], prediction: dict[str, Any] | None) -> dict[str, Any] | None:
    match_id = str(result.get("id", "")).strip()
    if not match_id:
        return None

    try:
        home_score = int(result["home_score"])
        away_score = int(result["away_score"])
    except (KeyError, TypeError, ValueError):
        return None

    actual_result = result.get("actual_result")
    if actual_result not in {"Home Win", "Draw", "Away Win"}:
        actual_result = actual_result_label(home_score, away_score)

    source = prediction or result
    league_id = source.get("league_id") or result.get("league_id") or ""
    recorded = prediction is not None

    return {
        "id": match_id,
        "league_id": league_id,
        "league_name": source.get("league_name") or result.get("league_name") or LEAGUE_NAMES.get(league_id, ""),
        "kickoff": source.get("kickoff") or result.get("kickoff") or "",
        "home_team": source.get("home_team") or result.get("home_team") or {},
        "away_team": source.get("away_team") or result.get("away_team") or {},
        "home_score": home_score,
        "away_score": away_score,
        "actual_result": actual_result,
        "prediction_status": "recorded" if recorded else "missing",
        "prediction_available": recorded,
        "predicted_result": prediction.get("predicted_result") if recorded else None,
        "home_win_probability": prediction.get("home_win_probability") if recorded else None,
        "draw_probability": prediction.get("draw_probability") if recorded else None,
        "away_win_probability": prediction.get("away_win_probability") if recorded else None,
        "is_correct": prediction.get("predicted_result") == actual_result if recorded else None,
        "confidence": prediction.get("confidence") if recorded else None,
        "data_quality": prediction.get("data_quality") if recorded else None,
        "model_version": prediction.get("model_version") if recorded else None,
    }


def atomic_write(payload: list[dict[str, Any]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEMP_OUTPUT_PATH.unlink(missing_ok=True)
    try:
        with TEMP_OUTPUT_PATH.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        verified = json.loads(TEMP_OUTPUT_PATH.read_text(encoding="utf-8"))
        if not isinstance(verified, list):
            raise ValueError("completed_matches.jsonは配列である必要があります")
        os.replace(TEMP_OUTPUT_PATH, OUTPUT_PATH)
    except Exception:
        TEMP_OUTPUT_PATH.unlink(missing_ok=True)
        raise


def main() -> None:
    results = load_json_list(RESULTS_PATH)
    history = load_json_list(HISTORY_PATH)
    history_by_id = {
        str(item["id"]): item
        for item in history
        if item.get("id") is not None
    }

    completed = []
    for result in results:
        match_id = str(result.get("id", "")).strip()
        item = build_completed_match(result, history_by_id.get(match_id))
        if item is not None:
            completed.append(item)

    completed.sort(key=lambda item: str(item.get("kickoff", "")), reverse=True)
    atomic_write(completed)

    recorded = sum(1 for item in completed if item["prediction_status"] == "recorded")
    print(f"終了済み試合を保存: {OUTPUT_PATH}")
    print(f"終了済み試合: {len(completed)}件")
    print(f"予測記録あり: {recorded}件")
    print(f"予測記録なし: {len(completed) - recorded}件")


if __name__ == "__main__":
    main()
