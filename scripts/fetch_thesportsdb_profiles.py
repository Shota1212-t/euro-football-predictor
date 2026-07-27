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
CACHE_DIR = DATA_DIR / "cache" / "thesportsdb"
BACKUP_DIR = DATA_DIR / "thesportsdb_backup"

TEAMS_PATH = PROCESSED_DIR / "teams.json"
PLAYERS_PATH = PROCESSED_DIR / "players.json"
MANAGERS_PATH = PROCESSED_DIR / "managers.json"
STAFF_PATH = PROCESSED_DIR / "staff.json"
STATUS_PATH = PROCESSED_DIR / "thesportsdb_status.json"

load_dotenv(ROOT / ".env")

API_KEY = os.getenv("THESPORTSDB_API_KEY", "123")
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"

LEAGUE_NAMES = {
    "pl": "English Premier League",
    "laliga": "Spanish La Liga",
    "seriea": "Italian Serie A",
    "bundesliga": "German Bundesliga",
    "ligue1": "French Ligue 1",
}

COUNTRY_NAMES = {
    "pl": "England",
    "laliga": "Spain",
    "seriea": "Italy",
    "bundesliga": "Germany",
    "ligue1": "France",
}

STAFF_WORDS = {
    "manager",
    "head coach",
    "coach",
    "assistant coach",
    "goalkeeping coach",
    "fitness coach",
    "technical director",
    "sporting director",
    "director of football",
    "caretaker manager",
}

PRIMARY_MANAGER_WORDS = {
    "manager",
    "head coach",
    "caretaker manager",
}

