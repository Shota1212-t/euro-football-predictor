import type {
  DashboardData, DataSourceItem, DataStatusItem, League, ManagerDetail,
  ManagerListResponse, MatchPrediction, ModelPerformance, PlayerDetail,
  PlayerListResponse, RankingResponse, StandingRow, TeamDetail, TeamListResponse,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
async function apiFetch<T>(path: string): Promise<T | null> {
  try { const res = await fetch(`${API_BASE}${path}`, { cache: 'no-store' }); if (!res.ok) return null; return (await res.json()) as T; }
  catch { return null; }
}
function qs(params: Record<string, string | undefined>): string {
  const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== '');
  return entries.length ? `?${new URLSearchParams(entries as [string, string][]).toString()}` : '';
}
export const api = {
  dashboard: () => apiFetch<DashboardData>('/api/v1/dashboard'),
  matches: (params: { league?: string; team?: string; confidence?: string; date?: string } = {}) => apiFetch<MatchPrediction[]>(`/api/v1/matches${qs(params)}`),
  match: (id: string) => apiFetch<MatchPrediction>(`/api/v1/matches/${id}`),
  leagues: () => apiFetch<League[]>('/api/v1/leagues'),
  standings: (leagueId: string, tab = 'total') => apiFetch<StandingRow[]>(`/api/v1/leagues/${leagueId}/standings${qs({ tab })}`),
  rankings: (leagueId: string, type = 'goals') => apiFetch<RankingResponse>(`/api/v1/leagues/${leagueId}/rankings${qs({ type })}`),
  teams: (params: { league_id?: string; search?: string; limit?: number; offset?: number } = {}) => apiFetch<TeamListResponse>(`/api/v1/teams${qs({ league_id: params.league_id, search: params.search, limit: params.limit?.toString(), offset: params.offset?.toString() })}`),
  team: (id: string) => apiFetch<TeamDetail>(`/api/v1/teams/${id}`),
  players: (params: { league_id?: string; team_id?: string; position?: string; search?: string; verification?: 'verified' | 'provisional' | 'all'; limit?: number; offset?: number } = {}) => apiFetch<PlayerListResponse>(`/api/v1/players${qs({ league_id: params.league_id, team_id: params.team_id, position: params.position, search: params.search, verification: params.verification, limit: params.limit?.toString(), offset: params.offset?.toString() })}`),
  player: (id: string) => apiFetch<PlayerDetail>(`/api/v1/players/${id}`),
  managers: (params: { league_id?: string; team_id?: string; role?: string; search?: string; limit?: number; offset?: number } = {}) => apiFetch<ManagerListResponse>(`/api/v1/managers${qs({ league_id: params.league_id, team_id: params.team_id, role: params.role, search: params.search, limit: params.limit?.toString(), offset: params.offset?.toString() })}`),
  manager: (id: string) => apiFetch<ManagerDetail>(`/api/v1/managers/${id}`),
  modelPerformance: () => apiFetch<ModelPerformance>('/api/v1/model/performance'),
  dataStatus: () => apiFetch<DataStatusItem[]>('/api/v1/data-status'),
  dataSources: () => apiFetch<DataSourceItem[]>('/api/v1/data-sources'),
};
