"""API 全体で使う Pydantic モデル。
UI設計書（1〜21節）の各ページが必要とする項目をそのままフィールドにしている。
実データ取り込みスクリプトは、ここに定義した形と同じキーで
data/processed 配下・data/predictions 配下の JSON を書き出せばよい。
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class Team(BaseModel):
    id: str
    name: str
    short: str
    league_id: str
    country: Optional[str] = None
    stadium: Optional[str] = None
    manager_id: Optional[str] = None
    logo_url: Optional[str] = None
    color: Optional[str] = "#334155"


class Player(BaseModel):
    id: str
    name: str
    team_id: str
    league_id: str
    position: Optional[str] = None
    nationality: Optional[str] = None
    age: Optional[int] = None
    shirt_number: Optional[int] = None
    photo_url: Optional[str] = None
    appearances: int = 0
    goals: int = 0
    assists: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    league_rank: Optional[int] = None
    team_rank: Optional[int] = None


class Manager(BaseModel):
    id: str
    name: str
    team_id: str
    nationality: Optional[str] = None
    age: Optional[int] = None
    appointed: Optional[str] = None
    photo_url: Optional[str] = None
    matches: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    avg_goals_for: Optional[float] = None
    avg_goals_against: Optional[float] = None
    recent_form: Optional[str] = None


class League(BaseModel):
    id: str
    name: str
    country: Optional[str] = None
    season: Optional[str] = "2025/2026"


class StandingRow(BaseModel):
    team_id: str
    team_name: str
    played: int
    win: int
    draw: int
    loss: int
    goals_for: int
    goals_against: int
    points: int
    recent_form: str = ""


class RankingRow(BaseModel):
    player_id: str
    player_name: str
    team_id: str
    team_name: str
    position: Optional[str] = None
    value: float


class FatigueDetail(BaseModel):
    index: int
    level: str  # Low / Medium / High
    matches_last_7d: int = 0
    matches_last_14d: int = 0
    days_since_last_match: Optional[int] = None
    after_european_competition: bool = False
    after_domestic_cup: bool = False
    had_extra_time_or_penalties: bool = False


class TeamComparisonRow(BaseModel):
    label: str
    home_value: str
    away_value: str


class MatchPrediction(BaseModel):
    id: str
    league_id: str
    league_name: str
    kickoff: str
    home_team: Team
    away_team: Team
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    predicted_result: str
    confidence: str  # High / Medium / Low
    home_fatigue: FatigueDetail
    away_fatigue: FatigueDetail
    comparison: list[TeamComparisonRow] = []
    reasons: list[str] = []
    h2h_summary: Optional[str] = None
    odds: Optional[dict] = None
    model_version: Optional[str] = None


class LeaguePerformance(BaseModel):
    league_name: str
    accuracy: float


class ModelPerformance(BaseModel):
    model_version: str
    overall_accuracy: float
    total_predictions: int
    correct_predictions: int
    last_30_days_accuracy: Optional[float] = None
    last_100_matches_accuracy: Optional[float] = None
    home_win_accuracy: Optional[float] = None
    draw_accuracy: Optional[float] = None
    away_win_accuracy: Optional[float] = None
    brier_score: Optional[float] = None
    log_loss: Optional[float] = None
    by_league: list[LeaguePerformance] = []


class DataStatusItem(BaseModel):
    source: str
    data_type: str
    last_updated: str
    records: str
    status: str  # Success / Warning / Failed / Running
    error: Optional[str] = None
    next_update: Optional[str] = None


class DataSourceItem(BaseModel):
    name: str
    purpose: str
    data_fetched: str
    update_frequency: str
    notes: Optional[str] = None