TEAM_SEARCH_ALIASES = {
    "fd-3": ["Bayer Leverkusen", "Leverkusen"],
    "fd-5": ["Bayern Munich", "Bayern Munchen"],
    "fd-7": ["Hamburg", "Hamburger SV"],
    "fd-77": ["Athletic Bilbao", "Athletic Club Bilbao"],
    "fd-560": ["Deportivo La Coruna", "Deportivo de La Coruna"],
    "fd-80": ["Espanyol", "RCD Espanyol"],
    "fd-90": ["Real Betis", "Betis"],
    "fd-532": ["Angers", "Angers SCO"],
    "fd-546": ["Lens", "RC Lens"],
    "fd-529": ["Rennes", "Stade Rennais"],
    "fd-351": ["Nottingham Forest", "Nottm Forest"],
    "fd-99": ["Fiorentina", "ACF Fiorentina"],
    "fd-108": ["Inter Milan", "Internazionale", "Inter"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "TheSportsDBから5大リーグ全96クラブのチーム・選手・スタッフ情報を"
            "待機、キャッシュ、途中再開付きで取得します。"
        )
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=4.0,
        help="APIリクエスト間の待機秒数。既定値は4秒。",
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
        help="既存キャッシュを無視して全クラブを再取得します。",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="試験用。先頭から指定クラブ数だけ処理します。",
    )
    parser.add_argument(
        "--league",
        choices=sorted(LEAGUE_NAMES),
        default=None,
        help="試験用。指定リーグだけ処理します。",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="通信エラーが残っていても取得済み分を公開JSONへ反映します。",
    )
    parser.add_argument(
        "--retry-not-found",
        action="store_true",
        help="not_foundのキャッシュだけを再取得します。成功済みキャッシュは維持します。",
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


def normalize(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def simplified_name(value: str | None) -> str:
    removable = {
        "fc", "afc", "cf", "ac", "as", "ss", "ssc", "us", "rc", "rcd",
        "club", "calcio", "football", "futbol", "de", "the", "sv", "vfb",
    }
    return " ".join(
        token
        for token in normalize(value).split()
        if token not in removable
        and not re.fullmatch(r"(?:18|19|20)\d{2}", token)
    )


def query_candidates(internal_id: str, team: dict) -> list[str]:
    candidates = [
        team.get("name", ""),
        simplified_name(team.get("name")),
        *TEAM_SEARCH_ALIASES.get(internal_id, []),
    ]
    result = []
    for candidate in candidates:
        candidate = candidate.strip()
        if candidate and normalize(candidate) not in {normalize(x) for x in result}:
            result.append(candidate)
    return result


def candidate_score(candidate: dict, expected: dict) -> int:
    score = 0
    expected_name = normalize(expected.get("name"))
    expected_simple = simplified_name(expected.get("name"))
    actual_name = normalize(candidate.get("strTeam"))
    actual_alt = normalize(candidate.get("strTeamAlternate"))
    actual_simple = simplified_name(candidate.get("strTeam"))

    if actual_name == expected_name:
        score += 100
    if expected_name and expected_name == actual_alt:
        score += 90
    if expected_simple and actual_simple == expected_simple:
        score += 75
    if expected_simple and (
        expected_simple in actual_simple or actual_simple in expected_simple
    ):
        score += 35

    expected_league = normalize(LEAGUE_NAMES.get(expected.get("league_id"), ""))
    actual_league = normalize(candidate.get("strLeague"))
    if expected_league and actual_league == expected_league:
        score += 30

    expected_country = normalize(COUNTRY_NAMES.get(expected.get("league_id"), ""))
    actual_country = normalize(candidate.get("strCountry"))
    if expected_country and actual_country == expected_country:
        score += 20

    if normalize(candidate.get("strSport")) == "soccer":
        score += 10
    return score


def choose_team(candidates: list[dict], expected: dict) -> dict | None:
    soccer = [
        item
        for item in candidates
        if normalize(item.get("strSport")) in {"", "soccer"}
    ]
    ranked = sorted(
        ((candidate_score(item, expected), item) for item in soccer),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if not ranked or ranked[0][0] < 75:
        return None
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        return None
    return ranked[0][1]


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
    match = re.search(r"\d+", value)
    return int(match.group()) if match else None


def is_staff(position: str | None) -> bool:
    normalized = normalize(position)
    return normalized in STAFF_WORDS or any(
        word in normalized
        for word in ("coach", "manager", "director")
    )


def is_primary_manager(position: str | None) -> bool:
    return normalize(position) in PRIMARY_MANAGER_WORDS


class RateLimitedClient:
    def __init__(self, delay: float, retries: int):
        self.delay = max(0.0, delay)
        self.retries = max(1, retries)
        self.last_request_at = 0.0
        self.client = httpx.Client(
            base_url=BASE_URL,
            timeout=30,
            headers={"User-Agent": "euro-football-predictor/1.0"},
        )

    def close(self) -> None:
        self.client.close()

    def request(self, endpoint: str, params: dict) -> dict:
        for attempt in range(1, self.retries + 1):
            elapsed = time.monotonic() - self.last_request_at
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)

            try:
                response = self.client.get(endpoint, params=params)
                self.last_request_at = time.monotonic()

                if response.status_code == 429:
                    wait = max(60.0, self.delay * (2 ** attempt))
                    print(f"HTTP 429: {wait:.0f}秒待機して再試行します")
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                return response.json()

            except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as error:
                if attempt >= self.retries:
                    raise RuntimeError(str(error)) from error
                wait = max(5.0, self.delay * (2 ** attempt))
                print(
                    f"通信失敗 ({attempt}/{self.retries}): {error} / "
                    f"{wait:.0f}秒後に再試行"
                )
                time.sleep(wait)

        raise RuntimeError("APIリクエストに失敗しました")


def fetch_team_bundle(
    client: RateLimitedClient,
    internal_id: str,
    expected_team: dict,
) -> dict:
    all_candidates = []
    attempted_queries = []

    for query in query_candidates(internal_id, expected_team):
        attempted_queries.append(query)
        payload = client.request("/searchteams.php", {"t": query})
        for item in payload.get("teams") or []:
            if item.get("idTeam") not in {
                candidate.get("idTeam") for candidate in all_candidates
            }:
                all_candidates.append(item)

        selected = choose_team(all_candidates, expected_team)
        if selected is not None:
            break
    else:
        selected = None

    if selected is None:
        return {
            "status": "not_found",
            "internal_id": internal_id,
            "expected_team": expected_team,
            "attempted_queries": attempted_queries,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    sportsdb_id = selected.get("idTeam")
    roster_payload = client.request(
        "/lookup_all_players.php",
        {"id": sportsdb_id},
    )

    return {
        "status": "success",
        "internal_id": internal_id,
        "expected_team": expected_team,
        "attempted_queries": attempted_queries,
        "team": selected,
        "roster": roster_payload.get("player") or [],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def player_record(raw: dict, team: dict) -> dict:
    player_id = f"tsdb-{raw.get('idPlayer')}"
    photo_url = raw.get("strThumb") or raw.get("strCutout")
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
        "photo_url": photo_url,
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
    staff_id = f"tsdb-{raw.get('idPlayer')}"
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


def enrich_team(team: dict, raw: dict) -> dict:
    enriched = dict(team)
    enriched.update(
        {
            "thesportsdb_id": raw.get("idTeam"),
            "logo_url": raw.get("strBadge") or team.get("logo_url"),
            "stadium": raw.get("strStadium") or team.get("stadium"),
            "stadium_thumb_url": raw.get("strStadiumThumb"),
            "website": raw.get("strWebsite"),
            "founded": parse_number(raw.get("intFormedYear")),
            "club_colors": raw.get("strColour1") or raw.get("strTeamColour"),
            "description_ja": raw.get("strDescriptionJP"),
            "description_en": raw.get("strDescriptionEN"),
            "jersey_url": raw.get("strEquipment"),
            "banner_url": raw.get("strBanner"),
            "fanart_url": raw.get("strFanart1"),
            "data_source_profile": "TheSportsDB",
        }
    )
    return enriched


def build_outputs(teams: dict[str, dict], bundles: dict[str, dict]):
    enriched_teams = {key: dict(value) for key, value in teams.items()}
    players = {}
    staff = {}
    managers = {}

    for internal_id, bundle in bundles.items():
        if bundle.get("status") != "success":
            continue
        team = enriched_teams[internal_id]
        team.update(enrich_team(team, bundle["team"]))

        team_staff = []
        for raw in bundle.get("roster", []):
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
                item
                for item in team_staff
                if is_primary_manager(item.get("role"))
            ),
            None,
        )
        if primary:
            managers[primary["id"]] = manager_record(primary)
            team["manager_id"] = primary["id"]

    return enriched_teams, players, staff, managers


def validate_outputs(
    teams: dict,
    players: dict,
    staff: dict,
    managers: dict,
) -> None:
    if len(teams) != 96:
        raise ValueError(f"チーム数が96ではありません: {len(teams)}")
    valid_team_ids = set(teams)

    for collection_name, collection in (
        ("players", players),
        ("staff", staff),
        ("managers", managers),
    ):
        for item_id, item in collection.items():
            if item.get("team_id") not in valid_team_ids:
                raise ValueError(
                    f"{collection_name}.{item_id} のteam_idが不正です"
                )


def main() -> None:
    args = parse_args()
    teams = read_json(TEAMS_PATH, {})
    if len(teams) != 96:
        raise RuntimeError(
            f"teams.jsonは96クラブである必要があります: {len(teams)}"
        )

    selected = [
        (internal_id, team)
        for internal_id, team in teams.items()
        if args.league is None or team.get("league_id") == args.league
    ]
    selected.sort(key=lambda pair: (pair[1].get("league_id", ""), pair[1].get("name", "")))
    if args.limit is not None:
        selected = selected[: max(0, args.limit)]

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    bundles = {}
    communication_failures = []
    client = RateLimitedClient(args.delay, args.retries)

    try:
        for index, (internal_id, team) in enumerate(selected, start=1):
            cache_path = CACHE_DIR / f"{internal_id}.json"
            cached_bundle = read_json(cache_path, {}) if cache_path.exists() else {}
            retry_cached_not_found = (
                args.retry_not_found
                and cached_bundle.get("status") == "not_found"
            )
            if cache_path.exists() and not args.refresh and not retry_cached_not_found:
                bundle = cached_bundle
                print(
                    f"[{index}/{len(selected)}] CACHE {team['name']} / "
                    f"{bundle.get('status', 'unknown')}"
                )
            else:
                print(f"[{index}/{len(selected)}] FETCH {team['name']}")
                try:
                    bundle = fetch_team_bundle(client, internal_id, team)
                    atomic_write_json(cache_path, bundle)
                except Exception as error:
                    communication_failures.append(
                        {"team_id": internal_id, "name": team["name"], "error": str(error)}
                    )
                    print(f"  ERROR: {error}")
                    continue
                print(
                    f"  {bundle.get('status')} / "
                    f"players+staff={len(bundle.get('roster', []))}"
                )
            bundles[internal_id] = bundle
    finally:
        client.close()

    if communication_failures and not args.allow_partial:
        failure_path = CACHE_DIR / "communication_failures.json"
        atomic_write_json(failure_path, communication_failures)
        raise RuntimeError(
            f"通信失敗が{len(communication_failures)}件残っています。"
            "キャッシュは保存済みです。再実行してください。"
        )

    all_bundles = {
        internal_id: read_json(CACHE_DIR / f"{internal_id}.json", {})
        for internal_id in teams
        if (CACHE_DIR / f"{internal_id}.json").exists()
    }
    enriched_teams, players, staff, managers = build_outputs(teams, all_bundles)
    validate_outputs(enriched_teams, players, staff, managers)

    success_count = sum(
        1 for bundle in all_bundles.values() if bundle.get("status") == "success"
    )
    not_found_count = sum(
        1 for bundle in all_bundles.values() if bundle.get("status") == "not_found"
    )
    missing_cache_count = 96 - len(all_bundles)

    status = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_teams": 96,
        "cached_teams": len(all_bundles),
        "success_teams": success_count,
        "not_found_teams": not_found_count,
        "missing_cache_teams": missing_cache_count,
        "players": len(players),
        "staff": len(staff),
        "managers": len(managers),
        "communication_failures": communication_failures,
        "complete": missing_cache_count == 0 and not communication_failures,
    }

    if missing_cache_count and not args.allow_partial:
        atomic_write_json(STATUS_PATH, status)
        raise RuntimeError(
            f"未取得キャッシュが{missing_cache_count}クラブあります。"
            "全96クラブ取得後に公開JSONを更新します。"
        )

    backup_once([TEAMS_PATH, PLAYERS_PATH, MANAGERS_PATH, STAFF_PATH])
    atomic_write_json(TEAMS_PATH, enriched_teams)
    atomic_write_json(PLAYERS_PATH, players)
    atomic_write_json(STAFF_PATH, staff)
    atomic_write_json(MANAGERS_PATH, managers)
    atomic_write_json(STATUS_PATH, status)

    print("\nTheSportsDB取得・反映完了")
    print(f"チーム成功: {success_count}/96")
    print(f"チーム未発見: {not_found_count}/96")
    print(f"選手: {len(players)}件")
    print(f"スタッフ: {len(staff)}件")
    print(f"主監督: {len(managers)}件")
    print(f"キャッシュ: {CACHE_DIR}")
    print(f"状態: {STATUS_PATH}")


if __name__ == "__main__":
    main()
