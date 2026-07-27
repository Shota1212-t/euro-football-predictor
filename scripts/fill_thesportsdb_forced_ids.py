from __future__ import annotations

import json
import os
import shutil
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache" / "thesportsdb"
BACKUP_DIR = DATA_DIR / "forced_profile_backup"

TEAMS_PATH = PROCESSED_DIR / "teams.json"
PLAYERS_PATH = PROCESSED_DIR / "players.json"
STAFF_PATH = PROCESSED_DIR / "staff.json"
MANAGERS_PATH = PROCESSED_DIR / "managers.json"
STATUS_PATH = PROCESSED_DIR / "thesportsdb_forced_status.json"

BASE_URL = "https://www.thesportsdb.com/api/v1/json/123"

FORCED_TEAMS = {
    "fd-108": {"thesportsdb_id": "133681", "expected_name": "Inter Milan"},
    "fd-529": {"thesportsdb_id": "133719", "expected_name": "Rennes"},
}

STAFF_KEYWORDS = ("coach", "manager", "director")
PRIMARY_MANAGER_ROLES = {"manager", "head coach", "caretaker manager"}


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


def backup_once(paths: list[Path]) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if not path.exists():
            continue
        destination = BACKUP_DIR / path.name
        if not destination.exists():
            shutil.copy2(path, destination)


def calculate_age(date_born: str | None) -> int | None:
    if not date_born:
        return None
    try:
        born = date.fromisoformat(date_born[:10])
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


def normalized_role(value: str | None) -> str:
    return " ".join((value or "").lower().replace("-", " ").split())


def is_staff(position: str | None) -> bool:
    role = normalized_role(position)
    return any(keyword in role for keyword in STAFF_KEYWORDS)


