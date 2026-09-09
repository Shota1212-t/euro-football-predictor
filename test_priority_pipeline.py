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


def test_completed_marks_missing(tmp_path, monkeypatch):
    module = mod("build_completed_matches.py")
    results_path = tmp_path / "r.json"
    history_path = tmp_path / "h.json"
    output_path = tmp_path / "o.json"

    results_path.write_text(
        json.dumps(
            [
                {
                    "id": "1",
                    "home_score": 1,
                    "away_score": 0,
                    "actual_result": "Home Win",
                }
            ]
        ),
        encoding="utf-8",
    )
    history_path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(module, "R", results_path)
    monkeypatch.setattr(module, "H", history_path)
    monkeypatch.setattr(module, "O", output_path)
    monkeypatch.setattr(module, "T", output_path.with_suffix(".tmp"))

    module.main()

    completed = json.loads(output_path.read_text(encoding="utf-8"))
    assert completed[0]["prediction_status"] == "missing"
    assert completed[0]["prediction_available"] is False
