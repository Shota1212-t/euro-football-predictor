from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
FIXTURES_PATH = PROCESSED_DIR / "fixtures.json"
RESULTS_PATH = PROCESSED_DIR / "current_season_results.json"
TEMP_RESULTS_PATH = RESULTS_PATH.with_suffix(".json.tmp")

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

# Minimum interval between API requests (in seconds)
MIN_REQUEST_INTERVAL = 6.5
last_request_time = 0.0
MAX_RETRIES = 3


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def rate_limit_wait() -> None:
    """Enforce minimum interval between API requests."""
    global last_request_time
    elapsed = time.time() - last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        sleep_time = MIN_REQUEST_INTERVAL - elapsed
        time.sleep(sleep_time)
    last_request_time = time.time()


def standing_rows(table: list[dict]) -> list[dict]:
    rows = []
    for row in table:
        team = row.get("team", {})
        rows.append(
            {
                "team_id": (
                    f"fd-{int(team['id'])}"
                    if team.get("id") is not None
                    else None
                ),
                "api_id": team.get("id"),
                "team_name": team.get("name", ""),
                "position": row.get("position"),
                "played": row.get("playedGames", 0),
                "win": row.get("won", 0),
                "draw": row.get("draw", 0),
                "loss": row.get("lost", 0),
                "goals_for": row.get("goalsFor", 0),
                "goals_against": row.get("goalsAgainst", 0),
                "points": row.get("points", 0),
                "recent_form": (row.get("form") or "").replace(",", ""),
            }
        )
    return rows


def request_json(client: httpx.Client, url: str, *, params: dict | None = None) -> dict:
    """Rate-limited request with finite retry and Retry-After support."""
    global last_request_time
    last_error = None
    for attempt in range(MAX_RETRIES):
        rate_limit_wait()
        response = client.get(url, params=params)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            try:
                delay = max(float(retry_after), MIN_REQUEST_INTERVAL) if retry_after else MIN_REQUEST_INTERVAL
            except ValueError:
                delay = MIN_REQUEST_INTERVAL
            time.sleep(delay)
            last_error = httpx.HTTPStatusError("rate limited", request=response.request, response=response)
            continue
        if response.status_code >= 500:
            last_error = httpx.HTTPStatusError("server error", request=response.request, response=response)
            if attempt + 1 < MAX_RETRIES:
                time.sleep(MIN_REQUEST_INTERVAL)
                continue
        response.raise_for_status()
        return response.json()
    raise last_error or RuntimeError("request retries exhausted")


def fetch_standings(client: httpx.Client, code: str) -> dict[str, list[dict]]:
    payload = request_json(client, f"/competitions/{code}/standings")
    standings = payload.get("standings", [])
    by_type = {str(item.get("type", "")).upper(): standing_rows(item.get("table", [])) for item in standings}
    return {"total": by_type.get("TOTAL", []), "home": by_type.get("HOME", []), "away": by_type.get("AWAY", [])}

def fetch_fixtures(
    client: httpx.Client,
    code: str,
    league_id: str,
    status: str,
) -> list[dict]:
    """Fetch fixtures with given status (SCHEDULED or FINISHED)."""
    payload = request_json(client, f"/competitions/{code}/matches", params={"status": status})
    competition = payload.get("competition", {})

    fixtures = []
    for match in payload.get("matches", []):
        home = match.get("homeTeam", {})
        away = match.get("awayTeam", {})
        season = match.get("season", {})
        score = match.get("score", {})
        full_time = score.get("fullTime", {})

        # For FINISHED matches, only include if score is confirmed
        if status == "FINISHED":
            home_score = full_time.get("home")
            away_score = full_time.get("away")
            if home_score is None or away_score is None:
                continue

            # Determine actual result
            if home_score > away_score:
                actual_result = "Home Win"
            elif home_score < away_score:
                actual_result = "Away Win"
            else:
                actual_result = "Draw"
        else:
            home_score = None
            away_score = None
            actual_result = None

        fixtures.append(
            {
                "id": str(match.get("id")),
                "league_id": league_id,
                "competition_code": competition.get("code") or code,
                "competition_name": competition.get("name", ""),
                "season_id": season.get("id"),
                "season_start": season.get("startDate"),
                "season_end": season.get("endDate"),
                "matchday": match.get("matchday"),
                "stage": match.get("stage"),
                "status": match.get("status"),
                "kickoff": match.get("utcDate"),
                "home_team": {
                    "id": (
                        f"fd-{int(home['id'])}"
                        if home.get("id") is not None
                        else None
                    ),
                    "api_id": home.get("id"),
                    "name": home.get("name", ""),
                    "short": home.get("tla") or home.get("shortName", ""),
                },
                "away_team": {
                    "id": (
                        f"fd-{int(away['id'])}"
                        if away.get("id") is not None
                        else None
                    ),
                    "api_id": away.get("id"),
                    "name": away.get("name", ""),
                    "short": away.get("tla") or away.get("shortName", ""),
                },
                "home_score": home_score,
                "away_score": away_score,
                "actual_result": actual_result,
            }
        )
    return fixtures


