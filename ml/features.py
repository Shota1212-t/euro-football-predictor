import numpy as np
import pandas as pd
from .config import TARGET_MAP
BASE_OPTIONAL=['HS','AS','HST','AST','B365H','B365D','B365A']

MODEL_FEATURE_COLUMNS = [
    "home_recent_points", "away_recent_points", "recent_points_diff",
    "home_recent_gf", "away_recent_gf", "recent_gf_diff",
    "home_recent_ga", "away_recent_ga", "recent_ga_diff",
    "home_recent_shots", "away_recent_shots",
    "home_recent_sot", "away_recent_sot",
    "home_days_rest", "away_days_rest", "rest_days_diff",
    "home_history_count", "away_history_count",
]


def build_prediction_features(home: dict, away: dict) -> dict:
    """学習時と本番推論時で共通の特徴量名・計算式を使用する。"""
    return {
        "home_recent_points": home["points"],
        "away_recent_points": away["points"],
        "recent_points_diff": home["points"] - away["points"],
        "home_recent_gf": home["gf"],
        "away_recent_gf": away["gf"],
        "recent_gf_diff": home["gf"] - away["gf"],
        "home_recent_ga": home["ga"],
        "away_recent_ga": away["ga"],
        "recent_ga_diff": home["ga"] - away["ga"],
        "home_recent_shots": home["shots"],
        "away_recent_shots": away["shots"],
        "home_recent_sot": home["sot"],
        "away_recent_sot": away["sot"],
        "home_days_rest": home["days"],
        "away_days_rest": away["days"],
        "rest_days_diff": home["days"] - away["days"],
        "home_history_count": home["played"],
        "away_history_count": away["played"],
    }

def _points(result, side):
    if result=='D': return 1
    return 3 if (result=='H' and side=='home') or (result=='A' and side=='away') else 0

def build_features(matches, window=5):
    """各試合日の開始前までの情報だけを使用して特徴量を生成する。"""
    df = matches.sort_values(
        ["Date", "HomeTeam", "AwayTeam"], kind="stable"
    ).reset_index(drop=True).copy()
    history = {}
    rows = []

    # 過去CSVにはキックオフ時刻がないため、同日の全試合について
    # 特徴量を先に作成し、その後で結果を履歴へ一括反映する。
    for _, daily_matches in df.groupby("Date", sort=True):
        pending_history = []

        for _, m in daily_matches.iterrows():
            h, a = m.HomeTeam, m.AwayTeam
            hh, ah = history.get(h, []), history.get(a, [])

            def agg(hist):
                recent = hist[-window:]
                if not recent:
                    return dict(
                        points=0, gf=0, ga=0, shots=0, sot=0,
                        days=14, played=0,
                    )
                def mean_available(key):
                    values = pd.to_numeric(
                        pd.Series([x[key] for x in recent]), errors="coerce"
                    )
                    return float(values.mean()) if values.notna().any() else np.nan

                return dict(
                    points=mean_available("points"),
                    gf=mean_available("gf"),
                    ga=mean_available("ga"),
                    shots=mean_available("shots"),
                    sot=mean_available("sot"),
                    days=max(1, (m.Date - recent[-1]["date"]).days),
                    played=len(recent),
                )

            H, A = agg(hh), agg(ah)
            row = {
                "Date": m.Date,
                "HomeTeam": h,
                "AwayTeam": a,
                "target": TARGET_MAP[m.FTR],
                "home_recent_points": H["points"],
                "away_recent_points": A["points"],
                "recent_points_diff": H["points"] - A["points"],
                "home_recent_gf": H["gf"],
                "away_recent_gf": A["gf"],
                "recent_gf_diff": H["gf"] - A["gf"],
                "home_recent_ga": H["ga"],
                "away_recent_ga": A["ga"],
                "recent_ga_diff": H["ga"] - A["ga"],
                "home_recent_shots": H["shots"],
                "away_recent_shots": A["shots"],
                "home_recent_sot": H["sot"],
                "away_recent_sot": A["sot"],
                "home_days_rest": H["days"],
                "away_days_rest": A["days"],
                "rest_days_diff": H["days"] - A["days"],
                "home_history_count": H["played"],
                "away_history_count": A["played"],
            }
            for c in ["B365H", "B365D", "B365A"]:
                row[c] = pd.to_numeric(m.get(c, np.nan), errors="coerce")
            rows.append(row)

            hs = pd.to_numeric(m.get("HS", np.nan), errors="coerce")
            ass = pd.to_numeric(m.get("AS", np.nan), errors="coerce")
            hst = pd.to_numeric(m.get("HST", np.nan), errors="coerce")
            ast = pd.to_numeric(m.get("AST", np.nan), errors="coerce")

            pending_history.extend([
                (
                    h,
                    {
                        "date": m.Date,
                        "points": _points(m.FTR, "home"),
                        "gf": m.FTHG,
                        "ga": m.FTAG,
                        "shots": hs,
                        "sot": hst,
                    },
                ),
                (
                    a,
                    {
                        "date": m.Date,
                        "points": _points(m.FTR, "away"),
                        "gf": m.FTAG,
                        "ga": m.FTHG,
                        "shots": ass,
                        "sot": ast,
                    },
                ),
            ])

        for team, result in pending_history:
            history.setdefault(team, []).append(result)

    out = pd.DataFrame(rows)
    out = out[
        (out.home_history_count >= window)
        & (out.away_history_count >= window)
    ].reset_index(drop=True)
    return out

def feature_columns(df):
    excluded={'Date','HomeTeam','AwayTeam','target'}
    return [c for c in df.columns if c not in excluded]
