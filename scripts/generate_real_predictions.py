from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_PATH = ROOT / "data" / "processed" / "fixtures.json"
EXTRA_FIXTURES_PATH = ROOT / "data" / "processed" / "extra_fixtures.json"
EXTRA_FIXTURES_STATUS_PATH = ROOT / "data" / "processed" / "extra_fixtures_status.json"
MATCHES_PATH = ROOT / "data" / "processed" / "matches.csv"
SECOND_DIVISION_DIR = ROOT / "data" / "raw" / "football_data_co_uk_second_division"
MODEL_PATH = ROOT / "ml" / "models" / "lightgbm_model.joblib"
META_PATH = ROOT / "ml" / "models" / "lightgbm_metadata.json"
OUTPUT_PATH = ROOT / "data" / "predictions" / "matches.json"
TEMP_OUTPUT_PATH = OUTPUT_PATH.with_suffix(".json.tmp")
BACKUP_PATH = ROOT / "data" / "predictions" / "matches_before_real_predictions.json"

LEAGUE_NAMES = {
    "pl": "Premier League",
    "laliga": "La Liga",
    "seriea": "Serie A",
    "bundesliga": "Bundesliga",
    "ligue1": "Ligue 1",
}

# football-data.org name -> Football-Data.co.uk CSV name
TEAM_ALIASES = {
    "afc bournemouth": "Bournemouth",
    "arsenal fc": "Arsenal",
    "aston villa fc": "Aston Villa",
    "brighton hove albion fc": "Brighton",
    "brentford fc": "Brentford",
    "burnley fc": "Burnley",
    "chelsea fc": "Chelsea",
    "crystal palace fc": "Crystal Palace",
    "everton fc": "Everton",
    "fulham fc": "Fulham",
    "ipswich town fc": "Ipswich",
    "leeds united fc": "Leeds",
    "liverpool fc": "Liverpool",
    "manchester city fc": "Man City",
    "manchester united fc": "Man United",
    "newcastle united fc": "Newcastle",
    "nottingham forest fc": "Nott'm Forest",
    "sunderland afc": "Sunderland",
    "tottenham hotspur fc": "Tottenham",
    "west ham united fc": "West Ham",
    "wolverhampton wanderers fc": "Wolves",
    "deportivo alaves": "Alaves",
    "athletic club": "Ath Bilbao",
    "club atletico de madrid": "Ath Madrid",
    "real betis balompie": "Betis",
    "rc celta de vigo": "Celta",
    "rcd espanyol de barcelona": "Espanol",
    "getafe cf": "Getafe",
    "girona fc": "Girona",
    "levante ud": "Levante",
    "ca osasuna": "Osasuna",
    "rayo vallecano de madrid": "Vallecano",
    "real madrid cf": "Real Madrid",
    "real sociedad de futbol": "Sociedad",
    "sevilla fc": "Sevilla",
    "valencia cf": "Valencia",
    "villarreal cf": "Villarreal",
    "ac milan": "Milan",
    "fc internazionale milano": "Inter",
    "internazionale": "Inter",
    "as roma": "Roma",
    "ss lazio": "Lazio",
    "ssc napoli": "Napoli",
    "atalanta bc": "Atalanta",
    "acf fiorentina": "Fiorentina",
    "bologna fc 1909": "Bologna",
    "juventus fc": "Juventus",
    "torino fc": "Torino",
    "udinese calcio": "Udinese",
    "hellas verona fc": "Verona",
    "us lecce": "Lecce",
    "us sassuolo calcio": "Sassuolo",
    "fc bayern munchen": "Bayern Munich",
    "borussia dortmund": "Dortmund",
    "bayer 04 leverkusen": "Leverkusen",
    "eintracht frankfurt": "Ein Frankfurt",
    "borussia monchengladbach": "M'gladbach",
    "1 fsv mainz 05": "Mainz",
    "rb leipzig": "RB Leipzig",
    "sc freiburg": "Freiburg",
    "tsg 1899 hoffenheim": "Hoffenheim",
    "vfb stuttgart": "Stuttgart",
    "vfl wolfsburg": "Wolfsburg",
    "sv werder bremen": "Werder Bremen",
    "1 fc union berlin": "Union Berlin",
    "paris saint germain fc": "Paris SG",
    "olympique de marseille": "Marseille",
    "olympique lyonnais": "Lyon",
    "as monaco fc": "Monaco",
    "losc lille": "Lille",
    "ogc nice": "Nice",
    "stade rennais fc 1901": "Rennes",
    "rc strasbourg alsace": "Strasbourg",
    "toulouse fc": "Toulouse",
    "fc nantes": "Nantes",
    "rc lens": "Lens",
    "fc lorient": "Lorient",
    "stade brestois 29": "Brest",
    "angers sco": "Angers",
}

