from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache" / "football_data_org_managers"
BACKUP_DIR = DATA_DIR / "manager_backup"

TEAMS_PATH = PROCESSED_DIR / "teams.json"
MANAGERS_PATH = PROCESSED_DIR / "managers.json"
STAFF_PATH = PROCESSED_DIR / "staff.json"
STATUS_PATH = PROCESSED_DIR / "manager_reconciliation_status.json"

load_dotenv(ROOT / ".env")
API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")
BASE_URL = "https://api.football-data.org/v4"

PRIMARY_ROLES = {"manager", "head coach", "caretaker manager"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "football-data.orgを基準に5大リーグ96クラブの現監督を照合し、"
            "TheSportsDBのプロフィールを補完情報として結合します。"
        )
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=6.5,
        help="APIリクエスト間の待機秒数。既定値は6.5秒。",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="通信失敗時の最大再試行回数。既定値は3回。",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="既存キャッシュを無視して96クラブを再取得します。",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="試験用。先頭から指定クラブ数だけ取得します。公開JSONは更新しません。",
    )
    parser.add_argument(
        "--publish-partial",
        action="store_true",
        help="未取得キャッシュがあっても取得済み分で公開JSONを更新します。通常は使用しません。",
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


def normalize(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


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


def is_primary_role(value: str | None) -> bool:
    return normalize(value) in PRIMARY_ROLES


def backup_current_files() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = BACKUP_DIR / timestamp
    destination.mkdir(parents=True, exist_ok=True)
    for path in (TEAMS_PATH, MANAGERS_PATH, STAFF_PATH, STATUS_PATH):
        if path.exists():
            shutil.copy2(path, destination / path.name)
    return destination


class RateLimitedClient:
    def __init__(self, delay: float, retries: int):
        self.delay = max(0.0, delay)
        self.retries = max(1, retries)
        self.last_request_at = 0.0
        self.client = httpx.Client(
            base_url=BASE_URL,
            headers={
                "X-Auth-Token": API_KEY,
                "User-Agent": "euro-football-predictor/1.0",
            },
            timeout=30,
        )

    def close(self) -> None:
        self.client.close()

    def get_team(self, api_id: int) -> dict:
        for attempt in range(1, self.retries + 1):
            elapsed = time.monotonic() - self.last_request_at
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            try:
                response = self.client.get(f"/teams/{api_id}")
                self.last_request_at = time.monotonic()
                if response.status_code == 429:
                    wait = max(65.0, self.delay * (2 ** attempt))
                    print(f"HTTP 429: {wait:.0f}秒待機して再試行します")
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as error:
                if attempt >= self.retries:
                    raise RuntimeError(str(error)) from error
                wait = max(10.0, self.delay * (2 ** attempt))
                print(
                    f"通信失敗 ({attempt}/{self.retries}): {error} / "
                    f"{wait:.0f}秒後に再試行"
                )
                time.sleep(wait)
        raise RuntimeError("APIリクエストに失敗しました")


def extract_coach(payload: dict) -> dict | None:
    coach = payload.get("coach")
    if not isinstance(coach, dict):
        return None
    name = (coach.get("name") or "").strip()
    if not name:
        return None
    return coach


def profile_candidates(existing_managers: dict, staff: dict) -> list[dict]:
    candidates: dict[str, dict] = {}
    for item in staff.values():
        if is_primary_role(item.get("role")):
            candidates[item["id"]] = dict(item)
    for item in existing_managers.values():
        merged = dict(candidates.get(item["id"], {}))
        merged.update(item)
        candidates[item["id"]] = merged
    return list(candidates.values())


def find_profile(coach: dict, candidates: list[dict]) -> dict | None:
    target = normalize(coach.get("name"))
    if not target:
        return None
    exact = [item for item in candidates if normalize(item.get("name")) == target]
    if len(exact) == 1:
        return exact[0]
    return None


def verified_manager_record(
    coach: dict,
    team: dict,
    profile: dict | None,
    verified_at: str,
) -> dict:
    coach_id = coach.get("id")
    manager_id = f"fdcoach-{int(coach_id)}" if coach_id is not None else (
        "fdcoach-name-" + normalize(coach.get("name")).replace(" ", "-")
    )
    contract = coach.get("contract") if isinstance(coach.get("contract"), dict) else {}
    date_of_birth = coach.get("dateOfBirth") or (profile or {}).get("date_of_birth")
    return {
        "id": manager_id,
        "football_data_coach_id": coach_id,
        "thesportsdb_id": (profile or {}).get("thesportsdb_id"),
        "name": coach.get("name") or (profile or {}).get("name") or "Unknown",
        "team_id": team["id"],
        "league_id": team.get("league_id"),
        "nationality": coach.get("nationality") or (profile or {}).get("nationality"),
        "date_of_birth": date_of_birth,
        "age": calculate_age(date_of_birth),
        "appointed": contract.get("start"),
        "contract_until": contract.get("until"),
        "photo_url": (profile or {}).get("photo_url"),
        "description_ja": (profile or {}).get("description_ja"),
        "description_en": (profile or {}).get("description_en"),
        "matches": None,
        "wins": None,
        "draws": None,
        "losses": None,
        "avg_goals_for": None,
        "avg_goals_against": None,
        "recent_form": None,
        "role": "Manager",
        "data_source": (
            "football-data.org + TheSportsDB"
            if profile
            else "football-data.org"
        ),
        "statistics_available": False,
        "employment_verified": True,
        "employment_status": "verified",
        "verification_source": "football-data.org",
        "verified_at": verified_at,
    }


def provisional_manager_record(
    profile: dict,
    team: dict,
    verified_at: str,
) -> dict:
    return {
        "id": profile["id"],
        "football_data_coach_id": None,
        "thesportsdb_id": profile.get("thesportsdb_id"),
        "name": profile.get("name") or "Unknown",
        "team_id": team["id"],
        "league_id": team.get("league_id"),
        "nationality": profile.get("nationality"),
        "date_of_birth": profile.get("date_of_birth"),
        "age": profile.get("age"),
        "appointed": profile.get("appointed"),
        "contract_until": None,
        "photo_url": profile.get("photo_url"),
        "description_ja": profile.get("description_ja"),
        "description_en": profile.get("description_en"),
        "matches": None,
        "wins": None,
        "draws": None,
        "losses": None,
        "avg_goals_for": None,
        "avg_goals_against": None,
        "recent_form": None,
        "role": "Manager",
        "data_source": "TheSportsDB",
        "statistics_available": False,
        "employment_verified": False,
        "employment_status": "provisional",
        "verification_source": "TheSportsDB",
        "verified_at": None,
        "last_checked_at": verified_at,
        "verification_note": "football-data.orgのcoachが空のため、TheSportsDB登録情報を暫定利用",
    }


def validate_outputs(teams: dict, managers: dict) -> None:
    if len(teams) != 96:
        raise ValueError(f"チーム数が96ではありません: {len(teams)}")
    valid_team_ids = set(teams)
    seen_teams: set[str] = set()
    for manager_id, manager in managers.items():
        team_id = manager.get("team_id")
        if team_id not in valid_team_ids:
            raise ValueError(f"{manager_id}のteam_idが不正です: {team_id}")
        if team_id in seen_teams:
            raise ValueError(f"1クラブに複数監督が登録されています: {team_id}")
        seen_teams.add(team_id)
        if manager.get("employment_status") not in {"verified", "provisional"}:
            raise ValueError(f"{manager_id}のemployment_statusが不正です")
    for team_id, team in teams.items():
        manager_id = team.get("manager_id")
        if manager_id is not None and manager_id not in managers:
            raise ValueError(f"{team_id}に孤立manager_idがあります: {manager_id}")
        if manager_id and managers[manager_id].get("team_id") != team_id:
            raise ValueError(f"{team_id}と{manager_id}の所属関係が不一致です")


def main() -> None:
    args = parse_args()
    if not API_KEY:
        print("FOOTBALL_DATA_API_KEYが未設定です。.envを確認してください。", file=sys.stderr)
        raise SystemExit(1)

    teams = read_json(TEAMS_PATH, {})
    existing_managers = read_json(MANAGERS_PATH, {})
    staff = read_json(STAFF_PATH, {})
    if len(teams) != 96:
        raise RuntimeError(f"teams.jsonは96クラブである必要があります: {len(teams)}")

    ordered_teams = sorted(
        teams.items(),
        key=lambda pair: (pair[1].get("league_id", ""), pair[1].get("name", "")),
    )
    selected = ordered_teams[: max(0, args.limit)] if args.limit is not None else ordered_teams
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    failures = []

    client = RateLimitedClient(args.delay, args.retries)
    try:
        for index, (team_id, team) in enumerate(selected, start=1):
            api_id = team.get("api_id")
            if api_id is None:
                failures.append({"team_id": team_id, "name": team.get("name"), "error": "api_idなし"})
                continue
            cache_path = CACHE_DIR / f"{team_id}.json"
            if cache_path.exists() and not args.refresh:
                payload = read_json(cache_path, {})
                print(f"[{index}/{len(selected)}] CACHE {team['name']} / coach={'yes' if extract_coach(payload) else 'no'}")
                continue
            print(f"[{index}/{len(selected)}] FETCH {team['name']}")
            try:
                payload = client.get_team(int(api_id))
                atomic_write_json(cache_path, payload)
                print(f"  coach: {(extract_coach(payload) or {}).get('name') or 'なし'}")
            except Exception as error:
                failures.append({"team_id": team_id, "name": team.get("name"), "error": str(error)})
                print(f"  ERROR: {error}")
    finally:
        client.close()

    all_payloads = {
        team_id: read_json(CACHE_DIR / f"{team_id}.json", {})
        for team_id in teams
        if (CACHE_DIR / f"{team_id}.json").exists()
    }
    missing_cache = sorted(set(teams) - set(all_payloads))
    verified_at = datetime.now(timezone.utc).isoformat()

    if (failures or missing_cache) and not args.publish_partial:
        status = {
            "updated_at": verified_at,
            "total_teams": 96,
            "cached_teams": len(all_payloads),
            "missing_cache_teams": missing_cache,
            "communication_failures": failures,
            "published": False,
            "note": "全96クラブのキャッシュが揃っていないため公開JSONは更新していません。再実行してください。",
        }
        atomic_write_json(STATUS_PATH, status)
        print("\n公開JSONは更新していません。")
        print(f"キャッシュ済み: {len(all_payloads)}/96")
        print(f"未取得: {len(missing_cache)}")
        print(f"通信失敗: {len(failures)}")
        raise SystemExit(1)

    candidates = profile_candidates(existing_managers, staff)
    team_profiles = {
        item.get("team_id"): item
        for item in candidates
        if item.get("team_id") in teams and is_primary_role(item.get("role"))
    }

    updated_teams = {team_id: dict(team) for team_id, team in teams.items()}
    reconciled_managers: dict[str, dict] = {}
    verified_count = 0
    provisional_count = 0
    missing_count = 0

    for team_id, team in updated_teams.items():
        payload = all_payloads.get(team_id, {})
        coach = extract_coach(payload)
        if coach:
            profile = find_profile(coach, candidates)
            manager = verified_manager_record(coach, team, profile, verified_at)
            reconciled_managers[manager["id"]] = manager
            team["manager_id"] = manager["id"]
            verified_count += 1
            continue

        profile = team_profiles.get(team_id)
        if profile:
            manager = provisional_manager_record(profile, team, verified_at)
            reconciled_managers[manager["id"]] = manager
            team["manager_id"] = manager["id"]
            provisional_count += 1
        else:
            team["manager_id"] = None
            missing_count += 1

    validate_outputs(updated_teams, reconciled_managers)
    backup_path = backup_current_files()
    atomic_write_json(TEAMS_PATH, updated_teams)
    atomic_write_json(MANAGERS_PATH, reconciled_managers)

    status = {
        "updated_at": verified_at,
        "total_teams": 96,
        "cached_teams": len(all_payloads),
        "verified_managers": verified_count,
        "provisional_managers": provisional_count,
        "missing_managers": missing_count,
        "published_managers": len(reconciled_managers),
        "orphan_manager_ids": 0,
        "duplicate_team_assignments": 0,
        "communication_failures": failures,
        "published": True,
        "backup_path": str(backup_path),
        "verification_policy": {
            "verified": "football-data.org team coach",
            "provisional": "TheSportsDB primary manager when football-data.org coach is empty",
            "missing": "neither source supplied a current-manager candidate",
        },
    }
    atomic_write_json(STATUS_PATH, status)

    print("\n監督の現所属照合完了")
    print(f"現所属確認済み: {verified_count}/96クラブ")
    print(f"暫定所属: {provisional_count}/96クラブ")
    print(f"監督未取得: {missing_count}/96クラブ")
    print(f"公開監督数: {len(reconciled_managers)}人")
    print("孤立manager_id: 0件")
    print(f"バックアップ: {backup_path}")
    print(f"状態: {STATUS_PATH}")


if __name__ == "__main__":
    main()
