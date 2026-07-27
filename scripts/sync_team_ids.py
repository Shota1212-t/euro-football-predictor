from __future__ import annotations

import json
import re
import shutil
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
PREDICTIONS = DATA / "predictions"
BACKUP = DATA / "team_id_backup"

TEAMS_PATH = PROCESSED / "teams.json"
FIXTURES_PATH = PROCESSED / "fixtures.json"
PREDICTIONS_PATH = PREDICTIONS / "matches.json"
PLAYERS_PATH = PROCESSED / "players.json"
MANAGERS_PATH = PROCESSED / "managers.json"
STANDINGS_DIR = PROCESSED / "standings"
RANKINGS_DIR = PROCESSED / "rankings"

LEAGUE_META = {
    "pl": {"country": "England", "color": "#334155"},
    "laliga": {"country": "Spain", "color": "#334155"},
    "seriea": {"country": "Italy", "color": "#334155"},
    "bundesliga": {"country": "Germany", "color": "#334155"},
    "ligue1": {"country": "France", "color": "#334155"},
}

NAME_ALIASES = {
    "manchester city fc": "manchester city",
    "manchester united fc": "manchester united",
    "newcastle united fc": "newcastle united",
    "tottenham hotspur fc": "tottenham",
    "paris saint germain fc": "psg",
    "fc internazionale milano": "inter",
    "ac milan": "ac milan",
    "fc bayern munchen": "bayern munchen",
    "bayer 04 leverkusen": "bayer leverkusen",
    "club atletico de madrid": "atletico madrid",
    "real sociedad de futbol": "real sociedad",
    "olympique de marseille": "marseille",
    "olympique lyonnais": "lyon",
    "as monaco fc": "monaco",
    "lille osc": "lille",
}


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def comparable_name(value: str) -> str:
    normalized = normalize(value)
    return NAME_ALIASES.get(normalized, normalized)


def canonical_id(api_id) -> str:
    return f"fd-{int(api_id)}"


def backup_files(paths: list[Path]) -> None:
    BACKUP.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if not path.exists():
            continue
        relative = path.relative_to(DATA)
        destination = BACKUP / relative
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def fixture_team_records(fixtures: list[dict]) -> dict[str, dict]:
    records = {}
    for fixture in fixtures:
        league_id = fixture["league_id"]
        for side in ("home_team", "away_team"):
            team = fixture.get(side, {})
            api_id = team.get("api_id")
            if api_id is None:
                continue
            team_id = canonical_id(api_id)
            records[team_id] = {
                "id": team_id,
                "api_id": int(api_id),
                "name": team.get("name", ""),
                "short": team.get("short") or team.get("name", "")[:3].upper(),
                "league_id": league_id,
            }
    return records


def find_existing(record: dict, existing: dict[str, dict]) -> tuple[str | None, dict | None]:
    api_id = record.get("api_id")
    for old_id, team in existing.items():
        if team.get("api_id") == api_id:
            return old_id, team

    target_name = comparable_name(record.get("name", ""))
    target_short = normalize(record.get("short", ""))
    candidates = []
    for old_id, team in existing.items():
        old_name = comparable_name(team.get("name", ""))
        old_short = normalize(team.get("short", ""))
        if target_name == old_name or (target_short and target_short == old_short):
            candidates.append((old_id, team))
    return candidates[0] if len(candidates) == 1 else (None, None)


def build_master(fixtures: list[dict], existing: dict[str, dict]):
    fixture_records = fixture_team_records(fixtures)
    master = {}
    old_to_new = {}

    for team_id, record in fixture_records.items():
        old_id, old = find_existing(record, existing)
        meta = LEAGUE_META[record["league_id"]]
        master[team_id] = {
            "id": team_id,
            "api_id": record["api_id"],
            "name": record["name"],
            "short": record["short"],
            "league_id": record["league_id"],
            "country": old.get("country") if old else meta["country"],
            "stadium": old.get("stadium") if old else None,
            "manager_id": old.get("manager_id") if old else None,
            "logo_url": old.get("logo_url") if old else None,
            "color": old.get("color") if old else meta["color"],
        }
        if old_id:
            old_to_new[old_id] = team_id

    return master, old_to_new