# Additional aliases verified against the current API fixture names.
TEAM_ALIASES.update({
    "brighton and hove albion fc": "Brighton",
    "genoa cfc": "Genoa",
    "como 1907": "Como",
    "ac monza": "Monza",
    "parma calcio 1913": "Parma",
    "cagliari calcio": "Cagliari",
    "fc internazionale milano": "Inter",
    "ssc napoli": "Napoli",
    "1 fc koln": "FC Koln",
    "racing club de lens": "Lens",
    "aj auxerre": "Auxerre",
    "lille osc": "Lille",
    "le havre ac": "Le Havre",
    "fc barcelona": "Barcelona",
    "paris fc": "Paris FC",
    "mainz 05": "Mainz",
})


SECOND_DIVISION_ALIASES = {
    "real racing club de santander": "Santander",
    "rc deportivo la coruna": "La Coruna",
    "malaga cf": "Malaga",
    "coventry city fc": "Coventry",
    "hull city afc": "Hull",
    "le mans fc": "Le Mans",
    "es troyes ac": "Troyes",
    "sc paderborn 07": "Paderborn",
    "sv 07 elversberg": "Elversberg",
    "hamburger sv": "Hamburg",
    "fc schalke 04": "Schalke 04",
}


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def slugify(value: str) -> str:
    return normalize_name(value).replace(" ", "-") or "unknown"


def csv_team_name(api_name: str, known_teams: set[str]) -> str | None:
    key = normalize_name(api_name)
    alias = TEAM_ALIASES.get(key)
    if alias in known_teams:
        return alias

    normalized_known = {normalize_name(name): name for name in known_teams}
    if key in normalized_known:
        return normalized_known[key]

    # Remove generic club prefixes/suffixes and founding years, then retry.
    removable = {
        "fc", "afc", "cf", "ac", "as", "ss", "ssc", "us", "rc", "rcd",
        "club", "calcio", "football", "futbol", "de", "the",
    }
    tokens = [
        token for token in key.split()
        if token not in removable and not re.fullmatch(r"(?:18|19|20)\d{2}", token)
    ]
    stripped = " ".join(tokens)
    if stripped in normalized_known:
        return normalized_known[stripped]

    # Conservative containment match: use only a unique match.
    candidates = [
        original for normalized, original in normalized_known.items()
        if len(stripped) >= 5 and (stripped in normalized or normalized in stripped)
    ]
    return candidates[0] if len(candidates) == 1 else None



def second_division_team_name(api_name: str, known_teams: set[str]) -> str | None:
    key = normalize_name(api_name)
    alias = SECOND_DIVISION_ALIASES.get(key)
    if alias in known_teams:
        return alias

    normalized_known = {normalize_name(name): name for name in known_teams}
    if key in normalized_known:
        return normalized_known[key]

    removable = {
        "fc", "afc", "cf", "ac", "as", "ss", "ssc", "us", "rc", "rcd",
        "club", "calcio", "football", "futbol", "de", "the",
    }
    tokens = [
        token for token in key.split()
        if token not in removable and not re.fullmatch(r"(?:18|19|20)\d{2}", token)
    ]
    stripped = " ".join(tokens)
    if stripped in normalized_known:
        return normalized_known[stripped]
    return None


def load_second_division_matches() -> pd.DataFrame:
    files = sorted(SECOND_DIVISION_DIR.glob("*.csv"))
    if not files:
        raise FileNotFoundError(
            f"2部CSVがありません: {SECOND_DIVISION_DIR}"
        )

    required = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"}
    useful_columns = required | {"Div", "HS", "AS", "HST", "AST"}
    frames = []
    for path in files:
        frame = pd.read_csv(
            path,
            encoding_errors="replace",
            usecols=lambda column: column in useful_columns,
        )
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(
                f"{path.name} に必須列がありません: {sorted(missing)}"
            )
        frames.append(frame)

    matches = pd.concat(frames, ignore_index=True)
    matches["Date"] = pd.to_datetime(
        matches["Date"],
        dayfirst=True,
        errors="coerce",
    )
    matches = matches.dropna(
        subset=["Date", "HomeTeam", "AwayTeam", "FTR"]
    )
    matches = matches[matches["FTR"].isin(["H", "D", "A"])]
    return matches.sort_values("Date").drop_duplicates(
        ["Date", "HomeTeam", "AwayTeam"],
        keep="last",
    ).reset_index(drop=True)


