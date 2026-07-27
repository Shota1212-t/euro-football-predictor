from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache" / "football_data_org_profiles"
BACKUP_DIR = DATA_DIR / "profile_fallback_backup"

TEAMS_PATH = PROCESSED_DIR / "teams.json"
PLAYERS_PATH = PROCESSED_DIR / "players.json"
MANAGERS_PATH = PROCESSED_DIR / "managers.json"
STATUS_PATH = PROCESSED_DIR / "football_data_profile_status.json"

load_dotenv(ROOT / ".env")
API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")
BASE_URL = "https://api.football-data.org/v4"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "TheSportsDBで選手を取得できなかった5大リーグのクラブを、"
            "football-data.orgのsquadで補完します。"
        )
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=6.0,
        help="APIリクエスト間の待機秒数。既定値は6秒。",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="football-data.orgプロフィールキャッシュを再取得します。",
    )
    return parser.parse_args()


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


def player_record(raw: dict, team: dict) -> dict:
    return {
        "id": f"fdp-{raw['id']}",
        "football_data_player_id": raw["id"],
        "name": raw.get("name") or "Unknown",
        "team_id": team["id"],
        "league_id": team["league_id"],
        "position": raw.get("position"),
        "nationality": raw.get("nationality"),
        "date_of_birth": raw.get("dateOfBirth"),
        "age": calculate_age(raw.get("dateOfBirth")),
        "shirt_number": None,
        "photo_url": None,
        "cutout_url": None,
        "height": None,
        "weight": None,
        "status": "Active",
        "description_ja": None,
        "description_en": None,
        "data_source": "football-data.org",
        "statistics_available": False,
        "appearances": 0,
        "goals": 0,
        "assists": 0,
        "yellow_cards": 0,
        "red_cards": 0,
        "league_rank": None,
        "team_rank": None,
    }


def manager_record(raw: dict, team: dict) -> dict | None:
    if not raw or not raw.get("name"):
        return None
    source_id = raw.get("id") or team["api_id"]
    return {
        "id": f"fdm-{source_id}",
        "football_data_manager_id": raw.get("id"),
        "name": raw["name"],
        "team_id": team["id"],
        "nationality": raw.get("nationality"),
        "age": calculate_age(raw.get("dateOfBirth")),
        "appointed": (raw.get("contract") or {}).get("start"),
        "photo_url": None,
        "matches": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "avg_goals_for": None,
        "avg_goals_against": None,
        "recent_form": None,
        "role": "Head Coach",
        "data_source": "football-data.org",
        "statistics_available": False,
    }


def fetch_profile(client: httpx.Client, team: dict) -> dict:
    response = client.get(f"/teams/{team['api_id']}")
    response.raise_for_status()
    return response.json()


def validate_outputs(teams: dict, players: dict, managers: dict) -> None:
    if len(teams) != 96:
        raise ValueError(f"チーム数が96ではありません: {len(teams)}")
    team_ids = set(teams)
    for collection_name, collection in (
        ("players", players),
        ("managers", managers),
    ):
        for item_id, item in collection.items():
            if item.get("team_id") not in team_ids:
                raise ValueError(
                    f"{collection_name}.{item_id}のteam_idが不正です"
                )


