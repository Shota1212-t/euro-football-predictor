"""疲労指数の算出（UI設計書 9章）。

バッチ側（ml/ や scripts/）から呼び出して、試合ごとの疲労指数(0-100)を
計算するための共通ロジック。API側にも同じ判定基準を置いておき、
UIの色分け（Low/Medium/High）がAPIとバッチで食い違わないようにしている。
"""


def fatigue_level(index: int) -> str:
    if index < 40:
        return "Low"
    if index < 70:
        return "Medium"
    return "High"


def compute_fatigue_index(
    matches_last_7d: int,
    matches_last_14d: int,
    days_since_last_match: int | None,
    after_european_competition: bool = False,
    after_domestic_cup: bool = False,
    had_extra_time_or_penalties: bool = False,
) -> int:
    """簡易的な加重スコア。実運用では実データで係数を調整すること。"""
    score = 0
    score += matches_last_7d * 12
    score += matches_last_14d * 5
    if days_since_last_match is not None:
        score += max(0, 10 - days_since_last_match) * 2
    if after_european_competition:
        score += 15
    if after_domestic_cup:
        score += 8
    if had_extra_time_or_penalties:
        score += 10
    return max(0, min(100, score))