def current_teams_from_fixtures(fixtures: list[dict]) -> list[dict]:
    teams = {}
    for fixture in fixtures:
        for side in ("home_team", "away_team"):
            team = fixture.get(side, {})
            api_id = team.get("api_id")
            if api_id is None:
                continue
            team_id = f"fd-{int(api_id)}"
            teams[team_id] = {
                "team_id": team_id,
                "api_id": api_id,
                "team_name": team.get("name", ""),
                "played": 0,
                "win": 0,
                "draw": 0,
                "loss": 0,
                "goals_for": 0,
                "goals_against": 0,
                "points": 0,
                "recent_form": "",
            }
    return sorted(teams.values(), key=lambda row: row["team_name"])


def normalize_preseason_standings(
    standings: list[dict],
    fixtures: list[dict],
) -> tuple[list[dict], bool]:
    season_start = next(
        (fixture.get("season_start") for fixture in fixtures if fixture.get("season_start")),
        None,
    )
    if not season_start:
        return standings, False

    today = time.strftime("%Y-%m-%d", time.gmtime())
    before_season = today < season_start
    if before_season:
        return current_teams_from_fixtures(fixtures), True
    return standings, False


def validate_results(results: list[dict]) -> None:
    """Validate results data structure."""
    if not isinstance(results, list):
        raise ValueError("Results must be a list")
    
    ids = set()
    for index, item in enumerate(results):
        # Check required fields
        required = {"id", "status", "kickoff", "home_score", "away_score", "actual_result"}
        missing = required - set(item)
        if missing:
            raise ValueError(f"Result {index} missing fields: {missing}")
        
        # Check no duplicates
        match_id = str(item["id"])
        if match_id in ids:
            raise ValueError(f"Duplicate match ID: {match_id}")
        ids.add(match_id)
        
        # Validate status and scores
        if item["status"] != "FINISHED":
            raise ValueError(f"Result {index} must have status FINISHED")
        
        if item["home_score"] is None or item["away_score"] is None:
            raise ValueError(f"Result {index} has missing scores")
        
        if item["actual_result"] not in {"Home Win", "Draw", "Away Win"}:
            raise ValueError(f"Result {index} has invalid actual_result")