def main() -> None:
    args = parse_args()
    if not API_KEY:
        raise RuntimeError("FOOTBALL_DATA_API_KEYが未設定です")

    teams = read_json(TEAMS_PATH, {})
    players = read_json(PLAYERS_PATH, {})
    managers = read_json(MANAGERS_PATH, {})
    if len(teams) != 96:
        raise RuntimeError(f"teams.jsonは96クラブである必要があります: {len(teams)}")

    teams_with_players = {
        item.get("team_id")
        for item in players.values()
        if item.get("team_id")
    }
    targets = [
        team
        for team in teams.values()
        if team["id"] not in teams_with_players
    ]
    targets.sort(key=lambda item: (item.get("league_id", ""), item.get("name", "")))

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fetched = 0
    cache_hits = 0
    failures = []
    last_request_at = 0.0

    with httpx.Client(
        base_url=BASE_URL,
        headers={"X-Auth-Token": API_KEY},
        timeout=30,
    ) as client:
        for index, team in enumerate(targets, start=1):
            cache_path = CACHE_DIR / f"{team['id']}.json"
            if cache_path.exists() and not args.refresh:
                profile = read_json(cache_path, {})
                cache_hits += 1
                print(f"[{index}/{len(targets)}] CACHE {team['name']}")
            else:
                elapsed = time.monotonic() - last_request_at
                if elapsed < args.delay:
                    time.sleep(args.delay - elapsed)
                print(f"[{index}/{len(targets)}] FETCH {team['name']}")
                try:
                    profile = fetch_profile(client, team)
                    last_request_at = time.monotonic()
                    atomic_write_json(cache_path, profile)
                    fetched += 1
                except (httpx.RequestError, httpx.HTTPStatusError) as error:
                    failures.append(
                        {
                            "team_id": team["id"],
                            "name": team["name"],
                            "error": str(error),
                        }
                    )
                    print(f"  ERROR: {error}")
                    continue

            team["logo_url"] = profile.get("crest") or team.get("logo_url")
            team["stadium"] = profile.get("venue") or team.get("stadium")
            team["website"] = profile.get("website") or team.get("website")
            team["founded"] = profile.get("founded") or team.get("founded")
            team["club_colors"] = profile.get("clubColors") or team.get("club_colors")
            team["data_source_profile"] = (
                team.get("data_source_profile") or "football-data.org"
            )

            # Rebuild only this team's fallback players, preserving TheSportsDB data.
            players = {
                key: value
                for key, value in players.items()
                if not (
                    value.get("team_id") == team["id"]
                    and value.get("data_source") == "football-data.org"
                )
            }
            for raw_player in profile.get("squad") or []:
                if raw_player.get("id") and raw_player.get("name"):
                    record = player_record(raw_player, team)
                    players[record["id"]] = record

            manager = manager_record(profile.get("coach") or {}, team)
            if manager:
                managers[manager["id"]] = manager
                team["manager_id"] = manager["id"]

            print(
                f"  squad={len(profile.get('squad') or [])} / "
                f"coach={bool((profile.get('coach') or {}).get('name'))}"
            )

    validate_outputs(teams, players, managers)
    if failures:
        atomic_write_json(
            STATUS_PATH,
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "success": False,
                "targets": len(targets),
                "failures": failures,
            },
        )
        raise RuntimeError(
            f"football-data.org補完で{len(failures)}クラブ失敗しました。"
            "既存公開JSONは更新していません。"
        )

    backup_once([TEAMS_PATH, PLAYERS_PATH, MANAGERS_PATH])
    atomic_write_json(TEAMS_PATH, teams)
    atomic_write_json(PLAYERS_PATH, players)
    atomic_write_json(MANAGERS_PATH, managers)

    teams_with_players_after = {
        item.get("team_id")
        for item in players.values()
        if item.get("team_id")
    }
    still_missing = sorted(
        team["name"]
        for team in teams.values()
        if team["id"] not in teams_with_players_after
    )
    status = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "success": True,
        "targets": len(targets),
        "fetched": fetched,
        "cache_hits": cache_hits,
        "players_total": len(players),
        "managers_total": len(managers),
        "teams_with_players": len(teams_with_players_after),
        "teams_without_players": len(still_missing),
        "missing_team_names": still_missing,
    }
    atomic_write_json(STATUS_PATH, status)

    print("\nfootball-data.orgプロフィール補完完了")
    print(f"補完対象: {len(targets)}クラブ")
    print(f"新規取得: {fetched}クラブ")
    print(f"キャッシュ: {cache_hits}クラブ")
    print(f"選手総数: {len(players)}件")
    print(f"選手あり: {len(teams_with_players_after)}/96クラブ")
    print(f"選手なし: {len(still_missing)}/96クラブ")
    if still_missing:
        for name in still_missing:
            print(f"  MISSING: {name}")


if __name__ == "__main__":
    main()
