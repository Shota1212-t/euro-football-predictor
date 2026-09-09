from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import PROCESSED_DIR, RAW_DIR

REQUIRED = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"}
CURRENT_RESULTS_PATH = PROCESSED_DIR / "current_season_results.json"
CANONICAL_OPTIONAL = ["match_id", "league_id", "season_id", "kickoff", "HS", "AS", "HST", "AST", "source"]
RESULT_TO_FTR = {"Home Win": "H", "Draw": "D", "Away Win": "A"}
LEAGUE_TO_DIV = {
    "pl": "E0",
    "laliga": "SP1",
    "seriea": "I1",
    "bundesliga": "D1",
    "ligue1": "F1",
}


def _empty_current_season_frame() -> pd.DataFrame:
    columns = [
        "match_id", "league_id", "season_id", "Season", "Div", "kickoff",
        "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
        "HS", "AS", "HST", "AST", "source",
    ]
    return pd.DataFrame(columns=columns)


def load_current_season_matches(path: Path = CURRENT_RESULTS_PATH) -> pd.DataFrame:
    """終了済みの今シーズン結果を学習用の共通形式へ変換する。"""
    path = Path(path)
    if not path.exists():
        return _empty_current_season_frame()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"今シーズン結果JSONを読み込めません: {path}: {error}") from error
    if not isinstance(payload, list):
        raise ValueError(f"今シーズン結果JSONのルートが配列ではありません: {path}")

    rows = []
    for item in payload:
        if not isinstance(item, dict) or item.get("status") != "FINISHED":
            continue

        kickoff = pd.to_datetime(item.get("kickoff"), utc=True, errors="coerce")
        home_team = item.get("home_team") or {}
        away_team = item.get("away_team") or {}
        home_score = pd.to_numeric(item.get("home_score"), errors="coerce")
        away_score = pd.to_numeric(item.get("away_score"), errors="coerce")
        if (
            pd.isna(kickoff)
            or not home_team.get("name")
            or not away_team.get("name")
            or pd.isna(home_score)
            or pd.isna(away_score)
        ):
            continue

        score_result = "H" if home_score > away_score else "A" if home_score < away_score else "D"
        stated_result = RESULT_TO_FTR.get(item.get("actual_result"))
        if stated_result is not None and stated_result != score_result:
            raise ValueError(f"スコアとactual_resultが一致しません: match_id={item.get('id')}")

        league_id = item.get("league_id")
        rows.append(
            {
                "match_id": str(item.get("id")),
                "league_id": league_id,
                "season_id": item.get("season_id"),
                "Season": str(item.get("season_id")) if item.get("season_id") is not None else None,
                "Div": LEAGUE_TO_DIV.get(league_id, item.get("competition_code")),
                "kickoff": kickoff,
                # 過去CSVに時刻がないため、特徴量生成用DateはUTCの日付単位に揃える。
                "Date": kickoff.tz_convert("UTC").tz_localize(None).normalize(),
                "HomeTeam": home_team["name"],
                "AwayTeam": away_team["name"],
                "FTHG": int(home_score),
                "FTAG": int(away_score),
                "FTR": score_result,
                # 取得できないシュート情報は実測0と区別するためNaNのまま保持する。
                "HS": np.nan,
                "AS": np.nan,
                "HST": np.nan,
                "AST": np.nan,
                "source": "current_season_results",
            }
        )

    if not rows:
        return _empty_current_season_frame()

    frame = pd.DataFrame(rows)
    frame = frame.drop_duplicates(subset=["match_id"], keep="last")
    return frame.sort_values(["Date", "HomeTeam", "AwayTeam"], kind="stable").reset_index(drop=True)


def load_raw_matches(
    raw_dir=RAW_DIR,
    *,
    include_current_season: bool = False,
    current_results_path: Path = CURRENT_RESULTS_PATH,
):
    files = [path for path in Path(raw_dir).glob("*.csv") if path.name != "sample_schema.csv"]
    if not files:
        raise FileNotFoundError(f"CSVがありません: {raw_dir}")

    frames = []
    for path in sorted(files):
        frame = pd.read_csv(path, encoding_errors="replace")
        missing = REQUIRED - set(frame.columns)
        if missing:
            raise ValueError(f"{path.name} に必須列がありません: {sorted(missing)}")
        frame["source_file"] = path.name
        frame["source"] = "historical_csv"
        frames.append(frame)

    frame = pd.concat(frames, ignore_index=True)
    frame["Date"] = pd.to_datetime(frame["Date"], dayfirst=True, errors="coerce")
    frame = frame.dropna(subset=["Date", "HomeTeam", "AwayTeam", "FTR"])
    frame = frame.sort_values(["Date", "HomeTeam", "AwayTeam", "source_file"], kind="stable")
    frame = frame.drop_duplicates(["Date", "HomeTeam", "AwayTeam"], keep="last")
    frame = frame[frame["FTR"].isin(["H", "D", "A"])]

    if include_current_season:
        current = load_current_season_matches(current_results_path)
        if not current.empty:
            for column in frame.columns:
                if column not in current.columns:
                    current[column] = np.nan
            for column in current.columns:
                if column not in frame.columns:
                    frame[column] = np.nan
            frame = pd.concat([frame, current[frame.columns]], ignore_index=True)
            # 過去CSVと今シーズンJSONが同じ試合を持つ場合は、時刻とIDを持つJSON側を優先する。
            frame["_source_priority"] = frame["source"].eq("current_season_results").astype(int)
            frame = frame.sort_values(
                ["Date", "HomeTeam", "AwayTeam", "_source_priority"], kind="stable"
            ).drop_duplicates(["Date", "HomeTeam", "AwayTeam"], keep="last")
            frame = frame.drop(columns=["_source_priority"])

    return frame.sort_values(["Date", "HomeTeam", "AwayTeam"], kind="stable").reset_index(drop=True)


def save_clean_matches(df):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / "matches.csv"
    df.to_csv(path, index=False)
    return path
