export interface League { id: string; name: string; country?: string; season?: string; }

export interface Team {
  id: string; api_id?: number; thesportsdb_id?: string; name: string; short: string;
  league_id: string; country?: string; stadium?: string | null; manager_id?: string | null;
  logo_url?: string | null; color?: string; website?: string | null;
  founded?: number | null; club_colors?: string | null;
}

export interface TeamListItem extends Team {
  standing_position?: number | null;
  standing_points?: number | null;
  standing_played?: number | null;
  manager_name?: string | null;
  has_manager: boolean;
}

export interface TeamListResponse {
  items: TeamListItem[]; total: number; limit: number; offset: number;
  filters: { league_id?: string | null; search?: string | null; };
}

export interface Player {
  id: string; name: string; team_id: string; league_id: string; 
  team_name?: string | null;
  team_logo_url?: string | null;
  position?: string | null; nationality?: string | null; date_of_birth?: string | null;
  age?: number | null; shirt_number?: number | null; photo_url?: string | null;
  cutout_url?: string | null; height?: string | null; weight?: string | null;
  description_ja?: string | null; description_en?: string | null;
  appearances?: number | null; goals?: number | null; assists?: number | null;
  yellow_cards?: number | null; red_cards?: number | null;
  league_rank?: number | null; team_rank?: number | null;
  statistics_available?: boolean; roster_verified?: boolean;
  roster_status?: 'verified' | 'provisional'; roster_verification_reason?: string | null;
  profile_matched?: boolean; data_source?: string;
}

export interface PlayerListResponse {
  items: Player[]; total: number; limit: number; offset: number;
  filters: {
    league_id?: string | null; team_id?: string | null; position?: string | null;
    search?: string | null; verification?: 'verified' | 'provisional' | 'all';
  };
}

export interface Manager {
  id: string;
  name: string;
  team_id: string;
  league_id?: string | null;

  team_name?: string | null;
  team_logo_url?: string | null;

  football_data_coach_id?: number | null;
  thesportsdb_id?: string | null;

  nationality?: string | null;
  date_of_birth?: string | null;
  age?: number | null;
  appointed?: string | null;
  contract_until?: string | null;
  photo_url?: string | null;

  matches?: number | null;
  wins?: number | null;
  draws?: number | null;
  losses?: number | null;
  avg_goals_for?: number | null;
  avg_goals_against?: number | null;
  recent_form?: string | null;

  role?: string | null;
  data_source?: string;
  statistics_available?: boolean;

  employment_verified?: boolean;
  employment_status?: 'verified' | 'provisional';
  verification_source?: string | null;
  verified_at?: string | null;
  last_checked_at?: string | null;
  verification_note?: string | null;

  description_ja?: string | null;
  description_en?: string | null;
}

export interface ManagerListResponse {
  items: Manager[]; total: number; limit: number; offset: number;
  filters: { league_id?: string | null; team_id?: string | null; role?: string | null; search?: string | null; };
}

export interface StandingRow {
  team_id: string;
  api_id?: number;
  team_name: string;
  team_logo_url?: string | null;
  position?: number;
  played: number;
  win: number;
  draw: number;
  loss: number;
  goals_for: number;
  goals_against: number;
  points: number;
  recent_form: string;
}
export interface RankingRow {
  player_id: string | null;
  football_data_player_id?: number | null;
  player_name: string;
  team_id: string | null;
  football_data_team_id?: number | null;
  team_name: string;
  team_logo_url?: string | null;
  position?: string | null;
  nationality?: string | null;
  value: number;
}
export interface RankingMetadata {
  league_id?: string; competition_code?: string; competition_name?: string | null;
  season_id?: number | null; season_start?: string | null; season_end?: string | null;
  current_matchday?: number | null; source?: string; updated_at?: string;
  state?: 'available' | 'preseason' | 'empty' | 'not_generated'; message?: string | null;
  available_types?: string[]; unavailable_types?: string[];
}
export interface RankingResponse {
  items: RankingRow[]; type: string;
  state: 'available' | 'preseason' | 'empty' | 'not_generated' | 'unavailable';
  message?: string | null; metadata: RankingMetadata;
}

