"""監督・スタッフ一覧と監督詳細 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import data_store as ds

router = APIRouter(prefix="/api/v1/managers", tags=["managers"])

VALID_LEAGUES = {"pl", "laliga", "seriea", "bundesliga", "ligue1"}


def _public_manager(manager: dict) -> dict:
    """未取得の監督成績を0として公開しない。"""
    result = dict(manager)
    if not result.get("statistics_available", False):
        for field in (
            "matches",
            "wins",
            "draws",
            "losses",
            "avg_goals_for",
            "avg_goals_against",
            "recent_form",
        ):
            result[field] = None
    return result


@router.get("")
def list_managers(
    league_id: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
    role: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    if league_id is not None and league_id not in VALID_LEAGUES:
        raise HTTPException(400, "league_idが不正です。")

    managers = list(ds.get_managers().values())

    if league_id is not None:
        managers = [
            item
            for item in managers
            if (ds.get_team(item.get("team_id")) or {}).get("league_id")
            == league_id
        ]
    if team_id is not None:
        managers = [item for item in managers if item.get("team_id") == team_id]
    if role:
        role_key = role.casefold().strip()
        managers = [
            item
            for item in managers
            if role_key in str(item.get("role") or "").casefold()
        ]
    if search:
        search_key = search.casefold().strip()
        managers = [
            item
            for item in managers
            if search_key in str(item.get("name") or "").casefold()
        ]

    managers.sort(
        key=lambda item: (
            (ds.get_team(item.get("team_id")) or {}).get("league_id") or "",
            (ds.get_team(item.get("team_id")) or {}).get("name") or "",
            item.get("name") or "",
        )
    )

    total = len(managers)
    items = []
    for manager in managers[offset : offset + limit]:
        public_manager = _public_manager(manager)
        team = ds.get_team(manager.get("team_id"))
        items.append(
            {
                **public_manager,
                "league_id": (team or {}).get("league_id"),
                "team_name": (team or {}).get("name"),
                "team_logo_url": (team or {}).get("logo_url"),
            }
        )

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "league_id": league_id,
            "team_id": team_id,
            "role": role,
            "search": search,
        },
    }


@router.get("/{manager_id}")
def get_manager(manager_id: str):
    manager = ds.get_manager(manager_id)
    if not manager:
        raise HTTPException(404, "指定された監督が見つかりません。")

    team = ds.get_team(manager["team_id"])
    next_match = next(
        (
            match
            for match in ds.get_predictions()
            if match["home_team"]["id"] == manager["team_id"]
            or match["away_team"]["id"] == manager["team_id"]
        ),
        None,
    )

    return {
        "manager": _public_manager(manager),
        "team": team,
        "next_match": next_match,
        "data_notice": (
            "監督プロフィールを取得済みです。成績統計は未取得です。"
            if not manager.get("statistics_available", False)
            else None
        ),
    }
