"""データアクセス層。"""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from .config import PROCESSED_DIR, PREDICTIONS_DIR, DATA_DIR


@lru_cache(maxsize=64)
def _read_json_cached(path_text: str):
    path = Path(path_text)
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _read_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return _read_json_cached(str(path.resolve()))
    except (json.JSONDecodeError, OSError):
        return default


def is_stale(iso_timestamp: str | None, hours: int = 24) -> bool:
    if not iso_timestamp:
        return True
    from datetime import datetime, timezone
    try:
        timestamp = datetime.fromisoformat(iso_timestamp)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - timestamp).total_seconds() > hours * 3600
    except ValueError:
        return True


def get_leagues() -> list[dict]:
    return _read_json(PROCESSED_DIR / "leagues.json", [])


def get_league(league_id: str) -> dict | None:
    return next((item for item in get_leagues() if item["id"] == league_id), None)


def get_teams() -> dict[str, dict]:
    return _read_json(PROCESSED_DIR / "teams.json", {})


def get_team(team_id: str) -> dict | None:
    return get_teams().get(team_id)




def _team_visual(team_id: str | None) -> dict:
    team = get_team(team_id) if team_id else None
    return {"logo_url": (team or {}).get("logo_url"), "color": (team or {}).get("color")}


def _enrich_team_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return payload
    enriched = dict(payload)
    visual = _team_visual(enriched.get("id"))
    enriched["logo_url"] = enriched.get("logo_url") or visual["logo_url"]
    enriched["color"] = enriched.get("color") or visual["color"] or "#334155"
    return enriched


def _enrich_prediction(match: dict) -> dict:
    enriched = dict(match)
    enriched["home_team"] = _enrich_team_payload(match.get("home_team"))
    enriched["away_team"] = _enrich_team_payload(match.get("away_team"))
    return enriched

def get_players() -> dict[str, dict]:
    return _read_json(PROCESSED_DIR / "players.json", {})


def get_player(player_id: str) -> dict | None:
    return get_players().get(player_id)


def get_managers() -> dict[str, dict]:
    return _read_json(PROCESSED_DIR / "managers.json", {})


def get_manager(manager_id: str) -> dict | None:
    return get_managers().get(manager_id)


def get_standings(league_id: str, tab: str = "total") -> list[dict]:
    data = _read_json(PROCESSED_DIR / "standings" / f"{league_id}.json", {})
    rows = data if isinstance(data, list) else data.get(tab) or data.get("total", [])
    return [{**row, "team_logo_url": _team_visual(row.get("team_id"))["logo_url"]} for row in rows]

def get_rankings_payload(league_id: str) -> dict:
    return _read_json(
        PROCESSED_DIR / "rankings" / f"{league_id}.json",
        {
            "metadata": {
                "league_id": league_id,
                "state": "not_generated",
                "message": "ランキングデータをまだ生成していません。",
                "available_types": [],
                "unavailable_types": [],
            },
            "goals": [],
            "assists": [],
            "appearances": [],
            "yellow_cards": [],
            "red_cards": [],
        },
    )


def get_rankings(league_id: str, kind: str = "goals") -> list[dict]:
    return get_rankings_payload(league_id).get(kind, [])


def get_predictions() -> list[dict]:
    return [_enrich_prediction(item) for item in _read_json(PREDICTIONS_DIR / "matches.json", [])]

def get_prediction(match_id: str) -> dict | None:
    return next((item for item in get_predictions() if item["id"] == match_id), None)


def get_model_performance() -> dict | None:
    return _read_json(PREDICTIONS_DIR / "model_performance.json", None)


def get_data_status() -> list[dict]:
    return _read_json(DATA_DIR / "data_status.json", [])


def get_data_sources() -> list[dict]:
    return _read_json(DATA_DIR / "data_sources.json", [])
