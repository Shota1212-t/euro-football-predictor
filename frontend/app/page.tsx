import Link from 'next/link';
import { api } from './lib/api';
import {
  EmptyState,
  ErrorState,
  Form,
  Header,
  MatchCard,
  StatusDot,
  TeamCrest,
} from './components/ui';

const percent = (value: number | null | undefined) =>
  value == null ? '—' : `${(value * 100).toFixed(2)}%`;

function displayModelName(version: string): string {
  if (version.includes('lightgbm') && version.includes('no_odds')) {
    return 'LightGBM（オッズなし・未校正）';
  }
  return version;
}

const DASHBOARD_LEAGUES = [
  { id: 'pl', label: 'Premier League' },
  { id: 'laliga', label: 'La Liga' },
  { id: 'seriea', label: 'Serie A' },
  { id: 'bundesliga', label: 'Bundesliga' },
  { id: 'ligue1', label: 'Ligue 1' },
] as const;

type DashboardLeagueId = (typeof DASHBOARD_LEAGUES)[number]['id'];

function isDashboardLeagueId(value?: string): value is DashboardLeagueId {
  return DASHBOARD_LEAGUES.some((league) => league.id === value);
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: { league?: string };
}) {
  const selectedLeagueId: DashboardLeagueId = isDashboardLeagueId(searchParams.league)
    ? searchParams.league
    : 'pl';
  const selectedLeague =
    DASHBOARD_LEAGUES.find((league) => league.id === selectedLeagueId) ??
    DASHBOARD_LEAGUES[0];

  const [dashboard, teamsData] = await Promise.all([
    api.dashboard(),
    api.teams({ limit: 100, offset: 0 }),
  ]);
  if (!dashboard) {
    return (
      <>
        <Header title="ダッシュボード" />
        <ErrorState message="ダッシュボードを取得できませんでした。" />
      </>
    );
  }

  const {
    featured_matches,
    model_performance,
    data_status,
    standings_summary,
    rankings_summary,
  } = dashboard;
  const selectedStandings = standings_summary[selectedLeagueId] ?? [];
  const selectedRankings = rankings_summary[selectedLeagueId] ?? [];
  const teamsById = new Map(
    (teamsData?.items ?? []).map((team) => [team.id, team]),
  );

  return (
    <>
      <Header title="ダッシュボード" />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.7fr) minmax(320px, 1fr)',
          gap: 16,
          alignItems: 'start',
        }}
      >
        <section>
          <h3>次の注目試合予測</h3>
          {featured_matches.length === 0 ? (
            <EmptyState message="予測対象の試合はありません。" />
          ) : (
            <div style={{ display: 'grid', gap: 12 }}>
              {featured_matches.slice(0, 3).map((match) => (
                <MatchCard key={match.id} match={match} />
              ))}
            </div>
          )}
        </section>

        <aside style={{ display: 'grid', gap: 16 }}>
          <section className="card" style={{ overflow: 'hidden' }}>
            <h3>予測モデル評価</h3>
            {model_performance ? (
              <>
                <div style={{ display: 'flex', gap: 18, alignItems: 'center' }}>
                  <div
                    style={{
                      width: 128,
                      height: 128,
                      flex: '0 0 128px',
                      borderRadius: '50%',
                      border: '12px solid #1e293b',
                      borderTopColor: '#3b82f6',
                      display: 'grid',
                      placeItems: 'center',
                      textAlign: 'center',
                    }}
                  >
                    <div>
                      <strong style={{ fontSize: '1.45rem' }}>
                        {percent(model_performance.overall_accuracy)}
                      </strong>
                      <div style={{ color: '#94a3b8', fontSize: '0.72rem' }}>
                        Accuracy
                      </div>
                    </div>
                  </div>

                  <div style={{ minWidth: 0 }}>
                    <strong style={{ display: 'block' }}>
                      {displayModelName(model_performance.model_version)}
                    </strong>
                    <small
                      style={{
                        display: 'block',
                        marginTop: 6,
                        color: '#94a3b8',
                        overflowWrap: 'anywhere',
                      }}
                    >
                      {model_performance.model_version}
                    </small>
                  </div>
                </div>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                    gap: 10,
                    marginTop: 18,
                  }}
                >
                  <div className="stat-card">
                    <small>評価試合数</small>
                    <strong>{model_performance.total_predictions}</strong>
                  </div>
                  <div className="stat-card">
                    <small>テスト正解数</small>
                    <strong>{model_performance.correct_predictions}</strong>
                  </div>
                </div>

                <p style={{ marginBottom: 0, color: '#94a3b8', fontSize: '0.82rem' }}>
                  時系列ホールドアウトテストの評価値です。運用開始後の実試合的中率ではありません。
                </p>
                <Link href="/model/performance" style={{ display: 'inline-block', marginTop: 10 }}>
                  詳細を見る →
                </Link>
              </>
            ) : (
              <EmptyState message="モデル評価データがありません。" />
            )}
          </section>

          <section className="card">
            <h3>データ更新状況</h3>
            {data_status.length === 0 ? (
              <EmptyState message="データ更新状況がありません。" />
            ) : (
              <div style={{ display: 'grid', gap: 0 }}>
                {data_status.slice(0, 5).map((status, index) => (
                  <div
                    key={`${status.source}-${status.data_type}-${index}`}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: 12,
                      padding: '10px 0',
                      borderBottom: '1px solid #334155',
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <strong>{status.source}</strong>
                      <div style={{ color: '#94a3b8', fontSize: '0.78rem' }}>
                        {status.data_type}
                      </div>
                    </div>
                    <StatusDot status={status.status} />
                  </div>
                ))}
              </div>
            )}
            <Link href="/data-status" style={{ display: 'inline-block', marginTop: 12 }}>
              すべて見る →
            </Link>
          </section>
        </aside>
      </div>

      <section className="card" style={{ marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>順位表・選手ランキングのリーグ</h3>
        <nav style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {DASHBOARD_LEAGUES.map((league) => (
            <Link
              key={league.id}
              href={league.id === 'pl' ? '/' : `/?league=${league.id}`}
              scroll={false}
              style={{
                padding: '9px 13px',
                borderRadius: 999,
                textDecoration: 'none',
                background: league.id === selectedLeagueId ? '#2563eb' : '#1e293b',
                color: league.id === selectedLeagueId ? '#fff' : '#cbd5e1',
                border: '1px solid #334155',
                fontWeight: 700,
              }}
            >
              {league.label}
            </Link>
          ))}
        </nav>
      </section>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 2fr) minmax(300px, 1fr)',
          gap: 16,
          marginTop: 16,
          alignItems: 'start',
        }}
      >
        <section className="card table-wrap">
          <h3>{selectedLeague.label} 順位表（トップ5）</h3>
          {selectedStandings.length === 0 ? (
            <EmptyState message="順位表データがありません。" />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>順位</th>
                  <th>チーム</th>
                  <th>試合</th>
                  <th>得失点</th>
                  <th>勝点</th>
                  <th>直近5</th>
                </tr>
              </thead>
              <tbody>
                {selectedStandings.slice(0, 5).map((row, index) => {
                  const goalDifference = row.goals_for - row.goals_against;
                  return (
                    <tr key={row.team_id}>
                      <td>{row.position ?? index + 1}</td>
                      <td>
                        <Link
                          href={`/teams/${row.team_id}`}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 8,
                          }}
                        >
                          <TeamCrest
                            name={row.team_name}
                            logoUrl={teamsById.get(row.team_id)?.logo_url}
                            color={teamsById.get(row.team_id)?.color}
                            size={28}
                          />
                          {row.team_name}
                        </Link>
                      </td>
                      <td>{row.played}</td>
                      <td>{goalDifference >= 0 ? '+' : ''}{goalDifference}</td>
                      <td><strong>{row.points}</strong></td>
                      <td>{row.recent_form ? <Form value={row.recent_form} /> : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>

        <section className="card">
          <h3>{selectedLeague.label} 得点ランキング</h3>
          {selectedRankings.length === 0 ? (
            <EmptyState
              message={`2026–27シーズンは開幕前のため、${selectedLeague.label}の得点ランキングはまだありません。`}
            />
          ) : (
            <div style={{ display: 'grid', gap: 12 }}>
              {selectedRankings.slice(0, 5).map((player, index) => (
                <div
                  key={`${player.player_id ?? player.player_name}-${index}`}
                  style={{ display: 'grid', gridTemplateColumns: '28px 1fr auto', gap: 10 }}
                >
                  <strong>{index + 1}</strong>
                  <div>
                    {player.player_id ? (
                      <Link href={`/players/${player.player_id}`}>{player.player_name}</Link>
                    ) : player.player_name}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 7,
                        color: '#94a3b8',
                        fontSize: '0.78rem',
                        marginTop: 4,
                      }}
                    >
                      <TeamCrest
                        name={player.team_name || '所属チーム未確認'}
                        logoUrl={
                          player.team_logo_url ||
                          (player.team_id
                            ? teamsById.get(player.team_id)?.logo_url
                            : null)
                        }
                        color={
                          player.team_id
                            ? teamsById.get(player.team_id)?.color
                            : undefined
                        }
                        size={24}
                      />
                      {player.team_id ? (
                        <Link href={`/teams/${player.team_id}`}>
                          {player.team_name}
                        </Link>
                      ) : (
                        <span>{player.team_name || '所属チーム未確認'}</span>
                      )}
                    </div>
                  </div>
                  <strong>{player.value}</strong>
                </div>
              ))}
            </div>
          )}
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 12 }}>
            <Link href={`/leagues/${selectedLeagueId}/standings`}>
              順位表を見る →
            </Link>
            <Link href={`/leagues/${selectedLeagueId}/rankings`}>
              ランキングを見る →
            </Link>
          </div>
        </section>
      </div>
    </>
  );
}