def load_inputs():
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    matches = pd.read_csv(MATCHES_PATH, parse_dates=["Date"])
    matches = matches.dropna(subset=["Date", "HomeTeam", "AwayTeam", "FTR"])
    matches = matches.sort_values("Date").reset_index(drop=True)
    second_division_matches = load_second_division_matches()
    model = joblib.load(MODEL_PATH)
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    extra_fixtures = (
        json.loads(EXTRA_FIXTURES_PATH.read_text(encoding="utf-8"))
        if EXTRA_FIXTURES_PATH.exists()
        else []
    )
    extra_status = (
        json.loads(EXTRA_FIXTURES_STATUS_PATH.read_text(encoding="utf-8"))
        if EXTRA_FIXTURES_STATUS_PATH.exists()
        else {}
    )
    return fixtures, matches, second_division_matches, model, meta, extra_fixtures, extra_status


def team_history(matches: pd.DataFrame, team: str, before: pd.Timestamp) -> pd.DataFrame:
    # API kickoff is timezone-aware UTC, while CSV dates are timezone-naive.
    before_naive = before.tz_convert("UTC").tz_localize(None) if before.tzinfo else before
    return matches[
        (matches["Date"] < before_naive)
        & ((matches["HomeTeam"] == team) | (matches["AwayTeam"] == team))
    ].tail(20)


def recent_stats(history: pd.DataFrame, team: str, kickoff: pd.Timestamp, window: int = 5) -> dict:
    recent = history.tail(window)
    if recent.empty:
        return {"points": 0.0, "gf": 0.0, "ga": 0.0, "shots": 0.0, "sot": 0.0,
                "days": 14, "played": 0, "last7": 0, "last14": 0, "form": ""}

    points, gf, ga, shots, sot, form = [], [], [], [], [], []
    for _, row in recent.iterrows():
        is_home = row["HomeTeam"] == team
        result = row["FTR"]
        won = (is_home and result == "H") or ((not is_home) and result == "A")
        pts = 3 if won else 1 if result == "D" else 0
        points.append(pts)
        form.append("W" if pts == 3 else "D" if pts == 1 else "L")
        gf.append(float(row["FTHG"] if is_home else row["FTAG"]))
        ga.append(float(row["FTAG"] if is_home else row["FTHG"]))
        shots.append(float(pd.to_numeric(row.get("HS" if is_home else "AS", 0), errors="coerce") or 0))
        sot.append(float(pd.to_numeric(row.get("HST" if is_home else "AST", 0), errors="coerce") or 0))

    last_date = pd.Timestamp(recent.iloc[-1]["Date"])
    days = max(1, (kickoff.tz_localize(None) - last_date.tz_localize(None)).days)
    dates = pd.to_datetime(history["Date"])
    kickoff_naive = kickoff.tz_localize(None)
    last7 = int(((dates >= kickoff_naive - pd.Timedelta(days=7)) & (dates < kickoff_naive)).sum())
    last14 = int(((dates >= kickoff_naive - pd.Timedelta(days=14)) & (dates < kickoff_naive)).sum())

    return {
        "points": float(np.mean(points)), "gf": float(np.mean(gf)), "ga": float(np.mean(ga)),
        "shots": float(np.mean(shots)), "sot": float(np.mean(sot)), "days": days,
        "played": len(recent), "last7": last7, "last14": last14, "form": "".join(form),
    }


DIV_BY_LEAGUE = {
    "pl": "E0",
    "laliga": "SP1",
    "seriea": "I1",
    "bundesliga": "D1",
    "ligue1": "F1",
}


