"""チーム一覧・チーム詳細 API。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import data_store as ds

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])
VALID_LEAGUES = {"pl", "laliga", "seriea", "bundesliga", "ligue1"}


@router.get("")
def list_teams(
    league_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    if league_id is not None and league_id not in VALID_LEAGUES:
        raise HTTPException(400, "league_idが不正です。")

    teams = list(ds.get_teams().values())
    if league_id is not None:
        teams = [team for team in teams if team.get("league_id") == league_id]
    if search:
        key = search.casefold().strip()
        teams = [team for team in teams if key in str(team.get("name") or "").casefold()]

    enriched = []
    for team in teams:
        standings = ds.get_standings(team.get("league_id", ""))
        standing = next(
            (row for row in standings if row.get("team_id") == team.get("id")),
            None,
        )
        manager = (
            ds.get_manager(team["manager_id"])
            if team.get("manager_id")
            else next(
                (
                    item
                    for item in ds.get_managers().values()
                    if item.get("team_id") == team.get("id")
                ),
                None,
            )
        )
        enriched.append(
            {
                **team,
                "standing_position": standing.get("position") if standing else None,
                "standing_points": standing.get("points") if standing else None,
                "standing_played": standing.get("played") if standing else None,
                "manager_name": manager.get("name") if manager else None,
                "has_manager": manager is not None,
            }
        )

    enriched.sort(
        key=lambda team: (
            team.get("league_id") or "",
            team.get("standing_position") if team.get("standing_position") is not None else 999,
            team.get("name") or "",
        )
    )
    total = len(enriched)
    return {
        "items": enriched[offset : offset + limit],
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {"league_id": league_id, "search": search},
    }


@router.get("/{team_id}")
def get_team(team_id: str):
    team = ds.get_team(team_id)
    if not team:
        raise HTTPException(404, "指定されたチームが見つかりません。")
    players = [
        player for player in ds.get_players().values()
        if player.get("team_id") == team_id
    ]
    manager = (
        ds.get_manager(team["manager_id"])
        if team.get("manager_id")
        else next(
            (
                item for item in ds.get_managers().values()
                if item.get("team_id") == team_id
            ),
            None,
        )
    )
    matches = [
        match for match in ds.get_predictions()
        if match["home_team"]["id"] == team_id
        or match["away_team"]["id"] == team_id
    ]
    standings = ds.get_standings(team["league_id"])
    standing_row = next(
        (row for row in standings if row.get("team_id") == team_id),
        None,
    )
    return {
        "team": team,
        "manager": manager,
        "players": players,
        "upcoming_matches": matches,
        "standing": standing_row,
    }