def player_record(raw: dict, team: dict) -> dict:
    player_id = f"tsdb-{raw['idPlayer']}"
    return {
        "id": player_id,
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
    staff_id = f"tsdb-{raw['idPlayer']}"
    return {
        "id": staff_id,
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


def manager_record(staff: dict) -> dict:
    return {
        "id": staff["id"],
        "name": staff["name"],
        "team_id": staff["team_id"],
        "nationality": staff.get("nationality"),
        "age": staff.get("age"),
        "appointed": None,
        "photo_url": staff.get("photo_url"),
        "matches": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "avg_goals_for": None,
        "avg_goals_against": None,
        "recent_form": None,
        "role": staff.get("role"),
        "data_source": "TheSportsDB",
        "statistics_available": False,
    }


def fetch_bundle(client: httpx.Client, internal_id: str, source_id: str) -> dict:
    team_response = client.get("/lookupteam.php", params={"id": source_id})
    team_response.raise_for_status()
    teams = team_response.json().get("teams") or []
    if not teams:
        raise RuntimeError(f"TheSportsDBチームが見つかりません: {source_id}")

    roster_response = client.get("/lookup_all_players.php", params={"id": source_id})
    roster_response.raise_for_status()
    roster = roster_response.json().get("player") or []
    if not roster:
        raise RuntimeError(f"選手・スタッフが0件です: {source_id}")

    return {
        "status": "success",
        "internal_id": internal_id,
        "expected_team": None,
        "attempted_queries": [f"forced_id:{source_id}"],
        "team": teams[0],
        "roster": roster,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "forced_mapping": True,
    }


def main() -> None:
    teams = read_json(TEAMS_PATH, {})
    players = read_json(PLAYERS_PATH, {})
    staff = read_json(STAFF_PATH, {})
    managers = read_json(MANAGERS_PATH, {})
    if len(teams) != 96:
        raise RuntimeError(f"teams.jsonは96クラブである必要があります: {len(teams)}")

    backup_once([TEAMS_PATH, PLAYERS_PATH, STAFF_PATH, MANAGERS_PATH])
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    updated = []

    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        for index, (internal_id, mapping) in enumerate(FORCED_TEAMS.items(), start=1):
            team = teams[internal_id]
            source_id = mapping["thesportsdb_id"]
            print(f"[{index}/{len(FORCED_TEAMS)}] {team['name']} -> {source_id}")
            bundle = fetch_bundle(client, internal_id, source_id)
            source_team = bundle["team"]

            # Replace the previous not_found cache with the verified bundle.
            atomic_write_json(CACHE_DIR / f"{internal_id}.json", bundle)

            team["thesportsdb_id"] = source_id
            team["logo_url"] = source_team.get("strBadge") or team.get("logo_url")
            team["stadium"] = source_team.get("strStadium") or team.get("stadium")
            team["stadium_thumb_url"] = source_team.get("strStadiumThumb")
            team["website"] = source_team.get("strWebsite") or team.get("website")
            team["founded"] = parse_number(source_team.get("intFormedYear")) or team.get("founded")
            team["club_colors"] = source_team.get("strColour1") or team.get("club_colors")
            team["description_ja"] = source_team.get("strDescriptionJP")
            team["description_en"] = source_team.get("strDescriptionEN")
            team["data_source_profile"] = "TheSportsDB"

            # Remove any fallback records for these teams before inserting verified TSDB records.
            players = {
                key: value
                for key, value in players.items()
                if value.get("team_id") != internal_id
            }
            staff = {
                key: value
                for key, value in staff.items()
                if value.get("team_id") != internal_id
            }
            managers = {
                key: value
                for key, value in managers.items()
                if value.get("team_id") != internal_id
            }

            team_staff = []
            for raw in bundle["roster"]:
                if not raw.get("idPlayer") or not raw.get("strPlayer"):
                    continue
                if is_staff(raw.get("strPosition")):
                    record = staff_record(raw, team)
                    staff[record["id"]] = record
                    team_staff.append(record)
                else:
                    record = player_record(raw, team)
                    players[record["id"]] = record

            primary = next(
                (
                    record
                    for record in team_staff
                    if normalized_role(record.get("role")) in PRIMARY_MANAGER_ROLES
                ),
                None,
            )
            if primary:
                managers[primary["id"]] = manager_record(primary)
                team["manager_id"] = primary["id"]
            else:
                team["manager_id"] = None

            updated.append(
                {
                    "team_id": internal_id,
                    "team_name": team["name"],
                    "thesportsdb_id": source_id,
                    "roster_count": len(bundle["roster"]),
                }
            )
            print(f"  roster={len(bundle['roster'])}")
            if index < len(FORCED_TEAMS):
                time.sleep(4)

    valid_team_ids = set(teams)
    for collection_name, collection in (
        ("players", players),
        ("staff", staff),
        ("managers", managers),
    ):
        for item_id, item in collection.items():
            if item.get("team_id") not in valid_team_ids:
                raise RuntimeError(f"{collection_name}.{item_id}のteam_idが不正です")

    atomic_write_json(TEAMS_PATH, teams)
    atomic_write_json(PLAYERS_PATH, players)
    atomic_write_json(STAFF_PATH, staff)
    atomic_write_json(MANAGERS_PATH, managers)

    teams_with_players = {
        item.get("team_id")
        for item in players.values()
        if item.get("team_id")
    }
    missing = sorted(
        team["name"]
        for team in teams.values()
        if team["id"] not in teams_with_players
    )
    status = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_teams": updated,
        "players_total": len(players),
        "staff_total": len(staff),
        "managers_total": len(managers),
        "teams_with_players": len(teams_with_players),
        "teams_without_players": len(missing),
        "missing_team_names": missing,
        "deportivo_note": (
            "RC Deportivo La Coruna remained unmatched to avoid linking the women, "
            "reserve, or another Deportivo club by mistake."
        ),
    }
    atomic_write_json(STATUS_PATH, status)

    print("\nTheSportsDB強制ID補完完了")
    print(f"選手総数: {len(players)}件")
    print(f"スタッフ総数: {len(staff)}件")
    print(f"主監督総数: {len(managers)}件")
    print(f"選手あり: {len(teams_with_players)}/96クラブ")
    print(f"選手なし: {len(missing)}/96クラブ")
    for name in missing:
        print(f"  MISSING: {name}")


if __name__ == "__main__":
    main()