def atomic_write_results(results: list[dict]) -> None:
    """Write results atomically, preserving existing data on failure."""
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEMP_RESULTS_PATH.unlink(missing_ok=True)
    
    try:
        # Write to temporary file
        with TEMP_RESULTS_PATH.open("w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        
        # Validate written data
        written = json.loads(TEMP_RESULTS_PATH.read_text(encoding="utf-8"))
        validate_results(written)
        
        # Atomic replace
        os.replace(TEMP_RESULTS_PATH, RESULTS_PATH)
    except Exception:
        TEMP_RESULTS_PATH.unlink(missing_ok=True)
        raise


def main() -> None:
    if not API_KEY:
        print(
            "FOOTBALL_DATA_API_KEYが未設定です。.envを確認してください。",
            file=sys.stderr,
        )
        raise SystemExit(1)

    all_fixtures = []
    all_results = []
    failures = []

    with httpx.Client(
        base_url=BASE_URL,
        headers={"X-Auth-Token": API_KEY},
        timeout=30,
    ) as client:
        for index, (code, league_id) in enumerate(COMPETITIONS.items()):
            try:
                # Fetch SCHEDULED fixtures
                scheduled = fetch_fixtures(client, code, league_id, "SCHEDULED")
                all_fixtures.extend(scheduled)
                print(f"{league_id}: SCHEDULED {len(scheduled)}試合")

                # Fetch FINISHED results
                finished = fetch_fixtures(client, code, league_id, "FINISHED")
                # Only add matches with confirmed scores
                finished_with_scores = [m for m in finished if m.get("home_score") is not None]
                all_results.extend(finished_with_scores)
                print(f"{league_id}: FINISHED {len(finished_with_scores)}試合")

                # Fetch standings
                standings_payload = fetch_standings(client, code)
                total_standings, provisional = normalize_preseason_standings(
                    standings_payload["total"],
                    scheduled,
                )
                if provisional:
                    home_standings = []
                    away_standings = []
                    last5_standings = []
                else:
                    home_standings = standings_payload["home"]
                    away_standings = standings_payload["away"]
                    last5_standings = sorted(
                        [row for row in total_standings if row.get("recent_form")],
                        key=lambda row: (
                            sum(
                                3 if result == "W" else 1 if result == "D" else 0
                                for result in row.get("recent_form", "")[-5:]
                            ),
                            row.get("goals_for", 0) - row.get("goals_against", 0),
                            row.get("goals_for", 0),
                        ),
                        reverse=True,
                    )
                    for position, row in enumerate(last5_standings, start=1):
                        row["position"] = position

                season_start = next(
                    (item.get("season_start") for item in scheduled if item.get("season_start")),
                    None,
                )
                season_end = next(
                    (item.get("season_end") for item in scheduled if item.get("season_end")),
                    None,
                )
                write_json(
                    PROCESSED_DIR / "standings" / f"{league_id}.json",
                    {
                        "season_start": season_start,
                        "season_end": season_end,
                        "provisional": provisional,
                        "note": (
                            "開幕前のため現シーズン所属クラブを0試合で表示"
                            if provisional
                            else None
                        ),
                        "total": total_standings,
                        "home": home_standings,
                        "away": away_standings,
                        "last5": last5_standings,
                    },
                )
                label = "開幕前暫定" if provisional else "API順位表"
                print(
                    f"{league_id}: 順位表 total={len(total_standings)} / "
                    f"home={len(home_standings)} / away={len(away_standings)} / "
                    f"last5={len(last5_standings)} ({label})"
                )

            except httpx.HTTPStatusError as error:
                status_code = error.response.status_code
                retry_after = error.response.headers.get("Retry-After")
                failures.append(f"{league_id}: HTTP {status_code}")
                print(
                    f"{league_id}: 取得失敗 HTTP {status_code}",
                    file=sys.stderr,
                )
                if retry_after and status_code == 429:
                    try:
                        wait_time = int(retry_after)
                        print(f"Rate limited. Waiting {wait_time} seconds.", file=sys.stderr)
                        time.sleep(wait_time)
                    except (ValueError, TypeError):
                        pass
            except httpx.RequestError as error:
                failures.append(f"{league_id}: {error}")
                print(f"{league_id}: 通信失敗 {error}", file=sys.stderr)

    # Sort fixtures and results
    all_fixtures.sort(key=lambda item: item.get("kickoff") or "")
    all_results.sort(key=lambda item: item.get("kickoff") or "", reverse=True)

    # Write fixtures (SCHEDULED only)
    write_json(FIXTURES_PATH, all_fixtures)

    # Write results atomically
    try:
        validate_results(all_results)
        atomic_write_results(all_results)
    except Exception as error:
        print(f"Results validation failed: {error}", file=sys.stderr)
        if RESULTS_PATH.exists():
            print("Keeping existing results.json", file=sys.stderr)
        else:
            # No existing file, write empty array
            atomic_write_results([])

    with_matchday = sum(
        1 for fixture in all_fixtures if fixture.get("matchday") is not None
    )
    print(f"日程合計: {len(all_fixtures)}試合")
    print(f"matchday保存済み: {with_matchday}試合")
    print(f"保存先 (日程): {FIXTURES_PATH}")
    print(f"終了済み試合: {len(all_results)}試合")
    print(f"保存先 (結果): {RESULTS_PATH}")

    if failures:
        print("一部取得失敗:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