def name_index(master: dict[str, dict]) -> dict[str, str]:
    result = {}
    for team_id, team in master.items():
        result[comparable_name(team["name"])] = team_id
        result[normalize(team["short"])] = team_id
    return result


def resolve_team_id(team: dict, index: dict[str, str]) -> str | None:
    api_id = team.get("api_id")
    if api_id is not None:
        return canonical_id(api_id)
    return index.get(comparable_name(team.get("name", ""))) or index.get(
        normalize(team.get("short", ""))
    )


def rewrite_fixtures(fixtures: list[dict]) -> None:
    for fixture in fixtures:
        for side in ("home_team", "away_team"):
            api_id = fixture.get(side, {}).get("api_id")
            if api_id is not None:
                fixture[side]["id"] = canonical_id(api_id)


def rewrite_predictions(predictions: list[dict], index: dict[str, str]) -> int:
    unresolved = 0
    for prediction in predictions:
        for side in ("home_team", "away_team"):
            team = prediction.get(side, {})
            resolved = resolve_team_id(team, index)
            if resolved:
                team["id"] = resolved
            else:
                unresolved += 1
    return unresolved


def rewrite_standings(master: dict[str, dict]) -> int:
    api_to_id = {team["api_id"]: team_id for team_id, team in master.items()}
    changed = 0
    for path in STANDINGS_DIR.glob("*.json"):
        payload = read_json(path, {})
        tables = {"total": payload} if isinstance(payload, list) else payload
        for rows in tables.values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                api_id = row.get("api_id")
                if api_id in api_to_id:
                    row["team_id"] = api_to_id[api_id]
                    changed += 1
        write_json(path, payload)
    return changed


def rewrite_entity_file(path: Path, old_to_new: dict[str, str]) -> int:
    payload = read_json(path, {})
    changed = 0
    if isinstance(payload, dict):
        items = payload.values()
    elif isinstance(payload, list):
        items = payload
    else:
        return 0
    for item in items:
        old_id = item.get("team_id")
        if old_id in old_to_new:
            item["team_id"] = old_to_new[old_id]
            changed += 1
    write_json(path, payload)
    return changed


def rewrite_rankings(old_to_new: dict[str, str]) -> int:
    changed = 0
    for path in RANKINGS_DIR.glob("*.json"):
        payload = read_json(path, {})
        groups = payload.values() if isinstance(payload, dict) else [payload]
        for rows in groups:
            if not isinstance(rows, list):
                continue
            for row in rows:
                old_id = row.get("team_id")
                if old_id in old_to_new:
                    row["team_id"] = old_to_new[old_id]
                    changed += 1
        write_json(path, payload)
    return changed


def main() -> None:
    fixtures = read_json(FIXTURES_PATH, [])
    existing = read_json(TEAMS_PATH, {})
    predictions = read_json(PREDICTIONS_PATH, [])
    if not fixtures:
        raise RuntimeError("fixtures.jsonが空です。先に日程を取得してください。")

    affected = [
        TEAMS_PATH,
        FIXTURES_PATH,
        PREDICTIONS_PATH,
        PLAYERS_PATH,
        MANAGERS_PATH,
        *STANDINGS_DIR.glob("*.json"),
        *RANKINGS_DIR.glob("*.json"),
    ]
    backup_files(affected)

    master, old_to_new = build_master(fixtures, existing)
    index = name_index(master)
    rewrite_fixtures(fixtures)
    unresolved = rewrite_predictions(predictions, index)
    standing_rows = rewrite_standings(master)
    player_rows = rewrite_entity_file(PLAYERS_PATH, old_to_new)
    manager_rows = rewrite_entity_file(MANAGERS_PATH, old_to_new)
    ranking_rows = rewrite_rankings(old_to_new)

    write_json(TEAMS_PATH, master)
    write_json(FIXTURES_PATH, fixtures)
    write_json(PREDICTIONS_PATH, predictions)

    print(f"チームマスタ: {len(master)}チーム")
    print(f"旧IDから移行: {len(old_to_new)}チーム")
    print(f"順位表ID更新: {standing_rows}行")
    print(f"選手ID更新: {player_rows}件")
    print(f"監督ID更新: {manager_rows}件")
    print(f"ランキングID更新: {ranking_rows}件")
    print(f"予測内の未解決ID: {unresolved}件")
    print(f"バックアップ: {BACKUP}")


if __name__ == "__main__":
    main()
