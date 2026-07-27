import Link from 'next/link';
import { api } from '../lib/api';
import { EmptyState, ErrorState, Header, TeamCrest } from '../components/ui';

const LEAGUES = [
  ['pl', 'Premier League'],
  ['laliga', 'La Liga'],
  ['seriea', 'Serie A'],
  ['bundesliga', 'Bundesliga'],
  ['ligue1', 'Ligue 1'],
] as const;

export default async function TeamsPage({
  searchParams,
}: {
  searchParams: { league?: string; q?: string };
}) {
  const data = await api.teams({
    league_id: searchParams.league,
    search: searchParams.q,
    limit: 100,
    offset: 0,
  });

  if (!data) {
    return (
      <>
        <Header title="チーム一覧" crumb="チーム" />
        <ErrorState message="チーム一覧を取得できませんでした。" />
      </>
    );
  }

  return (
    <>
      <Header title="チーム一覧" crumb="チーム" />

      <section className="card">
        <form
          method="get"
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(180px, 1fr) minmax(220px, 2fr) auto',
            gap: 12,
          }}
        >
          <select name="league" defaultValue={searchParams.league || ''}>
            <option value="">5大リーグすべて</option>
            {LEAGUES.map(([id, name]) => (
              <option key={id} value={id}>{name}</option>
            ))}
          </select>
          <input name="q" defaultValue={searchParams.q || ''} placeholder="チーム名検索" />
          <button type="submit">絞り込む</button>
        </form>
        <p style={{ marginBottom: 0, color: '#64748b' }}>
          該当 {data.total}クラブ
        </p>
      </section>

      {data.items.length === 0 ? (
        <EmptyState message="条件に一致するチームが見つかりませんでした。" />
      ) : (
        <section
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: 16,
          }}
        >
          {data.items.map((team) => (
            <Link
              key={team.id}
              href={`/teams/${team.id}`}
              className="card"
              style={{ textDecoration: 'none', color: 'inherit' }}
            >
              <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                <TeamCrest name={team.name} logoUrl={team.logo_url} color={team.color} size={72} />                <div style={{ minWidth: 0 }}>
                  <strong>{team.name}</strong>
                  <p style={{ margin: '5px 0' }}>
                    {team.country || '—'} · {team.stadium || 'スタジアム未登録'}
                  </p>
                  <small style={{ color: '#64748b' }}>
                    {team.manager_name ? `監督：${team.manager_name}` : '監督情報なし'}
                  </small>
                </div>
              </div>
              <div style={{ marginTop: 14, display: 'flex', gap: 16 }}>
                <span>順位：{team.standing_position ?? '—'}</span>
                <span>試合：{team.standing_played ?? '—'}</span>
                <span>勝点：{team.standing_points ?? '—'}</span>
              </div>
            </Link>
          ))}
        </section>
      )}
    </>
  );
}