export interface FatigueDetail {
  index: number;
  level: 'Low' | 'Medium' | 'High';
  matches_last_7d: number;
  matches_last_14d: number;
  days_since_last_match?: number;

  after_european_competition: boolean;
  after_domestic_cup: boolean;
  had_extra_time_or_penalties: boolean;

  extra_matches_last_7d?: number;
  extra_matches_last_14d?: number;
  last_extra_competition?: string | null;
  last_extra_match_source?: string | null;

  european_competition_data_status?:
    | 'available'
    | 'partial'
    | 'partial_last_event_only'
    | 'not_available'
    | 'unknown';

  domestic_cup_data_status?:
    | 'available'
    | 'partial'
    | 'partial_last_event_only'
    | 'not_available'
    | 'unknown';

  extra_time_data_status?:
    | 'available'
    | 'partial'
    | 'partial_last_event_only'
    | 'not_available'
    | 'unknown';

  official_matches_data_completeness?:
    | 'league_only'
    | 'league_and_champions_league_with_partial_cup_supplement';
}
export interface TeamComparisonRow { label: string; home_value: string; away_value: string; }
export interface ShapExplanation {
  feature: string; label: string; value: number | null; shap_value: number;
  impact: 'supports' | 'opposes'; target: string; text: string;
}
export interface MatchPrediction {
  id: string; league_id: string; league_name: string; kickoff: string;
  home_team: Team; away_team: Team; home_win_probability: number;
  draw_probability: number; away_win_probability: number; predicted_result: string;
  confidence: 'High' | 'Medium' | 'Low';
  data_quality?: 'full_history' | 'second_division_history' | 'estimated';
  home_fatigue: FatigueDetail; away_fatigue: FatigueDetail;
  comparison: TeamComparisonRow[]; reasons: string[];
  explanations?: ShapExplanation[]; explanation_method?: string | null;
  explanation_note?: string | null; h2h_summary?: string | null;
  odds?: { home: number; draw: number; away: number } | null; model_version?: string;
}

export interface LeaguePerformance { league_name: string; accuracy: number; }
export interface ClassPerformance {
  precision?: number;
  recall?: number;
  'f1-score'?: number;
  support?: number;
}

export interface ModelPerformance {
  model_name: string;
  model_version: string;
  trained_at?: string | null;
  production_variant?: string | null;
  production_calibration?: string | null;
  selection_reason?: string | null;
  class_weight?: string | null;
  features: string[];
  feature_count: number;
  excluded_features: string[];
  train_end?: string | null;
  validation_start?: string | null;
  test_start?: string | null;
  evaluation_type?: string;
  overall_accuracy: number;
  macro_f1?: number | null;
  log_loss?: number | null;
  brier_score?: number | null;
  expected_calibration_error?: number | null;
  draw_precision?: number | null;
  draw_recall?: number | null;
  draw_f1?: number | null;
  confusion_matrix: number[][];
  class_metrics: {
    home_win: ClassPerformance;
    draw: ClassPerformance;
    away_win: ClassPerformance;
  };
  total_predictions: number;
  correct_predictions: number;
  by_league: LeaguePerformance[];
  operational_results_available: boolean;
  operational_note?: string | null;
  probability_note?: string | null;
}
export interface DataStatusItem {
  source: string; data_type: string; last_updated: string | null; records: string;
  status: 'Success' | 'Warning' | 'Failed' | 'Running' | 'Not configured' | 'Not implemented';
  error?: string | null; next_update?: string | null; is_stale?: boolean;
}
export interface DataSourceItem { name: string; purpose: string; data_fetched: string; update_frequency: string; notes?: string; }
export interface TeamDetail { team: Team; manager: Manager | null; players: Player[]; upcoming_matches: MatchPrediction[]; standing: StandingRow | null; }
export interface PlayerDetail { player: Player; team: Team | null; next_match: MatchPrediction | null; data_notice?: string; }
export interface ManagerDetail { manager: Manager; team: Team | null; next_match: MatchPrediction | null; data_notice?: string | null; }
export interface DashboardData {
  featured_matches: MatchPrediction[]; model_performance: ModelPerformance | null;
  data_status: DataStatusItem[]; standings_summary: Record<string, StandingRow[]>;
  rankings_summary: Record<string, RankingRow[]>;
}
