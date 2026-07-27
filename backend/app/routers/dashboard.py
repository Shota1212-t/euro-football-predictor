"""ダッシュボード（UI設計書 6章）用の集約エンドポイント。"""
from fastapi import APIRouter
from .. import data_store as ds

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("")
def dashboard():
    predictions = ds.get_predictions()[:5]
    performance = ds.get_model_performance()
    status = ds.get_data_status()
    leagues = ds.get_leagues()

    standings_summary = {}
    rankings_summary = {}
    for league in leagues:
        standings_summary[league["id"]] = ds.get_standings(league["id"])[:5]
        rankings_summary[league["id"]] = ds.get_rankings(league["id"], "goals")[:5]

    return {
        "featured_matches": predictions,
        "model_performance": performance,
        "data_status": status,
        "standings_summary": standings_summary,
        "rankings_summary": rankings_summary,
    }