def league_average_stats(matches: pd.DataFrame, league_id: str, kickoff: pd.Timestamp) -> dict:
    division = DIV_BY_LEAGUE[league_id]
    league_matches = matches[matches["Div"] == division] if "Div" in matches.columns else matches
    teams = sorted(set(league_matches["HomeTeam"]) | set(league_matches["AwayTeam"]))
    values = []
    for team in teams:
        stats = recent_stats(team_history(league_matches, team, kickoff), team, kickoff)
        if stats["played"] >= 5:
            values.append(stats)

    if not values:
        return {
            "points": 1.0, "gf": 1.2, "ga": 1.2, "shots": 10.0, "sot": 4.0,
            "days": 14, "played": 5, "last7": 0, "last14": 0, "form": "EST",
        }

    numeric = ["points", "gf", "ga", "shots", "sot", "days", "played", "last7", "last14"]
    averaged = {key: float(np.mean([item[key] for item in values])) for key in numeric}
    averaged["days"] = max(1, int(round(averaged["days"])))
    averaged["played"] = 5
    averaged["last7"] = int(round(averaged["last7"]))
    averaged["last14"] = int(round(averaged["last14"]))
    averaged["form"] = "EST"
    return averaged


def extra_competition_context(
    extra_fixtures: list[dict],
    team_id: str,
    kickoff: pd.Timestamp,
    league_stats: dict,
    extra_status: dict,
) -> dict:
    kickoff_utc = kickoff.tz_convert("UTC") if kickoff.tzinfo else kickoff.tz_localize("UTC")
    events = []
    for event in extra_fixtures:
        if team_id not in set(event.get("team_ids") or []):
            continue
        event_kickoff = pd.to_datetime(event.get("kickoff"), utc=True, errors="coerce")
        if pd.isna(event_kickoff) or event_kickoff >= kickoff_utc:
            continue
        events.append((event_kickoff, event))
    events.sort(key=lambda item: item[0])

    last7_extra = sum(
        1 for date, _ in events
        if date >= kickoff_utc - pd.Timedelta(days=7)
    )
    last14_extra = sum(
        1 for date, _ in events
        if date >= kickoff_utc - pd.Timedelta(days=14)
    )
    league_last_date = kickoff_utc - pd.Timedelta(days=int(league_stats["days"]))
    latest_extra = events[-1] if events else None
    latest_is_extra = bool(latest_extra and latest_extra[0] > league_last_date)
    latest_event = latest_extra[1] if latest_is_extra and latest_extra else None
    extra_days = (
        max(1, int((kickoff_utc - latest_extra[0]).total_seconds() // 86400))
        if latest_extra else int(league_stats["days"])
    )
    days_since_last = min(int(league_stats["days"]), extra_days)
    latest_type = latest_event.get("competition_type") if latest_event else None
    had_extra_time = bool(
        latest_event and latest_event.get("had_extra_time_or_penalties") is True
    )
    coverage = extra_status.get("coverage") or {}
    return {
        "last7": int(league_stats["last7"]) + last7_extra,
        "last14": int(league_stats["last14"]) + last14_extra,
        "days": days_since_last,
        "after_european": latest_type == "european",
        "after_domestic_cup": latest_type == "domestic_cup",
        "had_extra_time_or_penalties": had_extra_time,
        "extra_matches_last_7d": last7_extra,
        "extra_matches_last_14d": last14_extra,
        "last_extra_competition": latest_event.get("competition_name") if latest_event else None,
        "last_extra_match_source": latest_event.get("source") if latest_event else None,
        "european_data_status": coverage.get("champions_league", "not_available"),
        "domestic_cup_data_status": coverage.get(
            "other_european_and_domestic_cups", "not_available"
        ),
        "extra_time_data_status": coverage.get(
            "extra_time_and_penalties", "not_available"
        ),
        "official_matches_data_completeness": (
            "league_and_champions_league_with_partial_cup_supplement"
            if extra_status.get("success")
            else "league_only"
        ),
    }


def fatigue_payload(stats: dict, context: dict | None = None) -> dict:
    context = context or {
        "last7": stats["last7"],
        "last14": stats["last14"],
        "days": stats["days"],
        "after_european": False,
        "after_domestic_cup": False,
        "had_extra_time_or_penalties": False,
        "extra_matches_last_7d": 0,
        "extra_matches_last_14d": 0,
        "last_extra_competition": None,
        "last_extra_match_source": None,
        "european_data_status": "not_available",
        "domestic_cup_data_status": "not_available",
        "extra_time_data_status": "not_available",
        "official_matches_data_completeness": "league_only",
    }
    score = (
        context["last7"] * 12
        + context["last14"] * 5
        + max(0, 10 - context["days"]) * 2
        + (10 if context["after_european"] else 0)
        + (6 if context["after_domestic_cup"] else 0)
        + (10 if context["days"] <= 3 else 0)
        + (8 if context["had_extra_time_or_penalties"] else 0)
    )
    score = max(0, min(100, int(score)))
    level = "Low" if score < 40 else "Medium" if score < 70 else "High"
    return {
        "index": score,
        "level": level,
        "matches_last_7d": context["last7"],
        "matches_last_14d": context["last14"],
        "days_since_last_match": context["days"],
        "after_european_competition": context["after_european"],
        "after_domestic_cup": context["after_domestic_cup"],
        "had_extra_time_or_penalties": context["had_extra_time_or_penalties"],
        "extra_matches_last_7d": context["extra_matches_last_7d"],
        "extra_matches_last_14d": context["extra_matches_last_14d"],
        "last_extra_competition": context["last_extra_competition"],
        "last_extra_match_source": context["last_extra_match_source"],
        "european_competition_data_status": context["european_data_status"],
        "domestic_cup_data_status": context["domestic_cup_data_status"],
        "extra_time_data_status": context["extra_time_data_status"],
        "official_matches_data_completeness": context[
            "official_matches_data_completeness"
        ],
    }


def build_features(home: dict, away: dict) -> dict:
    return {
        "home_recent_points": home["points"], "away_recent_points": away["points"],
        "recent_points_diff": home["points"] - away["points"],
        "home_recent_gf": home["gf"], "away_recent_gf": away["gf"],
        "recent_gf_diff": home["gf"] - away["gf"],
        "home_recent_ga": home["ga"], "away_recent_ga": away["ga"],
        "recent_ga_diff": home["ga"] - away["ga"],
        "home_recent_shots": home["shots"], "away_recent_shots": away["shots"],
        "home_recent_sot": home["sot"], "away_recent_sot": away["sot"],
        "home_days_rest": home["days"], "away_days_rest": away["days"],
        "rest_days_diff": home["days"] - away["days"],
        "home_history_count": home["played"], "away_history_count": away["played"],
        "B365H": np.nan, "B365D": np.nan, "B365A": np.nan,
    }


def team_payload(team: dict, league_id: str) -> dict:
    name = team.get("name", "Unknown")
    api_id = team.get("api_id")
    team_id = f"fd-{int(api_id)}" if api_id is not None else slugify(name)
    return {
        "id": team_id,
        "api_id": api_id,
        "name": name,
        "short": team.get("short") or name[:3].upper(),
        "league_id": league_id,
        "color": "#334155",
    }


FEATURE_LABELS = {
    "home_recent_points": "ホーム側の直近勝点",
    "away_recent_points": "アウェイ側の直近勝点",
    "recent_points_diff": "直近勝点差",
    "home_recent_gf": "ホーム側の平均得点",
    "away_recent_gf": "アウェイ側の平均得点",
    "recent_gf_diff": "平均得点差",
    "home_recent_ga": "ホーム側の平均失点",
    "away_recent_ga": "アウェイ側の平均失点",
    "recent_ga_diff": "平均失点差",
    "home_recent_shots": "ホーム側の平均シュート数",
    "away_recent_shots": "アウェイ側の平均シュート数",
    "home_recent_sot": "ホーム側の平均枠内シュート数",
    "away_recent_sot": "アウェイ側の平均枠内シュート数",
    "home_days_rest": "ホーム側の休養日数",
    "away_days_rest": "アウェイ側の休養日数",
    "rest_days_diff": "休養日数差",
    "home_history_count": "ホーム側の履歴試合数",
    "away_history_count": "アウェイ側の履歴試合数",
}


def create_shap_context(model):
    """Pipeline内部のLightGBMへSHAPを適用するための部品を返す。"""
    if not hasattr(model, "named_steps"):
        return None
    imputer = model.named_steps.get("imputer")
    classifier = model.named_steps.get("model")
    if imputer is None or classifier is None:
        return None
    return {
        "imputer": imputer,
        "explainer": shap.TreeExplainer(classifier),
    }


def class_shap_vector(shap_values, class_index: int, feature_count: int) -> np.ndarray:
    """SHAPのバージョン差による多クラス出力形式を吸収する。"""
    if isinstance(shap_values, list):
        values = np.asarray(shap_values[class_index])
        return values[0] if values.ndim == 2 else values

    values = np.asarray(shap_values)
    if values.ndim == 3:
        # 現行SHAP: samples x features x classes
        if values.shape[1] == feature_count:
            return values[0, :, class_index]
        # 旧形式の可能性: classes x samples x features
        if values.shape[2] == feature_count:
            return values[class_index, 0, :]
    if values.ndim == 2 and values.shape[1] == feature_count:
        return values[0]
    raise ValueError(f"未対応のSHAP出力形状です: {values.shape}")


def build_shap_explanations(
    shap_context,
    X: pd.DataFrame,
    feature_dict: dict,
    predicted_class_index: int,
    predicted_label: str,
    limit: int = 5,
) -> list[dict]:
    if shap_context is None:
        return []

    transformed = shap_context["imputer"].transform(X)
    shap_values = shap_context["explainer"].shap_values(transformed)
    vector = class_shap_vector(
        shap_values,
        predicted_class_index,
        feature_count=len(X.columns),
    )

    ranked = sorted(
        range(len(X.columns)),
        key=lambda index: abs(float(vector[index])),
        reverse=True,
    )[:limit]

    explanations = []
    for index in ranked:
        feature = X.columns[index]
        contribution = float(vector[index])
        raw_value = feature_dict.get(feature)
        value = None if pd.isna(raw_value) else round(float(raw_value), 4)
        impact = "supports" if contribution >= 0 else "opposes"
        label = FEATURE_LABELS.get(feature, feature)
        action = "押し上げた" if impact == "supports" else "押し下げた"
        explanations.append(
            {
                "feature": feature,
                "label": label,
                "value": value,
                "shap_value": round(contribution, 6),
                "impact": impact,
                "target": predicted_label,
                "text": f"{label}が{predicted_label}のモデル出力を{action}",
            }
        )
    return explanations


REQUIRED_PREDICTION_KEYS = {
    "id",
    "league_id",
    "league_name",
    "kickoff",
    "home_team",
    "away_team",
    "home_win_probability",
    "draw_probability",
    "away_win_probability",
    "predicted_result",
    "confidence",
    "data_quality",
    "model_version",
}


def validate_predictions(predictions: list[dict], expected_count: int) -> None:
    if len(predictions) != expected_count:
        raise ValueError(
            f"予測件数が不正です: expected={expected_count}, actual={len(predictions)}"
        )

    ids = set()
    for index, item in enumerate(predictions):
        missing = REQUIRED_PREDICTION_KEYS - set(item)
        if missing:
            raise ValueError(
                f"予測{index}に必須項目がありません: {sorted(missing)}"
            )

        match_id = str(item["id"])
        if match_id in ids:
            raise ValueError(f"試合IDが重複しています: {match_id}")
        ids.add(match_id)

        for side in ("home_team", "away_team"):
            team = item.get(side)
            if not isinstance(team, dict) or not team.get("id") or not team.get("name"):
                raise ValueError(f"予測{index}の{side}が不正です")

        probabilities = [
            item["home_win_probability"],
            item["draw_probability"],
            item["away_win_probability"],
        ]
        if not all(isinstance(value, (int, float)) for value in probabilities):
            raise ValueError(f"予測{index}の確率が数値ではありません")
        if not all(0 <= float(value) <= 100 for value in probabilities):
            raise ValueError(f"予測{index}の確率が0〜100の範囲外です")
        probability_sum = sum(float(value) for value in probabilities)
        if abs(probability_sum - 100.0) > 0.2:
            raise ValueError(
                f"予測{index}の確率合計が不正です: {probability_sum:.3f}"
            )


def atomic_write_predictions(predictions: list[dict]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEMP_OUTPUT_PATH.unlink(missing_ok=True)

    try:
        with TEMP_OUTPUT_PATH.open("w", encoding="utf-8") as file:
            json.dump(predictions, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())

        written = json.loads(TEMP_OUTPUT_PATH.read_text(encoding="utf-8"))
        validate_predictions(written, expected_count=len(predictions))

        if OUTPUT_PATH.exists() and not BACKUP_PATH.exists():
            BACKUP_PATH.write_bytes(OUTPUT_PATH.read_bytes())

        os.replace(TEMP_OUTPUT_PATH, OUTPUT_PATH)
    except Exception:
        TEMP_OUTPUT_PATH.unlink(missing_ok=True)
        raise


def main() -> None:
    for path in (FIXTURES_PATH, MATCHES_PATH, MODEL_PATH, META_PATH):
        if not path.exists():
            raise FileNotFoundError(f"必要なファイルがありません: {path}")

    (
        fixtures,
        matches,
        second_division_matches,
        model,
        meta,
        extra_fixtures,
        extra_status,
    ) = load_inputs()
    shap_context = create_shap_context(model)
    if shap_context is None:
        print("WARNING: 本番モデルが通常のPipelineではないためSHAP説明を省略します。")
    known_teams = set(matches["HomeTeam"].dropna()) | set(matches["AwayTeam"].dropna())
    known_second_division_teams = (
        set(second_division_matches["HomeTeam"].dropna())
        | set(second_division_matches["AwayTeam"].dropna())
    )
    now = pd.Timestamp(datetime.now(timezone.utc))
    future = [f for f in fixtures if pd.Timestamp(f["kickoff"]) >= now]
    future.sort(key=lambda f: f["kickoff"])

    selected = []
    selected_matchdays = {}
    for league_id in LEAGUE_NAMES:
        league_fixtures = [
            fixture
            for fixture in future
            if fixture.get("league_id") == league_id
            and fixture.get("matchday") is not None
        ]
        if not league_fixtures:
            print(f"WARNING: {league_id} has no future fixtures with matchday")
            continue

        next_matchday = min(int(fixture["matchday"]) for fixture in league_fixtures)
        matchday_fixtures = [
            fixture
            for fixture in league_fixtures
            if int(fixture["matchday"]) == next_matchday
        ]
        selected.extend(matchday_fixtures)
        selected_matchdays[league_id] = next_matchday

    selected.sort(key=lambda fixture: fixture["kickoff"])

    predictions = []
    full_history_count = 0
    second_division_history_count = 0
    estimated_count = 0
    missing_first_division_history_count = 0
    history_shortage_count = 0
    shap_success_count = 0
    shap_failure_count = 0

    for fixture in selected:
        league_id = fixture["league_id"]
        home_api = fixture["home_team"]["name"]
        away_api = fixture["away_team"]["name"]
        home_name = csv_team_name(home_api, known_teams)
        away_name = csv_team_name(away_api, known_teams)
        home_second_name = None
        away_second_name = None
        kickoff = pd.Timestamp(fixture["kickoff"])
        league_average = league_average_stats(matches, league_id, kickoff)

        if home_name is None:
            missing_first_division_history_count += 1
            home_second_name = second_division_team_name(
                home_api,
                known_second_division_teams,
            )
        if away_name is None:
            missing_first_division_history_count += 1
            away_second_name = second_division_team_name(
                away_api,
                known_second_division_teams,
            )

        home_source = "first_division"
        away_source = "first_division"

        if home_name is not None:
            home_stats = recent_stats(
                team_history(matches, home_name, kickoff),
                home_name,
                kickoff,
            )
        elif home_second_name is not None:
            home_stats = recent_stats(
                team_history(second_division_matches, home_second_name, kickoff),
                home_second_name,
                kickoff,
            )
            home_source = "second_division"
        else:
            home_stats = dict(league_average)
            home_source = "estimated"

        if away_name is not None:
            away_stats = recent_stats(
                team_history(matches, away_name, kickoff),
                away_name,
                kickoff,
            )
        elif away_second_name is not None:
            away_stats = recent_stats(
                team_history(second_division_matches, away_second_name, kickoff),
                away_second_name,
                kickoff,
            )
            away_source = "second_division"
        else:
            away_stats = dict(league_average)
            away_source = "estimated"

        if home_stats["played"] < 5:
            history_shortage_count += 1
            home_stats = dict(league_average)
            home_source = "estimated"
        if away_stats["played"] < 5:
            history_shortage_count += 1
            away_stats = dict(league_average)
            away_source = "estimated"

        estimated = "estimated" in {home_source, away_source}
        uses_second_division = "second_division" in {home_source, away_source}
        if estimated:
            data_quality = "estimated"
            estimated_count += 1
        elif uses_second_division:
            data_quality = "second_division_history"
            second_division_history_count += 1
        else:
            data_quality = "full_history"
            full_history_count += 1

        home_team_id = team_payload(fixture["home_team"], league_id)["id"]
        away_team_id = team_payload(fixture["away_team"], league_id)["id"]
        home_fatigue_context = extra_competition_context(
            extra_fixtures,
            home_team_id,
            kickoff,
            home_stats,
            extra_status,
        )
        away_fatigue_context = extra_competition_context(
            extra_fixtures,
            away_team_id,
            kickoff,
            away_stats,
            extra_status,
        )

        feature_dict = build_features(home_stats, away_stats)
        X = pd.DataFrame([{col: feature_dict.get(col, np.nan) for col in meta["features"]}])
        probs = model.predict_proba(X)[0]
        hp, dp, ap = [round(float(x) * 100, 1) for x in probs]
        labels = ["Home Win", "Draw", "Away Win"]
        winner = int(np.argmax(probs))
        ordered = sorted([hp, dp, ap], reverse=True)
        gap = ordered[0] - ordered[1]
        confidence = "High" if gap >= 20 else "Medium" if gap >= 10 else "Low"
        if estimated:
            confidence = "Low"

        try:
            explanations = build_shap_explanations(
                shap_context,
                X,
                feature_dict,
                predicted_class_index=winner,
                predicted_label=labels[winner],
            )
            if explanations:
                shap_success_count += 1
        except Exception as error:
            explanations = []
            shap_failure_count += 1
            print(f"WARNING: SHAP説明生成失敗 match={fixture['id']}: {error}")

        reasons = [
            f"{home_api}: 直近勝点平均 {home_stats['points']:.2f}",
            f"{away_api}: 直近勝点平均 {away_stats['points']:.2f}",
            "試合前オッズは未取得のため、モデル内の欠損値補完を使用しています。",
        ]
        if home_source == "second_division":
            reasons.append(
                f"{home_api}: 前シーズンまでの2部実績を使用しています。"
            )
        elif home_source == "estimated":
            reasons.append(
                f"{home_api}: 十分な履歴がないためリーグ平均値で推定しています。"
            )
        if away_source == "second_division":
            reasons.append(
                f"{away_api}: 前シーズンまでの2部実績を使用しています。"
            )
        elif away_source == "estimated":
            reasons.append(
                f"{away_api}: 十分な履歴がないためリーグ平均値で推定しています。"
            )

        predictions.append({
            "id": str(fixture["id"]), "league_id": league_id,
            "league_name": LEAGUE_NAMES[league_id], "kickoff": fixture["kickoff"],
            "home_team": team_payload(fixture["home_team"], league_id),
            "away_team": team_payload(fixture["away_team"], league_id),
            "home_win_probability": hp, "draw_probability": dp, "away_win_probability": ap,
            "predicted_result": labels[winner], "confidence": confidence,
            "data_quality": data_quality,
            "home_fatigue": fatigue_payload(home_stats, home_fatigue_context),
            "away_fatigue": fatigue_payload(away_stats, away_fatigue_context),
            "comparison": [
                {"label": "直近勝点", "home_value": f"{home_stats['points']:.2f}", "away_value": f"{away_stats['points']:.2f}"},
                {"label": "平均得点", "home_value": f"{home_stats['gf']:.2f}", "away_value": f"{away_stats['gf']:.2f}"},
                {"label": "平均失点", "home_value": f"{home_stats['ga']:.2f}", "away_value": f"{away_stats['ga']:.2f}"},
                {"label": "直近成績", "home_value": home_stats["form"], "away_value": away_stats["form"]},
            ],
            "reasons": reasons, "h2h_summary": None, "odds": None,
            "explanations": explanations,
            "explanation_method": "SHAP TreeExplainer" if explanations else None,
            "explanation_note": (
                "SHAP値は予測クラスのモデル出力への寄与であり、確率差そのものではありません。"
                if explanations else
                "SHAP説明を生成できませんでした。"
            ),
            "history_source": {"home": home_source, "away": away_source},
            "model_version": meta.get("version", "lightgbm"),
        })

    if not predictions:
        raise RuntimeError("予測を生成できませんでした。日程データを確認してください。")

    validate_predictions(predictions, expected_count=len(selected))
    atomic_write_predictions(predictions)

    print(f"予測生成: {len(predictions)}試合")
    for league_id, matchday in selected_matchdays.items():
        count = sum(1 for item in predictions if item["league_id"] == league_id)
        print(f"{league_id}: matchday {matchday} / {count}試合")
    print(f"1部実履歴使用: {full_history_count}試合")
    print(f"2部実履歴使用: {second_division_history_count}試合")
    print(f"リーグ平均補完: {estimated_count}試合")
    print(f"過去1部CSV未収録チーム数: {missing_first_division_history_count}")
    print(f"履歴不足チーム数: {history_shortage_count}")
    print(f"SHAP説明生成: {shap_success_count}試合")
    print(f"SHAP説明失敗: {shap_failure_count}試合")
    print(f"追加大会データ: {len(extra_fixtures)}件")
    print(f"追加大会データ状態: {'Success' if extra_status.get('success') else 'Unavailable'}")
    print(f"保存先: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
