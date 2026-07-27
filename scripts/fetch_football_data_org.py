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


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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


def fetch_standings(client: httpx.Client, code: str) -> dict[str, list[dict]]:
    response = client.get(f"/competitions/{code}/standings")
    response.raise_for_status()
    standings = response.json().get("standings", [])
    by_type = {
        str(item.get("type", "")).upper(): standing_rows(item.get("table", []))
        for item in standings
    }
    return {
        "total": by_type.get("TOTAL", []),
        "home": by_type.get("HOME", []),
        "away": by_type.get("AWAY", []),
    }

def fetch_fixtures(
    client: httpx.Client,
    code: str,
    league_id: str,
) -> list[dict]:
    response = client.get(
        f"/competitions/{code}/matches",
        params={"status": "SCHEDULED"},
    )
    response.raise_for_status()
    payload = response.json()
    competition = payload.get("competition", {})

    fixtures = []
    for match in payload.get("matches", []):
        home = match.get("homeTeam", {})
        away = match.get("awayTeam", {})
        season = match.get("season", {})

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


def main() -> None:
    if not API_KEY:
        print(
            "FOOTBALL_DATA_API_KEYが未設定です。.envを確認してください。",
            file=sys.stderr,
        )
        raise SystemExit(1)

    all_fixtures = []
    failures = []

    with httpx.Client(
        base_url=BASE_URL,
        headers={"X-Auth-Token": API_KEY},
        timeout=30,
    ) as client:
        for index, (code, league_id) in enumerate(COMPETITIONS.items()):
            try:
                fixtures = fetch_fixtures(client, code, league_id)
                all_fixtures.extend(fixtures)
                print(f"{league_id}: 日程 {len(fixtures)}試合")

                time.sleep(6)

                standings_payload = fetch_standings(client, code)
                total_standings, provisional = normalize_preseason_standings(
                    standings_payload["total"],
                    fixtures,
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
                    (item.get("season_start") for item in fixtures if item.get("season_start")),
                    None,
                )
                season_end = next(
                    (item.get("season_end") for item in fixtures if item.get("season_end")),
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
                failures.append(f"{league_id}: HTTP {status_code}")
                print(
                    f"{league_id}: 取得失敗 HTTP {status_code}",
                    file=sys.stderr,
                )
            except httpx.RequestError as error:
                failures.append(f"{league_id}: {error}")
                print(f"{league_id}: 通信失敗 {error}", file=sys.stderr)

            if index < len(COMPETITIONS) - 1:
                time.sleep(6)

    all_fixtures.sort(key=lambda item: item.get("kickoff") or "")
    write_json(FIXTURES_PATH, all_fixtures)

    with_matchday = sum(
        1 for fixture in all_fixtures if fixture.get("matchday") is not None
    )
    print(f"日程合計: {len(all_fixtures)}試合")
    print(f"matchday保存済み: {with_matchday}試合")
    print(f"保存先: {FIXTURES_PATH}")

    if failures:
        print("一部取得失敗:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
