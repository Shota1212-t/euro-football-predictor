from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RANKINGS_DIR = PROCESSED_DIR / "rankings"
CACHE_DIR = DATA_DIR / "cache" / "football_data_org_rankings"
BACKUP_DIR = DATA_DIR / "rankings_backup"
STATUS_PATH = PROCESSED_DIR / "rankings_status.json"

load_dotenv(ROOT / ".env")
API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")
BASE_URL = "https://api.football-data.org/v4"

COMPETITIONS = {
    "PL": "pl",
    "PD": "laliga",
    "SA": "seriea",
    "BL1": "bundesliga",
    "FL1": "ligue1",
}


def read_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        json.loads(temporary.read_text(encoding="utf-8"))
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def ranking_row(item: dict, value: int) -> dict:
    player = item.get("player") or {}
    team = item.get("team") or {}
    player_id = player.get("id")
    team_id = team.get("id")
    return {
        "player_id": f"fdp-{int(player_id)}" if player_id is not None else None,
        "football_data_player_id": player_id,
        "player_name": player.get("name") or "Unknown",
        "team_id": f"fd-{int(team_id)}" if team_id is not None else None,
        "football_data_team_id": team_id,
        "team_name": team.get("name") or "Unknown",
        "position": player.get("position"),
        "nationality": player.get("nationality"),
        "value": int(value),
    }


def build_ranking(items: list[dict], field: str) -> list[dict]:
    rows = []
    for item in items:
        value = item.get(field)
        if value is None:
            continue
        rows.append(ranking_row(item, value))
    rows.sort(key=lambda row: (-row["value"], row["player_name"]))
    return rows


def build_payload(api_payload: dict, code: str, league_id: str) -> dict:
    season = api_payload.get("season") or {}
    scorers = api_payload.get("scorers") or []
    competition = api_payload.get("competition") or {}
    now = datetime.now(timezone.utc).isoformat()
    season_start = season.get("startDate")
    today = datetime.now(timezone.utc).date().isoformat()
    preseason = bool(season_start and today < season_start)

    goals = build_ranking(scorers, "goals")
    assists = build_ranking(scorers, "assists")
    appearances = build_ranking(scorers, "playedMatches")

    if scorers:
        state = "available"
        message = None
    elif preseason:
        state = "preseason"
        message = "シーズン開幕前のため、選手ランキングはまだありません。"
    else:
        state = "empty"
        message = "ランキングデータはまだ提供されていません。"

    return {
        "metadata": {
            "league_id": league_id,
            "competition_code": competition.get("code") or code,
            "competition_name": competition.get("name"),
            "season_id": season.get("id"),
            "season_start": season_start,
            "season_end": season.get("endDate"),
            "current_matchday": season.get("currentMatchday"),
            "source": "football-data.org",
            "updated_at": now,
            "state": state,
            "message": message,
            "available_types": ["goals", "assists", "appearances"],
            "unavailable_types": ["yellow_cards", "red_cards"],
        },
        "goals": goals,
        "assists": assists,
        "appearances": appearances,
        "yellow_cards": [],
        "red_cards": [],
    }


def main() -> None:
    if not API_KEY:
        raise RuntimeError("FOOTBALL_DATA_API_KEYが未設定です")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    generated: dict[str, dict] = {}
    failures = []

    with httpx.Client(
        base_url=BASE_URL,
        headers={"X-Auth-Token": API_KEY},
        timeout=30,
    ) as client:
        for index, (code, league_id) in enumerate(COMPETITIONS.items(), start=1):
            print(f"[{index}/{len(COMPETITIONS)}] {league_id}: 得点ランキング取得")
            try:
                response = client.get(
                    f"/competitions/{code}/scorers",
                    params={"limit": 100},
                )
                response.raise_for_status()
                raw = response.json()
                atomic_write_json(CACHE_DIR / f"{league_id}.json", raw)
                generated[league_id] = build_payload(raw, code, league_id)
                metadata = generated[league_id]["metadata"]
                print(
                    f"  state={metadata['state']} / "
                    f"goals={len(generated[league_id]['goals'])}"
                )
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as error:
                failures.append({"league_id": league_id, "error": str(error)})
                print(f"  ERROR: {error}")
            if index < len(COMPETITIONS):
                time.sleep(6)

    if failures or len(generated) != len(COMPETITIONS):
        atomic_write_json(
            STATUS_PATH,
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "success": False,
                "failures": failures,
                "generated_leagues": sorted(generated),
            },
        )
        raise RuntimeError(
            "ランキング取得に失敗したリーグがあります。既存ランキングJSONは更新していません。"
        )

    RANKINGS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for league_id, payload in generated.items():
        destination = RANKINGS_DIR / f"{league_id}.json"
        backup = BACKUP_DIR / f"{league_id}.json"
        if destination.exists() and not backup.exists():
            shutil.copy2(destination, backup)
        atomic_write_json(destination, payload)

    states = {
        league_id: payload["metadata"]["state"]
        for league_id, payload in generated.items()
    }
    status = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "success": True,
        "source": "football-data.org",
        "leagues": len(generated),
        "states": states,
        "available_types": ["goals", "assists", "appearances"],
        "unavailable_types": ["yellow_cards", "red_cards"],
    }
    atomic_write_json(STATUS_PATH, status)

    print("\n選手ランキング更新完了")
    for league_id, state in states.items():
        print(f"{league_id}: {state}")
    print(f"保存先: {RANKINGS_DIR}")


if __name__ == "__main__":
    main()
