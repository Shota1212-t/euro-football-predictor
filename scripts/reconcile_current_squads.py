from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import time
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
CACHE = DATA / "cache" / "football_data_org_squads"
BACKUP = DATA / "squad_reconciliation_backup"

TEAMS_PATH = PROCESSED / "teams.json"
PLAYERS_PATH = PROCESSED / "players.json"
STATUS_PATH = PROCESSED / "squad_reconciliation_status.json"

load_dotenv(ROOT / ".env")
API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")
BASE_URL = "https://api.football-data.org/v4"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="football-data.orgのsquadを現所属の基準にして選手一覧を再構築します。"
    )
    parser.add_argument("--delay", type=float, default=6.0)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--publish-partial", action="store_true")
    return parser.parse_args()


def read_json(path: Path, default: Any):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


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
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def age(value: str | None) -> int | None:
    if not value:
        return None
    try:
        born = date.fromisoformat(value[:10])
    except ValueError:
        return None
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def best_profile(fd_player: dict, candidates: list[dict]) -> dict | None:
    target = normalize(fd_player.get("name"))
    exact = [item for item in candidates if normalize(item.get("name")) == target]
    return exact[0] if len(exact) == 1 else None


def merged_player(fd_player: dict, team: dict, profile: dict | None) -> dict:
    profile = profile or {}
    return {
        "id": f"fdp-{fd_player['id']}",
        "football_data_player_id": fd_player["id"],
        "thesportsdb_id": profile.get("thesportsdb_id"),
        "name": fd_player.get("name") or profile.get("name") or "Unknown",
        "team_id": team["id"],
        "league_id": team["league_id"],
        "position": fd_player.get("position") or profile.get("position"),
        "nationality": fd_player.get("nationality") or profile.get("nationality"),
        "date_of_birth": fd_player.get("dateOfBirth") or profile.get("date_of_birth"),
        "age": age(fd_player.get("dateOfBirth") or profile.get("date_of_birth")),
        "shirt_number": profile.get("shirt_number"),
        "photo_url": profile.get("photo_url"),
        "cutout_url": profile.get("cutout_url"),
        "height": profile.get("height"),
        "weight": profile.get("weight"),
        "status": "Active",
        "description_ja": profile.get("description_ja"),
        "description_en": profile.get("description_en"),
        "data_source": "football-data.org + TheSportsDB" if profile else "football-data.org",
        "roster_verified": True,
        "profile_matched": bool(profile),
        "statistics_available": False,
        "appearances": 0,
        "goals": 0,
        "assists": 0,
        "yellow_cards": 0,
        "red_cards": 0,
        "league_rank": None,
        "team_rank": None,
    }


def main() -> None:
    args = parse_args()
    if not API_KEY:
        raise RuntimeError("FOOTBALL_DATA_API_KEYが未設定です")

    teams = read_json(TEAMS_PATH, {})
    old_players = read_json(PLAYERS_PATH, {})
    if len(teams) != 96:
        raise RuntimeError(f"teams.jsonは96クラブである必要があります: {len(teams)}")

    selected = sorted(teams.values(), key=lambda item: (item["league_id"], item["name"]))
    if args.limit is not None:
        selected = selected[: max(0, args.limit)]

    CACHE.mkdir(parents=True, exist_ok=True)
    last_request = 0.0
    failures = []

    with httpx.Client(base_url=BASE_URL, headers={"X-Auth-Token": API_KEY}, timeout=30) as client:
        for index, team in enumerate(selected, 1):
            path = CACHE / f"{team['id']}.json"
            if path.exists() and not args.refresh:
                print(f"[{index}/{len(selected)}] CACHE {team['name']}")
                continue
            elapsed = time.monotonic() - last_request
            if elapsed < args.delay:
                time.sleep(args.delay - elapsed)
            print(f"[{index}/{len(selected)}] FETCH {team['name']}")
            try:
                response = client.get(f"/teams/{team['api_id']}")
                last_request = time.monotonic()
                response.raise_for_status()
                atomic_write(path, response.json())
            except (httpx.RequestError, httpx.HTTPStatusError) as error:
                failures.append({"team_id": team["id"], "name": team["name"], "error": str(error)})
                print(f"  ERROR: {error}")

    cached = {team_id: read_json(CACHE / f"{team_id}.json", {}) for team_id in teams if (CACHE / f"{team_id}.json").exists()}
    missing_cache = sorted(set(teams) - set(cached))
    if (failures or missing_cache) and not args.publish_partial:
        atomic_write(STATUS_PATH, {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "published": False,
            "failures": failures,
            "missing_cache_team_ids": missing_cache,
        })
        raise RuntimeError("未取得クラブがあるためplayers.jsonは更新していません。再実行してください。")

    profiles_by_team: dict[str, list[dict]] = {}
    for player in old_players.values():
        profiles_by_team.setdefault(player.get("team_id", ""), []).append(player)

    new_players = {}
    verified_teams = 0
    provisional_teams = 0
    matched_profiles = 0
    empty_squad_teams = []

    for team_id, team in teams.items():
        payload = cached.get(team_id, {})
        squad = payload.get("squad") or []
        profiles = profiles_by_team.get(team_id, [])
        if squad:
            verified_teams += 1
            for fd_player in squad:
                if not fd_player.get("id") or not fd_player.get("name"):
                    continue
                profile = best_profile(fd_player, profiles)
                if profile:
                    matched_profiles += 1
                record = merged_player(fd_player, team, profile)
                new_players[record["id"]] = record
        else:
            provisional_teams += 1
            empty_squad_teams.append(team["name"])
            for old in profiles:
                record = dict(old)
                record["roster_verified"] = False
                record["roster_verification_reason"] = "football-data.org squad was empty"
                new_players[record["id"]] = record

    valid_team_ids = set(teams)
    if any(item.get("team_id") not in valid_team_ids for item in new_players.values()):
        raise RuntimeError("players.jsonに不正なteam_idがあります")
    if not new_players:
        raise RuntimeError("選手データが0件です")

    BACKUP.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP / "players.json"
    if PLAYERS_PATH.exists() and not backup_path.exists():
        shutil.copy2(PLAYERS_PATH, backup_path)

    atomic_write(PLAYERS_PATH, new_players)
    status = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "published": True,
        "total_teams": 96,
        "verified_teams": verified_teams,
        "provisional_teams": provisional_teams,
        "players_total": len(new_players),
        "profiles_matched": matched_profiles,
        "empty_squad_team_names": empty_squad_teams,
        "failures": failures,
    }
    atomic_write(STATUS_PATH, status)

    print("\n現所属選手の照合完了")
    print(f"現所属確認済み: {verified_teams}/96クラブ")
    print(f"暫定利用: {provisional_teams}/96クラブ")
    print(f"選手総数: {len(new_players)}件")
    print(f"TheSportsDBプロフィール結合: {matched_profiles}件")
    for name in empty_squad_teams:
        print(f"  PROVISIONAL: {name}")


if __name__ == "__main__":
    main()
