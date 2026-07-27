from __future__ import annotations

import json
import os
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache" / "thesportsdb"
BACKUP_DIR = DATA_DIR / "deportivo_profile_backup"

TEAMS_PATH = PROCESSED_DIR / "teams.json"
PLAYERS_PATH = PROCESSED_DIR / "players.json"
STAFF_PATH = PROCESSED_DIR / "staff.json"
MANAGERS_PATH = PROCESSED_DIR / "managers.json"
STATUS_PATH = PROCESSED_DIR / "deportivo_profile_status.json"

TEAM_ID = "fd-560"
THESPORTSDB_ID = "133816"
BASE_URL = "https://www.thesportsdb.com/api/v1/json/123"


def read_json(path: Path, default: Any):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


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


def backup_once(paths: list[Path]) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.exists():
            destination = BACKUP_DIR / path.name
            if not destination.exists():
                shutil.copy2(path, destination)


def calculate_age(value: str | None) -> int | None:
    if not value:
        return None
    try:
        born = date.fromisoformat(value[:10])
    except ValueError:
        return None
    today = date.today()
    return today.year - born.year - (
        (today.month, today.day) < (born.month, born.day)
    )


def parse_number(value: str | None) -> int | None:
    if not value:
        return None
    digits = "".join(character for character in value if character.isdigit())
    return int(digits) if digits else None


def normalize_role(value: str | None) -> str:
    return " ".join((value or "").lower().replace("-", " ").split())


def is_staff(value: str | None) -> bool:
    role = normalize_role(value)
    return any(word in role for word in ("coach", "manager", "director"))


def player_record(raw: dict, team: dict) -> dict:
    return {
        "id": f"tsdb-{raw['idPlayer']}",
        "thesportsdb_id": raw.get("idPlayer"),
        "name": raw.get("strPlayer") or "Unknown",
        "team_id": team["id"],
        "league_id": team["league_id"],
        "position": raw.get("strPosition"),
        "nationality": raw.get("strNationality"),
        "date_of_birth": raw.get("dateBorn"),
        "age": calculate_age(raw.get("dateBorn")),
        "shirt_number": parse_number(raw.get("strNumber")),
        "photo_url": raw.get("strThumb") or raw.get("strCutout"),
        "cutout_url": raw.get("strCutout"),
        "height": raw.get("strHeight"),
        "weight": raw.get("strWeight"),
        "status": raw.get("strStatus"),
        "description_ja": raw.get("strDescriptionJP"),
        "description_en": raw.get("strDescriptionEN"),
        "data_source": "TheSportsDB",
        "statistics_available": False,
        "appearances": 0,
        "goals": 0,
        "assists": 0,
        "yellow_cards": 0,
        "red_cards": 0,
        "league_rank": None,
        "team_rank": None,
    }


def staff_record(raw: dict, team: dict) -> dict:
    return {
        "id": f"tsdb-{raw['idPlayer']}",
        "thesportsdb_id": raw.get("idPlayer"),
        "name": raw.get("strPlayer") or "Unknown",
        "team_id": team["id"],
        "league_id": team["league_id"],
        "role": raw.get("strPosition"),
        "nationality": raw.get("strNationality"),
        "date_of_birth": raw.get("dateBorn"),
        "age": calculate_age(raw.get("dateBorn")),
        "photo_url": raw.get("strThumb") or raw.get("strCutout"),
        "description_ja": raw.get("strDescriptionJP"),
        "description_en": raw.get("strDescriptionEN"),
        "data_source": "TheSportsDB",
    }


def main() -> None:
    teams = read_json(TEAMS_PATH, {})
    players = read_json(PLAYERS_PATH, {})
    staff = read_json(STAFF_PATH, {})
    managers = read_json(MANAGERS_PATH, {})
    if len(teams) != 96 or TEAM_ID not in teams:
        raise RuntimeError("96クラブ版teams.jsonまたはDeportivoが見つかりません")

    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        team_response = client.get("/lookupteam.php", params={"id": THESPORTSDB_ID})
        team_response.raise_for_status()
        source_teams = team_response.json().get("teams") or []
        roster_response = client.get(
            "/lookup_all_players.php",
            params={"id": THESPORTSDB_ID},
        )
        roster_response.raise_for_status()
        roster = roster_response.json().get("player") or []

    if not source_teams or not roster:
        raise RuntimeError("Deportivoのチーム情報または選手情報が取得できません")

    source_team = source_teams[0]
    if "deportivo" not in (source_team.get("strTeam") or "").lower():
        raise RuntimeError(f"別クラブを取得しました: {source_team.get('strTeam')}")

    team = teams[TEAM_ID]
    team["thesportsdb_id"] = THESPORTSDB_ID
    team["logo_url"] = source_team.get("strBadge") or team.get("logo_url")
    team["stadium"] = source_team.get("strStadium") or team.get("stadium")
    team["stadium_thumb_url"] = source_team.get("strStadiumThumb")
    team["website"] = source_team.get("strWebsite") or team.get("website")
    team["founded"] = parse_number(source_team.get("intFormedYear")) or team.get("founded")
    team["club_colors"] = source_team.get("strColour1") or team.get("club_colors")
    team["description_ja"] = source_team.get("strDescriptionJP")
    team["description_en"] = source_team.get("strDescriptionEN")
    team["data_source_profile"] = "TheSportsDB"

    players = {
        key: value for key, value in players.items()
        if value.get("team_id") != TEAM_ID
    }
    staff = {
        key: value for key, value in staff.items()
        if value.get("team_id") != TEAM_ID
    }
    managers = {
        key: value for key, value in managers.items()
        if value.get("team_id") != TEAM_ID
    }

    for raw in roster:
        if not raw.get("idPlayer") or not raw.get("strPlayer"):
            continue
        if is_staff(raw.get("strPosition")):
            record = staff_record(raw, team)
            staff[record["id"]] = record
        else:
            record = player_record(raw, team)
            players[record["id"]] = record

    backup_once([TEAMS_PATH, PLAYERS_PATH, STAFF_PATH, MANAGERS_PATH])
    atomic_write_json(TEAMS_PATH, teams)
    atomic_write_json(PLAYERS_PATH, players)
    atomic_write_json(STAFF_PATH, staff)
    atomic_write_json(MANAGERS_PATH, managers)

    cache_bundle = {
        "status": "success",
        "internal_id": TEAM_ID,
        "attempted_queries": [f"forced_id:{THESPORTSDB_ID}"],
        "team": source_team,
        "roster": roster,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "forced_mapping": True,
    }
    atomic_write_json(CACHE_DIR / f"{TEAM_ID}.json", cache_bundle)

    teams_with_players = {
        item.get("team_id") for item in players.values() if item.get("team_id")
    }
    missing = sorted(
        item["name"] for item in teams.values()
        if item["id"] not in teams_with_players
    )
    status = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "team_id": TEAM_ID,
        "thesportsdb_id": THESPORTSDB_ID,
        "roster_count": len(roster),
        "players_total": len(players),
        "staff_total": len(staff),
        "managers_total": len(managers),
        "teams_with_players": len(teams_with_players),
        "teams_without_players": len(missing),
        "missing_team_names": missing,
    }
    atomic_write_json(STATUS_PATH, status)

    print("Deportivoプロフィール補完完了")
    print(f"TheSportsDB ID: {THESPORTSDB_ID}")
    print(f"選手・スタッフ取得: {len(roster)}件")
    print(f"選手総数: {len(players)}件")
    print(f"選手あり: {len(teams_with_players)}/96クラブ")
    print(f"選手なし: {len(missing)}/96クラブ")


if __name__ == "__main__":
    main()
