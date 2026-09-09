import importlib.util
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def mod(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_429_retry(monkeypatch):
    module = mod("fetch_football_data_org.py")
    calls = []

    class Client:
        def get(self, *args, **kwargs):
            calls.append(1)
            return httpx.Response(
                429 if len(calls) == 1 else 200,
                content="{}",
                headers={"Retry-After": "0"},
                request=httpx.Request("GET", "https://x"),
            )

    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "rate_limit_wait", lambda: None)

    assert module.request_json(Client(), "/x") == {}
    assert len(calls) == 2


def test_results_atomic(monkeypatch, tmp_path):
    module = mod("fetch_football_data_org.py")
    output_path = tmp_path / "r.json"
    temp_path = tmp_path / "r.tmp"
    monkeypatch.setattr(module, "RESULTS_PATH", output_path)
    monkeypatch.setattr(module, "TEMP_RESULTS_PATH", temp_path)

    rows = [
        {
            "id": "1",
            "status": "FINISHED",
            "kickoff": "x",
            "home_score": 1,
            "away_score": 0,
            "actual_result": "Home Win",
        }
    ]
    module.atomic_write_results(rows)
    assert json.loads(output_path.read_text()) == rows


def run_completed_builder(module, monkeypatch, tmp_path, results, history):
    results_path = tmp_path / "results.json"
    history_path = tmp_path / "history.json"
    output_path = tmp_path / "completed.json"

    results_path.write_text(json.dumps(results), encoding="utf-8")
    history_path.write_text(json.dumps(history), encoding="utf-8")

    monkeypatch.setattr(module, "R", results_path)
    monkeypatch.setattr(module, "H", history_path)
    monkeypatch.setattr(module, "O", output_path)
    monkeypatch.setattr(module, "T", output_path.with_suffix(".tmp"))

    module.main()
    return json.loads(output_path.read_text(encoding="utf-8"))


def completed_result(match_id="1", home_score=1, away_score=0):
    return {
        "id": match_id,
        "league_id": "pl",
        "league_name": "Premier League",
        "kickoff": "2026-09-01T12:00:00Z",
        "home_team": {"id": "home", "name": "Home"},
        "away_team": {"id": "away", "name": "Away"},
        "home_score": home_score,
        "away_score": away_score,
        "actual_result": (
            "Home Win"
            if home_score > away_score
            else "Away Win"
            if home_score < away_score
            else "Draw"
        ),
    }


def history_prediction(match_id="1", predicted_result="Home Win"):
    return {
        "id": match_id,
        "league_id": "pl",
        "league_name": "Premier League",
        "kickoff": "2026-09-01T12:00:00Z",
        "home_team": {"id": "home", "name": "Home"},
        "away_team": {"id": "away", "name": "Away"},
        "home_win_probability": 60.0,
        "draw_probability": 20.0,
        "away_win_probability": 20.0,
        "predicted_result": predicted_result,
        "confidence": "High",
        "data_quality": "full_history",
        "model_version": "test-model",
    }


def test_completed_marks_missing(tmp_path, monkeypatch):
    module = mod("build_completed_matches.py")
    completed = run_completed_builder(
        module,
        monkeypatch,
        tmp_path,
        [completed_result()],
        [],
    )

    assert completed[0]["prediction_status"] == "missing"
    assert completed[0]["prediction_available"] is False
    assert completed[0]["is_correct"] is None


def test_completed_marks_recorded_and_correct(tmp_path, monkeypatch):
    module = mod("build_completed_matches.py")
    completed = run_completed_builder(
        module,
        monkeypatch,
        tmp_path,
        [completed_result(home_score=2, away_score=1)],
        [history_prediction(predicted_result="Home Win")],
    )

    assert completed[0]["prediction_status"] == "recorded"
    assert completed[0]["prediction_available"] is True
    assert completed[0]["predicted_result"] == "Home Win"
    assert completed[0]["actual_result"] == "Home Win"
    assert completed[0]["is_correct"] is True


def test_completed_marks_recorded_and_incorrect(tmp_path, monkeypatch):
    module = mod("build_completed_matches.py")
    completed = run_completed_builder(
        module,
        monkeypatch,
        tmp_path,
        [completed_result(home_score=2, away_score=1)],
        [history_prediction(predicted_result="Away Win")],
    )

    assert completed[0]["prediction_status"] == "recorded"
    assert completed[0]["prediction_available"] is True
    assert completed[0]["predicted_result"] == "Away Win"
    assert completed[0]["actual_result"] == "Home Win"
    assert completed[0]["is_correct"] is False


def test_completed_marks_recorded_draw_correctly(tmp_path, monkeypatch):
    module = mod("build_completed_matches.py")
    completed = run_completed_builder(
        module,
        monkeypatch,
        tmp_path,
        [completed_result(home_score=1, away_score=1)],
        [history_prediction(predicted_result="Draw")],
    )

    assert completed[0]["actual_result"] == "Draw"
    assert completed[0]["is_correct"] is True


def test_completed_does_not_match_different_id(tmp_path, monkeypatch):
    module = mod("build_completed_matches.py")
    completed = run_completed_builder(
        module,
        monkeypatch,
        tmp_path,
        [completed_result(match_id="result-1")],
        [history_prediction(match_id="prediction-2")],
    )

    assert completed[0]["prediction_status"] == "missing"
    assert completed[0]["prediction_available"] is False


def test_migrate_does_not_duplicate_existing_history_entry(tmp_path, monkeypatch):
    module = mod("migrate_predictions_to_history.py")
    matches_path = tmp_path / "matches.json"
    history_path = tmp_path / "prediction_history.json"
    temp_history_path = tmp_path / "prediction_history.json.tmp"
    backup_path = tmp_path / "backup.json"

    existing = history_prediction(match_id="same-id", predicted_result="Home Win")
    current = history_prediction(match_id="same-id", predicted_result="Away Win")
    matches_path.write_text(json.dumps([current]), encoding="utf-8")
    history_path.write_text(json.dumps([existing]), encoding="utf-8")

    monkeypatch.setattr(module, "MATCHES_PATH", matches_path)
    monkeypatch.setattr(module, "HISTORY_PATH", history_path)
    monkeypatch.setattr(module, "TEMP_HISTORY_PATH", temp_history_path)
    monkeypatch.setattr(module, "BACKUP_PATH", backup_path)

    module.main()

    history = json.loads(history_path.read_text(encoding="utf-8"))
    matching = [item for item in history if item.get("id") == "same-id"]
    assert len(matching) == 1
    assert matching[0]["predicted_result"] == "Home Win"
