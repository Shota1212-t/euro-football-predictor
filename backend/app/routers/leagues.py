"""リーグ詳細・順位表・選手ランキング。"""
from fastapi import APIRouter, HTTPException, Query
from .. import data_store as ds

router = APIRouter(prefix="/api/v1/leagues", tags=["leagues"])


@router.get("")
def list_leagues():
    return ds.get_leagues()


@router.get("/{league_id}")
def get_league(league_id: str):
    league = ds.get_league(league_id)
    if not league:
        raise HTTPException(404, "指定されたリーグが見つかりません。")
    return league


@router.get("/{league_id}/standings")
def get_standings(
    league_id: str,
    tab: str = Query("total", pattern="^(total|home|away|last5)$"),
):
    if not ds.get_league(league_id):
        raise HTTPException(404, "指定されたリーグが見つかりません。")
    return ds.get_standings(league_id, tab)


@router.get("/{league_id}/rankings")
def get_rankings(
    league_id: str,
    type: str = Query(
        "goals",
        pattern="^(goals|assists|appearances|yellow_cards|red_cards)$",
    ),
):
    if not ds.get_league(league_id):
        raise HTTPException(404, "指定されたリーグが見つかりません。")

    payload = ds.get_rankings_payload(league_id)
    metadata = payload.get("metadata", {})
    available_types = set(metadata.get("available_types", []))

    if type not in available_types:
        return {
            "items": [],
            "type": type,
            "state": "unavailable",
            "message": "このランキング種別は現在のデータソースでは取得できません。",
            "metadata": metadata,
        }

    items = []
    for item in payload.get(type, []):
        team = ds.get_team(item.get("team_id")) if item.get("team_id") else None
        items.append({**item, "team_logo_url": (team or {}).get("logo_url")})
    return {
        "items": items,
        "type": type,
        "state": metadata.get("state", "not_generated"),
        "message": metadata.get("message"),
        "metadata": metadata,
    }
