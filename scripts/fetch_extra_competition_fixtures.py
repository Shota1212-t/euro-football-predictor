from __future__ import annotations

import json
import os
import time
import unicodedata
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache" / "extra_fixtures"
MANUAL_PATH = DATA_DIR / "manual" / "extra_fixtures.json"
TEAMS_PATH = PROCESSED_DIR / "teams.json"
OUTPUT_PATH = PROCESSED_DIR / "extra_fixtures.json"
STATUS_PATH = PROCESSED_DIR / "extra_fixtures_status.json"

load_dotenv(ROOT / ".env")
FOOTBALL_DATA_API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")
FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
THESPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123"

EUROPEAN_MARKERS = (
    "champions league", "europa league", "conference league", "uefa super cup",
)
DOMESTIC_CUP_MARKERS = (
    "fa cup", "league cup", "efl cup", "carabao cup", "copa del rey",
    "coppa italia", "dfb-pokal", "dfb pokal", "coupe de france",
    "community shield", "supercoppa", "supercopa", "trophee des champions",
)
LEAGUE_MARKERS = (
    "premier league", "la liga", "primera division", "serie a", "bundesliga", "ligue 1",
)


def read_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def atomic_write(path: Path, payload: Any) -> None:
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


def normalize(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def classify_competition(name: str | None) -> str:
    key = normalize(name)
    if any(marker in key for marker in EUROPEAN_MARKERS):
        return "european"
    if any(marker in key for marker in DOMESTIC_CUP_MARKERS):
        return "domestic_cup"
    if any(marker in key for marker in LEAGUE_MARKERS):
        return "league"
    return "unknown"


def iso_kickoff(date_value: str | None, time_value: str | None = None) -> str | None:
    if not date_value:
        return None
    time_text = time_value or "00:00:00"
    candidate = f"{date_value}T{time_text}"
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_champions_league(client: httpx.Client) -> list[dict]:
    response = client.get("/competitions/CL/matches")
    response.raise_for_status()
    events = []
    for match in response.json().get("matches", []):
        home = match.get("homeTeam") or {}
        away = match.get("awayTeam") or {}
        team_ids = [
            f"fd-{int(team_id)}"
            for team_id in (home.get("id"), away.get("id"))
            if team_id is not None
        ]
        events.append({
            "id": f"fd-cl-{match.get('id')}",
            "source": "football-data.org",
            "competition_name": "UEFA Champions League",
            "competition_type": "european",
            "kickoff": match.get("utcDate"),
            "status": match.get("status"),
            "team_ids": team_ids,
            "home_team_id": team_ids[0] if team_ids else None,
            "away_team_id": team_ids[1] if len(team_ids) > 1 else None,
            "home_score": (match.get("score") or {}).get("fullTime", {}).get("home"),
            "away_score": (match.get("score") or {}).get("fullTime", {}).get("away"),
            "had_extra_time_or_penalties": (
                (match.get("score") or {}).get("duration") in {"EXTRA_TIME", "PENALTY_SHOOTOUT"}
            ),
            "data_quality": "official",
        })
    return events


def cache_is_current(path: Path) -> bool:
    if not path.exists():
        return False
    modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date()
    return modified == datetime.now(timezone.utc).date()


def fetch_thesportsdb_last_events(teams: dict[str, dict]) -> tuple[list[dict], int, int]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    events = []
    success = 0
    unavailable = 0
    with httpx.Client(timeout=30) as client:
        candidates = [team for team in teams.values() if team.get("thesportsdb_id")]
        for index, team in enumerate(candidates, start=1):
            team_id = team["id"]
            cache = CACHE_DIR / f"tsdb_{team_id}.json"
            try:
                if cache_is_current(cache):
                    payload = read_json(cache, {})
                else:
                    response = client.get(
                        f"{THESPORTSDB_BASE}/eventslast.php",
                        params={"id": str(team["thesportsdb_id"])},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    atomic_write(cache, payload)
                    time.sleep(0.5)
                raw_events = payload.get("results") or payload.get("events") or []
                success += 1
                for raw in raw_events:
                    competition_name = raw.get("strLeague") or ""
                    competition_type = classify_competition(competition_name)
                    if competition_type == "league":
                        continue
                    kickoff = iso_kickoff(raw.get("dateEvent"), raw.get("strTime"))
                    if not kickoff:
                        continue
                    events.append({
                        "id": f"tsdb-{raw.get('idEvent') or team_id + '-' + raw.get('dateEvent', '')}",
                        "source": "TheSportsDB",
                        "competition_name": competition_name,
                        "competition_type": competition_type,
                        "kickoff": kickoff,
                        "status": raw.get("strStatus"),
                        "team_ids": [team_id],
                        "home_team_id": None,
                        "away_team_id": None,
                        "home_score": raw.get("intHomeScore"),
                        "away_score": raw.get("intAwayScore"),
                        "had_extra_time_or_penalties": False,
                        "data_quality": "supplemental_last_event_only",
                    })
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError, OSError):
                unavailable += 1
            if index % 20 == 0 or index == len(candidates):
                print(f"TheSportsDB直前試合: {index}/{len(candidates)}")
    return events, success, unavailable


def deduplicate(events: list[dict]) -> list[dict]:
    ranked = {"official": 3, "manual": 2, "supplemental_last_event_only": 1}
    unique: dict[tuple, dict] = {}
    for event in events:
        key = (
            event.get("kickoff", "")[:10],
            tuple(sorted(event.get("team_ids") or [])),
            event.get("competition_type"),
        )
        current = unique.get(key)
        if current is None or ranked.get(event.get("data_quality"), 0) > ranked.get(current.get("data_quality"), 0):
            unique[key] = event
    return sorted(unique.values(), key=lambda item: item.get("kickoff") or "")


def main() -> None:
    if not FOOTBALL_DATA_API_KEY:
        raise RuntimeError("FOOTBALL_DATA_API_KEYが未設定です")
    teams = read_json(TEAMS_PATH, {})
    if not isinstance(teams, dict) or not teams:
        raise RuntimeError("teams.jsonが不正または空です")

    failures = []
    events = []
    try:
        with httpx.Client(
            base_url=FOOTBALL_DATA_BASE,
            headers={"X-Auth-Token": FOOTBALL_DATA_API_KEY},
            timeout=30,
        ) as client:
            cl_events = fetch_champions_league(client)
            events.extend(cl_events)
            print(f"Champions League: {len(cl_events)}試合")
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as error:
        failures.append(f"Champions League: {error}")

    tsdb_events, tsdb_success, tsdb_unavailable = fetch_thesportsdb_last_events(teams)
    events.extend(tsdb_events)
    manual = read_json(MANUAL_PATH, [])
    if isinstance(manual, list):
        for event in manual:
            events.append({**event, "source": event.get("source", "manual"), "data_quality": "manual"})

    final_events = deduplicate(events)
    official_count = sum(1 for item in final_events if item.get("data_quality") == "official")
    supplemental_count = sum(1 for item in final_events if item.get("data_quality") == "supplemental_last_event_only")
    manual_count = sum(1 for item in final_events if item.get("data_quality") == "manual")

    if failures and OUTPUT_PATH.exists():
        atomic_write(STATUS_PATH, {
            "success": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "failures": failures,
            "existing_data_preserved": True,
        })
        raise RuntimeError("追加大会の公式データ取得に失敗したため既存JSONを維持しました")

    atomic_write(OUTPUT_PATH, final_events)
    atomic_write(STATUS_PATH, {
        "success": not failures,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "records": len(final_events),
        "official_records": official_count,
        "supplemental_records": supplemental_count,
        "manual_records": manual_count,
        "thesportsdb_teams_success": tsdb_success,
        "thesportsdb_teams_unavailable": tsdb_unavailable,
        "coverage": {
            "league": "Football-Data.co.uk",
            "champions_league": "available",
            "other_european_and_domestic_cups": "partial_last_event_only",
            "extra_time_and_penalties": "partial",
        },
        "failures": failures,
    })
    print(f"追加大会試合: {len(final_events)}件")
    print(f"公式CL: {official_count}件 / TheSportsDB補助: {supplemental_count}件 / 手動: {manual_count}件")
    print(f"保存先: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
