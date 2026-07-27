import Link from 'next/link';
import { api } from '../../../lib/api';
import { EmptyState, ErrorState, Header, TeamCrest } from '../../../components/ui';

const LEAGUES = [
  { id: 'pl', label: 'Premier League' },
  { id: 'laliga', label: 'La Liga' },
  { id: 'seriea', label: 'Serie A' },
  { id: 'bundesliga', label: 'Bundesliga' },
  { id: 'ligue1', label: 'Ligue 1' },
] as const;

const TABS = [
  { id: 'goals', label: '得点' },
  { id: 'assists', label: 'アシスト' },
  { id: 'appearances', label: '出場試合数' },
  { id: 'yellow_cards', label: 'イエローカード' },
  { id: 'red_cards', label: 'レッドカード' },
] as const;

type RankingType = (typeof TABS)[number]['id'];

function isRankingType(value: string | undefined): value is RankingType {
  return TABS.some((tab) => tab.id === value);
}

function seasonLabel(start?: string | null, end?: string | null): string | null {
  if (!start || !end) return null;
  return `${start.slice(0, 4)}–${end.slice(2, 4)}`;
}

export default async function RankingsPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams: { type?: string };
}) {
  const type: RankingType = isRankingType(searchParams.type)
    ? searchParams.type
    : 'goals';

  const [leagues, rankings] = await Promise.all([
    api.leagues(),
    api.rankings(params.id, type),
  ]);
  const league = leagues?.find((item) => item.id === params.id);
  const columnLabel = TABS.find((tab) => tab.id === type)?.label ?? '数値';

  if (rankings === null) {
    return (
      <>
        <Header title={`${league?.name ?? params.id} 選手ランキング`} crumb="ランキング" />
        <ErrorState message="選手ランキングを取得できませんでした。" />
      </>
    );
  }

  const season = seasonLabel(
    rankings.metadata?.season_start,
    rankings.metadata?.season_end,
  );

  return (
    <>
      <Header title={`${league?.name ?? params.id} 選手ランキング`} crumb="ランキング" />

      <section className="card">
        <h3 style={{ marginTop: 0 }}>リーグ</h3>
        <nav style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {LEAGUES.map((item) => (
            <Link
              key={item.id}
              href={`/leagues/${item.id}/rankings?type=${type}`}
              style={{
                padding: '9px 13px',
                borderRadius: 999,
                textDecoration: 'none',
                background: item.id === params.id ? '#1d4ed8' : '#e2e8f0',
                color: item.id === params.id ? '#fff' : '#334155',
                fontWeight: 700,
              }}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </section>

      <section className="card">
        <h3 style={{ marginTop: 0 }}>ランキング種別</h3>
        <nav style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {TABS.map((tab) => (
            <Link
              key={tab.id}
              href={`/leagues/${params.id}/rankings?type=${tab.id}`}
              style={{
                padding: '8px 12px',
                borderRadius: 999,
                textDecoration: 'none',
                background: tab.id === type ? '#0f766e' : '#e2e8f0',
                color: tab.id === type ? '#fff' : '#334155',
                fontWeight: 700,
              }}
            >
              {tab.label}
            </Link>
          ))}
        </nav>
      </section>

      <section className="card">
        <strong>{league?.name ?? params.id} · {columnLabel}</strong>
        <p style={{ marginBottom: 0, color: '#64748b' }}>
          {season ? `${season}シーズン` : '対象シーズン'} · データ元：
          {rankings.metadata?.source ?? '未設定'}
        </p>
      </section>

      {rankings.state === 'unavailable' ? (
        <EmptyState message={rankings.message || 'このランキング種別は現在のデータソースでは取得できません。'} />
      ) : rankings.state === 'preseason' || rankings.state === 'empty' ? (
        <EmptyState message={rankings.message || 'シーズン開幕前のため、選手ランキングはまだありません。'} />
      ) : rankings.state === 'not_generated' ? (
        <EmptyState message={rankings.message || 'ランキングデータをまだ生成していません。'} />
      ) : rankings.items.length === 0 ? (
        <EmptyState message="ランキングデータがありません。" />
      ) : (
        <section className="card table-wrap">
          <table>
            <thead>
              <tr>
                <th>順位</th>
                <th>選手</th>
                <th>チーム</th>
                <th>ポジション</th>
                <th>{columnLabel}</th>
              </tr>
            </thead>
            <tbody>
              {rankings.items.map((row, index) => (
                <tr key={`${row.player_id ?? row.player_name}-${index}`}>
                  <td><strong>{index + 1}</strong></td>
                  <td>
                    {row.player_id ? (
                      <Link href={`/players/${row.player_id}`}><strong>{row.player_name}</strong></Link>
                    ) : (
                      <strong>{row.player_name}</strong>
                    )}
                  </td>
                  <td>
                    {row.team_id ? (
                      <Link
                        href={`/teams/${row.team_id}`}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 9 }}
                      >
                        <TeamCrest
                          name={row.team_name}
                          logoUrl={row.team_logo_url}
                          size={28}
                        />
                        {row.team_name}
                      </Link>
                    ) : (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9 }}>
                        <TeamCrest
                          name={row.team_name || 'Unknown'}
                          logoUrl={row.team_logo_url}
                          size={28}
                        />
                        {row.team_name}
                      </span>
                    )}
                  </td>
                  <td>{row.position ?? '—'}</td>
                  <td><strong>{row.value}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}
