"""デモデータ生成スクリプト。

目的：
  1) 実データ取得（あなたが実装する部分）が終わっていなくても、
     フロントエンド／バックエンドをすぐに動かして確認できるようにする。
  2) data/processed, data/predictions 配下に置くべき JSON の
     「形」の実例として使う（実データ取り込みスクリプトはこれと同じキーで
     ファイルを書き出せばよい）。

実行方法：
    python scripts/generate_demo_data.py

実データが揃ったら、このスクリプトが生成したファイルを
あなたの取得・加工スクリプトの出力で上書きすればよい
（ファイルパス・キー名を変えなければ、API・フロントエンドの改修は不要）。
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
PREDICTIONS = DATA / "predictions"

NOW = datetime.now(timezone.utc)


def w(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", path.relative_to(ROOT))


LEAGUES = [
    {"id": "pl", "name": "Premier League", "country": "England", "season": "2025/2026"},
    {"id": "laliga", "name": "La Liga", "country": "Spain", "season": "2025/2026"},
    {"id": "seriea", "name": "Serie A", "country": "Italy", "season": "2025/2026"},
    {"id": "bundesliga", "name": "Bundesliga", "country": "Germany", "season": "2025/2026"},
    {"id": "ligue1", "name": "Ligue 1", "country": "France", "season": "2025/2026"},
]

# league_id -> [(team_id, name, short, color, stadium), ...]
TEAMS_BY_LEAGUE = {
    "pl": [
        ("arsenal", "Arsenal", "ARS", "#EF0107", "Emirates Stadium"),
        ("man-city", "Manchester City", "MCI", "#6CABDD", "Etihad Stadium"),
        ("liverpool", "Liverpool", "LIV", "#C8102E", "Anfield"),
        ("aston-villa", "Aston Villa", "AVL", "#670E36", "Villa Park"),
        ("tottenham", "Tottenham", "TOT", "#132257", "Tottenham Hotspur Stadium"),
        ("newcastle", "Newcastle United", "NEW", "#241F20", "St James' Park"),
        ("chelsea", "Chelsea", "CHE", "#034694", "Stamford Bridge"),
        ("man-utd", "Manchester United", "MUN", "#DA291C", "Old Trafford"),
    ],
    "laliga": [
        ("real-madrid", "Real Madrid", "RMA", "#FEBE10", "Santiago Bernabeu"),
        ("barcelona", "Barcelona", "BAR", "#A50044", "Spotify Camp Nou"),
        ("atletico", "Atletico Madrid", "ATM", "#CB3524", "Civitas Metropolitano"),
        ("girona", "Girona", "GIR", "#CD2534", "Estadi Montilivi"),
        ("athletic", "Athletic Bilbao", "ATH", "#EE2523", "San Mames"),
        ("sociedad", "Real Sociedad", "RSO", "#0067B1", "Reale Arena"),
    ],
    "seriea": [
        ("inter", "Inter", "INT", "#1E3E7C", "San Siro"),
        ("ac-milan", "AC Milan", "MIL", "#FB090B", "San Siro"),
        ("juventus", "Juventus", "JUV", "#000000", "Allianz Stadium"),
        ("napoli", "Napoli", "NAP", "#12A0D7", "Diego Armando Maradona"),
        ("roma", "Roma", "ROM", "#8E1F2F", "Stadio Olimpico"),
        ("atalanta", "Atalanta", "ATA", "#1E71B8", "Gewiss Stadium"),
    ],
    "bundesliga": [
        ("bayern", "Bayern Munchen", "BAY", "#DC052D", "Allianz Arena"),
        ("dortmund", "Borussia Dortmund", "BVB", "#FDE100", "Signal Iduna Park"),
        ("leverkusen", "Bayer Leverkusen", "B04", "#E32221", "BayArena"),
        ("leipzig", "RB Leipzig", "RBL", "#DD0741", "Red Bull Arena"),
        ("stuttgart", "VfB Stuttgart", "VFB", "#E32219", "MHPArena"),
    ],
    "ligue1": [
        ("psg", "PSG", "PSG", "#004170", "Parc des Princes"),
        ("marseille", "Marseille", "OM", "#2FAEE0", "Orange Velodrome"),
        ("monaco", "Monaco", "ASM", "#E32118", "Stade Louis II"),
        ("lille", "Lille", "LOSC", "#C60C30", "Stade Pierre-Mauroy"),
        ("lyon", "Lyon", "OL", "#004A99", "Groupama Stadium"),
    ],
}

MANAGERS = {
    "arsenal": ("mikel-arteta", "Mikel Arteta", "Spain", 43, "2019-12-20"),
    "man-city": ("pep-guardiola", "Pep Guardiola", "Spain", 54, "2016-07-01"),
    "liverpool": ("arne-slot", "Arne Slot", "Netherlands", 46, "2024-06-01"),
    "real-madrid": ("carlo-ancelotti", "Carlo Ancelotti", "Italy", 66, "2021-06-01"),
    "barcelona": ("hansi-flick", "Hansi Flick", "Germany", 59, "2024-05-01"),
    "inter": ("simone-inzaghi", "Simone Inzaghi", "Italy", 49, "2021-06-01"),
    "bayern": ("vincent-kompany", "Vincent Kompany", "Belgium", 39, "2024-06-01"),
    "psg": ("luis-enrique", "Luis Enrique", "Spain", 55, "2023-07-01"),
    "chelsea": ("enzo-maresca", "Enzo Maresca", "Italy", 45, "2024-06-01"),
    "man-utd": ("ruben-amorim", "Ruben Amorim", "Portugal", 40, "2024-11-11"),
}

STAR_PLAYERS = {
    # team_id: [(player_id, name, position, nat, age, number, apps, goals, assists, yellow, red)]
    "man-city": [("e-haaland", "E. Haaland", "FW", "Norway", 25, 9, 37, 27, 5, 2, 0)],
    "liverpool": [("m-salah", "M. Salah", "FW", "Egypt", 33, 11, 38, 25, 12, 1, 0)],
    "newcastle": [("a-isak", "A. Isak", "FW", "Sweden", 26, 14, 34, 21, 4, 3, 0)],
    "chelsea": [("c-palmer", "C. Palmer", "MF", "England", 24, 20, 36, 17, 9, 4, 0)],
    "aston-villa": [("o-watkins", "O. Watkins", "FW", "England", 29, 11, 37, 15, 6, 2, 0)],
    "real-madrid": [("k-mbappe", "K. Mbappe", "FW", "France", 27, 9, 34, 28, 6, 3, 0)],
    "barcelona": [("r-lewandowski", "R. Lewandowski", "FW", "Poland", 37, 9, 33, 24, 5, 1, 0)],
    "bayern": [("h-kane", "H. Kane", "FW", "England", 32, 9, 32, 30, 7, 2, 0)],
    "psg": [("o-dembele", "O. Dembele", "FW", "France", 28, 10, 30, 22, 8, 3, 0)],
    "inter": [("l-martinez", "L. Martinez", "FW", "Argentina", 27, 10, 31, 19, 5, 4, 0)],
}


def build_teams_and_players():
    teams: dict[str, dict] = {}
    players: dict[str, dict] = {}
    managers: dict[str, dict] = {}

    for league_id, rows in TEAMS_BY_LEAGUE.items():
        for team_id, name, short, color, stadium in rows:
            manager_id = None
            if team_id in MANAGERS:
                mid, mname, mnat, mage, appointed = MANAGERS[team_id]
                manager_id = mid
                managers[mid] = {
                    "id": mid,
                    "name": mname,
                    "team_id": team_id,
                    "nationality": mnat,
                    "age": mage,
                    "appointed": appointed,
                    "photo_url": None,
                    "matches": 58,
                    "wins": 38,
                    "draws": 11,
                    "losses": 9,
                    "avg_goals_for": 2.1,
                    "avg_goals_against": 0.9,
                    "recent_form": "WWWWD",
                }
            teams[team_id] = {
                "id": team_id,
                "name": name,
                "short": short,
                "league_id": league_id,
                "country": next(l["country"] for l in LEAGUES if l["id"] == league_id),
                "stadium": stadium,
                "manager_id": manager_id,
                "logo_url": None,
                "color": color,
            }
            for i, p in enumerate(STAR_PLAYERS.get(team_id, [])):
                pid, pname, pos, nat, age, num, apps, goals, assists, yellow, red = p
                players[pid] = {
                    "id": pid,
                    "name": pname,
                    "team_id": team_id,
                    "league_id": league_id,
                    "position": pos,
                    "nationality": nat,
                    "age": age,
                    "shirt_number": num,
                    "photo_url": None,
                    "appearances": apps,
                    "goals": goals,
                    "assists": assists,
                    "yellow_cards": yellow,
                    "red_cards": red,
                    "league_rank": i + 1,
                    "team_rank": 1,
                }
    return teams, players, managers


def build_standings(teams: dict[str, dict]):
    import random
    random.seed(42)
    for league in LEAGUES:
        league_id = league["id"]
        team_rows = [t for t in teams.values() if t["league_id"] == league_id]
        rows = []
        for t in team_rows:
            played = 38 if league_id == "pl" else 34
            win = random.randint(14, 28)
            loss = random.randint(3, 12)
            draw = max(0, played - win - loss)
            gf = win * random.randint(2, 3) + draw
            ga = loss * random.randint(1, 2) + draw // 2
            rows.append({
                "team_id": t["id"],
                "team_name": t["name"],
                "played": played,
                "win": win,
                "draw": draw,
                "loss": loss,
                "goals_for": gf,
                "goals_against": ga,
                "points": win * 3 + draw,
                "recent_form": "".join(random.choice(["W", "W", "D", "L"]) for _ in range(5)),
            })
        rows.sort(key=lambda r: (-r["points"], -(r["goals_for"] - r["goals_against"])))
        payload = {
            "total": rows,
            "home": rows,   # 参考値。実データ取り込み時はホーム/アウェイ別に分けて上書きしてください
            "away": rows,
            "last5": rows,
        }
        w(PROCESSED / "standings" / f"{league_id}.json", payload)


def build_rankings(players: dict[str, dict]):
    for league in LEAGUES:
        league_id = league["id"]
        league_players = [p for p in players.values() if p["league_id"] == league_id]

        def rows(key):
            ranked = sorted(league_players, key=lambda p: -p[key])
            return [
                {
                    "player_id": p["id"],
                    "player_name": p["name"],
                    "team_id": p["team_id"],
                    "team_name": next(
                        t["name"] for t in teams.values() if t["id"] == p["team_id"]
                    ),
                    "position": p["position"],
                    "value": p[key],
                }
                for p in ranked
            ]

        payload = {
            "goals": rows("goals"),
            "assists": rows("assists"),
            "appearances": rows("appearances"),
            "yellow_cards": rows("yellow_cards"),
            "red_cards": rows("red_cards"),
        }
        w(PROCESSED / "rankings" / f"{league_id}.json", payload)


def build_predictions(teams: dict[str, dict]):
    fixtures = [
        ("pl", "arsenal", "chelsea", 52, 25, 23, 42, 68),
        ("laliga", "real-madrid", "barcelona", 47, 27, 26, 35, 54),
        ("seriea", "inter", "ac-milan", 50, 25, 25, 48, 51),
        ("bundesliga", "bayern", "dortmund", 60, 20, 20, 31, 69),
        ("ligue1", "psg", "marseille", 65, 20, 15, 44, 72),
    ]
    predictions = []
    for i, (league_id, home_id, away_id, hp, dp, ap, hf, af) in enumerate(fixtures):
        home = teams[home_id]
        away = teams[away_id]
        kickoff = (NOW + timedelta(days=i + 1)).replace(hour=20, minute=0, second=0, microsecond=0)
        gap = max(hp, dp, ap) - sorted([hp, dp, ap])[-2]
        confidence = "High" if gap >= 20 else "Medium" if gap >= 10 else "Low"
        predicted = "Home Win" if hp >= max(dp, ap) else ("Draw" if dp >= ap else "Away Win")

        def fatigue_detail(idx):
            level = "Low" if idx < 40 else "Medium" if idx < 70 else "High"
            return {
                "index": idx,
                "level": level,
                "matches_last_7d": 1 if idx < 50 else 2,
                "matches_last_14d": 2 if idx < 50 else 4,
                "days_since_last_match": 7 if idx < 50 else 3,
                "after_european_competition": idx >= 60,
                "after_domestic_cup": False,
                "had_extra_time_or_penalties": False,
            }

        predictions.append({
            "id": f"m-{league_id}-{i + 1:03d}",
            "league_id": league_id,
            "league_name": next(l["name"] for l in LEAGUES if l["id"] == league_id),
            "kickoff": kickoff.isoformat(),
            "home_team": {"id": home["id"], "name": home["name"], "short": home["short"],
                          "league_id": league_id, "color": home["color"]},
            "away_team": {"id": away["id"], "name": away["name"], "short": away["short"],
                          "league_id": league_id, "color": away["color"]},
            "home_win_probability": hp,
            "draw_probability": dp,
            "away_win_probability": ap,
            "predicted_result": predicted,
            "confidence": confidence,
            "home_fatigue": fatigue_detail(hf),
            "away_fatigue": fatigue_detail(af),
            "comparison": [
                {"label": "順位", "home_value": "1", "away_value": "3"},
                {"label": "勝ち点", "home_value": "87", "away_value": "74"},
                {"label": "平均得点", "home_value": "2.3", "away_value": "1.4"},
                {"label": "平均失点", "home_value": "0.7", "away_value": "1.1"},
                {"label": "直近5試合", "home_value": "WWWWD", "away_value": "WLDWL"},
            ],
            "reasons": [
                f"{home['name']}は直近5試合で4勝1分0敗",
                f"{away['name']}は直近14日間で4試合を消化",
                f"{home['name']}のホーム平均得点は2.3",
                f"{away['name']}の疲労指数は{af}/100",
                "直近5回の対戦は2勝2分1敗",
            ],
            "h2h_summary": "直近5回の対戦はホームチームが2勝2分1敗",
            "odds": {"home": 1.85, "draw": 3.6, "away": 4.2},
            "model_version": "v1.2-demo",
        })
    w(PREDICTIONS / "matches.json", predictions)


def build_model_performance():
    w(PREDICTIONS / "model_performance.json", {
        "model_version": "v1.2-demo",
        "overall_accuracy": 48.2,
        "total_predictions": 1248,
        "correct_predictions": 601,
        "last_30_days_accuracy": 50.4,
        "last_100_matches_accuracy": 49.1,
        "home_win_accuracy": 55.2,
        "draw_accuracy": 24.8,
        "away_win_accuracy": 44.6,
        "brier_score": 0.612,
        "log_loss": 1.024,
        "by_league": [
            {"league_name": "Premier League", "accuracy": 51.0},
            {"league_name": "La Liga", "accuracy": 46.8},
            {"league_name": "Serie A", "accuracy": 47.5},
            {"league_name": "Bundesliga", "accuracy": 49.1},
            {"league_name": "Ligue 1", "accuracy": 45.9},
        ],
    })


def build_data_status():
    ts = NOW.strftime("%Y-%m-%dT%H:%M:%S")
    w(DATA / "data_status.json", [
        {"source": "football-data.org", "data_type": "Matches / Standings", "last_updated": ts,
         "records": "248", "status": "Success", "next_update": "翌日 09:00"},
        {"source": "Football-Data.co.uk", "data_type": "Historical Results / Odds", "last_updated": ts,
         "records": "31 seasons", "status": "Success", "next_update": "週次"},
        {"source": "API-FOOTBALL", "data_type": "Additional Fixtures", "last_updated": ts,
         "records": "84", "status": "Warning", "error": "レート制限に近づいています", "next_update": "翌日 07:45"},
        {"source": "TheSportsDB", "data_type": "Team / Player Images", "last_updated": ts,
         "records": "1,024", "status": "Success", "next_update": "週次"},
        {"source": "OpenFootball", "data_type": "Master Data", "last_updated": ts,
         "records": "5 leagues", "status": "Success", "next_update": "月次"},
        {"source": "OpenLigaDB", "data_type": "Bundesliga Supplement", "last_updated": ts,
         "records": "306", "status": "Success", "next_update": "翌日 09:00"},
        {"source": "StatsBomb Open Data", "data_type": "Event Analysis Demo", "last_updated": ts,
         "records": "Demo", "status": "Success", "next_update": "-"},
    ])


def build_data_sources():
    w(DATA / "data_sources.json", [
        {"name": "football-data.org", "purpose": "現在の試合日程・順位表",
         "data_fetched": "fixtures, standings", "update_frequency": "毎日",
         "notes": "無料枠はリクエスト数に制限あり。API keyは.envで管理。"},
        {"name": "Football-Data.co.uk", "purpose": "過去の試合結果・オッズ・スタッツ（モデル学習用）",
         "data_fetched": "historical results, odds", "update_frequency": "シーズン中は週次",
         "notes": "CSV配布。ml/data_loader.pyが読み込む。"},
        {"name": "API-FOOTBALL", "purpose": "追加の日程・国内カップ・欧州大会補完",
         "data_fetched": "fixtures (cup/european)", "update_frequency": "毎日",
         "notes": "疲労指数の算出に必要な直近試合数の補完に使用。"},
        {"name": "TheSportsDB", "purpose": "チームロゴ・選手画像・プロフィール",
         "data_fetched": "logos, photos, profiles", "update_frequency": "週次",
         "notes": "画像が取得できない場合はイニシャル表示にフォールバック。"},
        {"name": "OpenFootball", "purpose": "チーム名・リーグ名のマスタ正規化",
         "data_fetched": "master data", "update_frequency": "月次", "notes": None},
        {"name": "OpenLigaDB", "purpose": "ブンデスリーガ系データの補完",
         "data_fetched": "Bundesliga results", "update_frequency": "毎日", "notes": None},
        {"name": "StatsBomb Open Data", "purpose": "xGなどイベント分析のデモ用",
         "data_fetched": "event data (一部大会のみ)", "update_frequency": "-",
         "notes": "無料公開分のみ。本番運用には別途契約が必要。"},
    ])


if __name__ == "__main__":
    w(PROCESSED / "leagues.json", LEAGUES)
    teams, players, managers = build_teams_and_players()
    w(PROCESSED / "teams.json", teams)
    w(PROCESSED / "players.json", players)
    w(PROCESSED / "managers.json", managers)
    build_standings(teams)
    build_rankings(players)
    build_predictions(teams)
    build_model_performance()
    build_data_status()
    build_data_sources()
    print("\nデモデータの生成が完了しました。 backend を起動して /docs で確認できます。")
