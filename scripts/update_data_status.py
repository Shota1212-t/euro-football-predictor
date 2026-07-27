from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STATUS_PATH = DATA_DIR / "data_status.json"
FIXTURES_PATH = DATA_DIR / "processed" / "fixtures.json"
PREDICTIONS_PATH = DATA_DIR / "predictions" / "matches.json"
MATCHES_PATH = DATA_DIR / "processed" / "matches.csv"
SECOND_DIVISION_DIR = DATA_DIR / "raw" / "football_data_co_uk_second_division"
STANDINGS_DIR = DATA_DIR / "processed" / "standings"
TEAMS_PATH = DATA_DIR / "processed" / "teams.json"
PLAYERS_PATH = DATA_DIR / "processed" / "players.json"
MANAGERS_PATH = DATA_DIR / "processed" / "managers.json"
STAFF_PATH = DATA_DIR / "processed" / "staff.json"
SQUAD_STATUS_PATH = DATA_DIR / "processed" / "squad_reconciliation_status.json"
THESPORTSDB_STATUS_PATH = DATA_DIR / "processed" / "thesportsdb_status.json"
RANKINGS_DIR = DATA_DIR / "processed" / "rankings"
RANKINGS_STATUS_PATH = DATA_DIR / "processed" / "rankings_status.json"
EXTRA_FIXTURES_PATH = DATA_DIR / "processed" / "extra_fixtures.json"
EXTRA_FIXTURES_STATUS_PATH = DATA_DIR / "processed" / "extra_fixtures_status.json"


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def file_updated_at(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(
        path.stat().st_mtime,
        tz=timezone.utc,
    ).isoformat(timespec="seconds")


def status_item(
    source: str,
    data_type: str,
    path: Path | None,
    records: str,
    notes: str,
) -> dict:
    exists = path is not None and path.exists()
    return {
        "source": source,
        "data_type": data_type,
        "last_updated": file_updated_at(path) if exists else None,
        "records": records,
        "status": "Success" if exists else "Not configured",
        "error": None if exists else notes,
        "next_update": "手動実行",
        "is_stale": not exists,
    }


def build_status() -> list[dict]:
    fixtures = read_json(FIXTURES_PATH, [])
    predictions = read_json(PREDICTIONS_PATH, [])
    teams = read_json(TEAMS_PATH, {})
    players = read_json(PLAYERS_PATH, {})
    managers = read_json(MANAGERS_PATH, {})
    staff = read_json(STAFF_PATH, {})
    squad_status = read_json(SQUAD_STATUS_PATH, {})
    thesportsdb_status = read_json(THESPORTSDB_STATUS_PATH, {})
    rankings_status = read_json(RANKINGS_STATUS_PATH, {})
    extra_fixtures = read_json(EXTRA_FIXTURES_PATH, [])
    extra_fixtures_status = read_json(EXTRA_FIXTURES_STATUS_PATH, {})
    ranking_files = (
        sorted(RANKINGS_DIR.glob("*.json"))
        if RANKINGS_DIR.exists()
        else []
    )
    standings_files = (
        sorted(STANDINGS_DIR.glob("*.json"))
        if STANDINGS_DIR.exists()
        else []
    )
    second_division_files = (
        sorted(SECOND_DIVISION_DIR.glob("*.csv"))
        if SECOND_DIVISION_DIR.exists()
        else []
    )

    first_division_history = sum(
        1
        for item in predictions
        if item.get("data_quality") == "full_history"
    )
    second_division_history = sum(
        1
        for item in predictions
        if item.get("data_quality") == "second_division_history"
    )
    estimated = sum(
        1
        for item in predictions
        if item.get("data_quality") == "estimated"
    )
    unknown_quality = len(predictions) - (
        first_division_history + second_division_history + estimated
    )

    team_profiles = sum(
        1 for item in teams.values()
        if item.get("thesportsdb_id") or item.get("data_source_profile") == "TheSportsDB"
    )
    verified_players = sum(
        1 for item in players.values() if item.get("roster_verified") is True
    )
    provisional_players = len(players) - verified_players
    verified_squads = int(squad_status.get("verified_teams", 0))
    provisional_squads = int(squad_status.get("provisional_teams", 0))

    profile_paths = [
        path for path in (
            TEAMS_PATH, PLAYERS_PATH, MANAGERS_PATH, STAFF_PATH,
            SQUAD_STATUS_PATH, THESPORTSDB_STATUS_PATH,
        ) if path.exists()
    ]
    profile_reference = max(
        profile_paths,
        key=lambda path: path.stat().st_mtime,
        default=None,
    )

    ranking_reference = max(
        ranking_files,
        key=lambda path: path.stat().st_mtime,
        default=None,
    )
    ranking_states = {}
    ranking_totals = {"goals": 0, "assists": 0, "appearances": 0}
    for path in ranking_files:
        payload = read_json(path, {})
        metadata = payload.get("metadata", {})
        ranking_states[path.stem] = metadata.get("state", "unknown")
        for kind in ranking_totals:
            ranking_totals[kind] += len(payload.get(kind, []))

    preseason_leagues = sum(
        1 for state in ranking_states.values() if state == "preseason"
    )
    available_leagues = sum(
        1 for state in ranking_states.values() if state == "available"
    )
    ranking_records = (
        f"{len(ranking_files)} leagues "
        f"({available_leagues} available / {preseason_leagues} preseason) / "
        f"goals {ranking_totals['goals']} / "
        f"assists {ranking_totals['assists']} / "
        f"appearances {ranking_totals['appearances']}"
    )

    official_extra = sum(
        1 for item in extra_fixtures
        if item.get("data_quality") == "official"
    )
    supplemental_extra = sum(
        1 for item in extra_fixtures
        if item.get("data_quality") == "supplemental_last_event_only"
    )
    manual_extra = sum(
        1 for item in extra_fixtures
        if item.get("data_quality") == "manual"
    )
    extra_unknown = len(extra_fixtures) - (
        official_extra + supplemental_extra + manual_extra
    )
    extra_records = (
        f"{len(extra_fixtures)} extra competition fixtures "
        f"({official_extra} official CL / "
        f"{supplemental_extra} supplemental / {manual_extra} manual)"
    )
    if extra_unknown:
        extra_records += f" / {extra_unknown} unknown"

    standings_reference = max(
        standings_files,
        key=lambda path: path.stat().st_mtime,
        default=None,
    )
    second_division_reference = max(
        second_division_files,
        key=lambda path: path.stat().st_mtime,
        default=None,
    )

    prediction_records = (
        f"{len(predictions)} predictions "
        f"({first_division_history} first-division / "
        f"{second_division_history} second-division / "
        f"{estimated} estimated)"
    )
    if unknown_quality:
        prediction_records += f" / {unknown_quality} unknown"

    return [
        status_item(
            "football-data.org",
            "Fixtures",
            FIXTURES_PATH,
            f"{len(fixtures)} fixtures",
            "日程取得スクリプトがまだ正常実行されていません。",
        ),
        status_item(
            "football-data.org",
            "Standings",
            standings_reference,
            f"{len(standings_files)} leagues",
            "順位表データがありません。",
        ),
        status_item(
            "football-data.org",
            "Player rankings",
            ranking_reference if rankings_status.get("success") else None,
            ranking_records,
            "選手ランキング取得処理が正常に完了していません。",
        ),
        status_item(
            "football-data.org + TheSportsDB",
            "European / cup fixtures for fatigue",
            (
                EXTRA_FIXTURES_PATH
                if extra_fixtures_status.get("success") and extra_fixtures
                else None
            ),
            extra_records,
            "追加大会・カップ戦補完データが正常に取得されていません。",
        ),
        status_item(
            "LightGBM",
            "Match predictions",
            PREDICTIONS_PATH,
            prediction_records,
            "予測生成スクリプトがまだ正常実行されていません。",
        ),
        {
            "source": "Football-Data.co.uk",
            "data_type": "First-division historical results / training data",
            "last_updated": file_updated_at(MATCHES_PATH),
            "records": "local CSV",
            "status": "Success" if MATCHES_PATH.exists() else "Not configured",
            "error": None if MATCHES_PATH.exists() else "学習用CSVがありません。",
            "next_update": "手動更新",
            "is_stale": not MATCHES_PATH.exists(),
        },
        status_item(
            "Football-Data.co.uk",
            "Second-division promotion history",
            second_division_reference,
            f"{len(second_division_files)} CSV files",
            "昇格クラブ補完用の2部CSVがありません。",
        ),
        {
            "source": "API-FOOTBALL",
            "data_type": "Cup / European fixtures",
            "last_updated": None,
            "records": "0",
            "status": "Not implemented",
            "error": "取得処理は未実装です。",
            "next_update": None,
            "is_stale": True,
        },
        status_item(
            "TheSportsDB",
            "Team profiles / images",
            profile_reference if team_profiles else None,
            f"{team_profiles} team profiles",
            "TheSportsDBのチームプロフィールがありません。",
        ),
        status_item(
            "TheSportsDB + football-data.org",
            "Player profiles / squad verification",
            PLAYERS_PATH if players else None,
            (
                f"{len(players)} players "
                f"({verified_players} verified / {provisional_players} provisional)"
            ),
            "選手プロフィールがありません。",
        ),
        status_item(
            "TheSportsDB",
            "Managers / staff profiles",
            MANAGERS_PATH if managers else None,
            f"{len(managers)} managers / {len(staff)} staff",
            "監督・スタッフのプロフィールがありません。",
        ),
        status_item(
            "football-data.org",
            "Current squad verification",
            SQUAD_STATUS_PATH if squad_status.get("published") else None,
            f"{verified_squads} verified squads / {provisional_squads} provisional squads",
            "現所属選手の照合処理が完了していません。",
        ),
        {
            "source": "StatsBomb Open Data",
            "data_type": "Event data",
            "last_updated": None,
            "records": "0",
            "status": "Not implemented",
            "error": "現在の本番予測では使用していません。",
            "next_update": None,
            "is_stale": True,
        },
    ]


def main() -> None:
    items = build_status()
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"更新完了: {STATUS_PATH}")
    for item in items:
        print(
            f"{item['source']}: {item['status']} / "
            f"{item['records']}"
        )


if __name__ == "__main__":
    main()
