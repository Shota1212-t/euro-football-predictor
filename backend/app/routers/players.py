"""選手一覧・選手詳細 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import data_store as ds

router = APIRouter(prefix="/api/v1/players", tags=["players"])

VALID_LEAGUES = {"pl", "laliga", "seriea", "bundesliga", "ligue1"}
VALID_VERIFICATION = {"verified", "provisional", "all"}


def _is_verified(player: dict) -> bool:
    return player.get("roster_verified") is True


def _public_player(player: dict) -> dict:
    """成績未取得の0を実績値として公開しない。"""
    result = dict(player)
    result["roster_status"] = "verified" if _is_verified(player) else "provisional"

    if not result.get("statistics_available", False):
        for field in (
            "appearances",
            "goals",
            "assists",
            "yellow_cards",
            "red_cards",
            "league_rank",
            "team_rank",
        ):
            result[field] = None

    return result


@router.get("")
def list_players(
    league_id: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
    position: str | None = Query(default=None),
    search: str | None = Query(default=None),
    verification: str = Query(default="all"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    if league_id is not None and league_id not in VALID_LEAGUES:
        raise HTTPException(400, "league_idが不正です。")
    if verification not in VALID_VERIFICATION:
        raise HTTPException(400, "verificationが不正です。")

    players = list(ds.get_players().values())

    if league_id is not None:
        players = [item for item in players if item.get("league_id") == league_id]
    if team_id is not None:
        players = [item for item in players if item.get("team_id") == team_id]
    if position:
        position_key = position.casefold()
        players = [
            item
            for item in players
            if position_key in str(item.get("position") or "").casefold()
        ]
    if search:
        search_key = search.casefold().strip()
        players = [
            item
            for item in players
            if search_key in str(item.get("name") or "").casefold()
        ]
    if verification == "verified":
        players = [item for item in players if _is_verified(item)]
    elif verification == "provisional":
        players = [item for item in players if not _is_verified(item)]

    players.sort(
        key=lambda item: (
            item.get("league_id") or "",
            item.get("team_id") or "",
            item.get("name") or "",
        )
    )

    total = len(players)
    page = []
    for item in players[offset : offset + limit]:
        public_player = _public_player(item)
        team = ds.get_team(item.get("team_id"))
        page.append(
            {
                **public_player,
                "team_name": (team or {}).get("name"),
                "team_logo_url": (team or {}).get("logo_url"),
            }
        )

    return {
        "items": page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "league_id": league_id,
            "team_id": team_id,
            "position": position,
            "search": search,
            "verification": verification,
        },
    }


@router.get("/{player_id}")
def get_player(player_id: str):
    player = ds.get_player(player_id)
    if not player:
        raise HTTPException(404, "指定された選手が見つかりません。")

    team = ds.get_team(player["team_id"])
    next_match = next(
        (
            match
            for match in ds.get_predictions()
            if match["home_team"]["id"] == player["team_id"]
            or match["away_team"]["id"] == player["team_id"]
        ),
        None,
    )

    return {
        "player": _public_player(player),
        "team": team,
        "next_match": next_match,
        "data_notice": (
            "現所属確認済み。成績統計は未取得です。"
            if _is_verified(player)
            else "所属は暫定情報です。成績統計は未取得です。"
        ),
    }
