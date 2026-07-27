"""試合予測一覧・詳細（UI設計書 7〜9章）。"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from .. import data_store as ds

router = APIRouter(prefix="/api/v1/matches", tags=["matches"])


@router.get("")
def list_matches(
    league: Optional[str] = Query(None, description="league_id で絞り込み"),
    team: Optional[str] = Query(None, description="team_id またはチーム名の一部"),
    confidence: Optional[str] = Query(None, description="High / Medium / Low"),
    date: Optional[str] = Query(None, description="YYYY-MM-DD 前方一致"),
):
    matches = ds.get_predictions()
    if league:
        matches = [m for m in matches if m["league_id"] == league]
    if confidence:
        matches = [m for m in matches if m["confidence"].lower() == confidence.lower()]
    if date:
        matches = [m for m in matches if m["kickoff"].startswith(date)]
    if team:
        needle = team.lower()
        matches = [
            m for m in matches
            if needle in m["home_team"]["id"].lower()
            or needle in m["away_team"]["id"].lower()
            or needle in m["home_team"]["name"].lower()
            or needle in m["away_team"]["name"].lower()
        ]
    return matches


@router.get("/{match_id}")
def get_match(match_id: str):
    match = ds.get_prediction(match_id)
    if not match:
        raise HTTPException(404, "指定された試合予測が見つかりません。")
    return match
