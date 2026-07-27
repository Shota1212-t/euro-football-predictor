import Link from 'next/link';
import { api } from '../lib/api';
import { Crest, ErrorState, Header, TeamCrest } from '../components/ui';

const LEAGUES = [
  ['pl', 'Premier League'],
  ['laliga', 'La Liga'],
  ['seriea', 'Serie A'],
  ['bundesliga', 'Bundesliga'],
  ['ligue1', 'Ligue 1'],
] as const;
const PAGE_SIZE = 48;

export default async function PlayersPage({
  searchParams,
}: {
  searchParams: {
    league?: string;
    team?: string;
    position?: string;
    q?: string;
    verification?: string;
    page?: string;
  };
}) {
  const page = Math.max(1, Number(searchParams.page || '1') || 1);
  const verification = (
    ['verified', 'provisional', 'all'].includes(searchParams.verification || '')
      ? searchParams.verification
      : 'all'
  ) as 'verified' | 'provisional' | 'all';

  const data = await api.players({
    league_id: searchParams.league,
    team_id: searchParams.team,
    position: searchParams.position,
    search: searchParams.q,
    verification,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });

  if (!data) {
    return (
      <>
        <Header title="選手一覧" crumb="選手" />
        <ErrorState message="選手一覧を取得できませんでした。" />
      </>
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const href = (target: number) => {
    const params = new URLSearchParams();
    if (searchParams.league) params.set('league', searchParams.league);
    if (searchParams.team) params.set('team', searchParams.team);
    if (searchParams.position) params.set('position', searchParams.position);
    if (searchParams.q) params.set('q', searchParams.q);
    if (verification !== 'all') params.set('verification', verification);
    params.set('page', String(target));
    return `/players?${params.toString()}`;
  };

  return (
    <>
      <Header title="選手一覧" crumb="選手" />
      <section className="card">
        <form method="get" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 12 }}>
          <select name="league" defaultValue={searchParams.league || ''}>
            <option value="">5大リーグすべて</option>
            {LEAGUES.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
          <input name="team" defaultValue={searchParams.team || ''} placeholder="チームID（例 fd-57）" />
          <input name="position" defaultValue={searchParams.position || ''} placeholder="ポジション" />
          <input name="q" defaultValue={searchParams.q || ''} placeholder="選手名検索" />
          <select name="verification" defaultValue={verification}>
            <option value="all">確認済み＋暫定</option>
            <option value="verified">現所属確認済み</option>
            <option value="provisional">暫定所属</option>
          </select>
          <button type="submit">絞り込む</button>
        </form>
        <p style={{ color: '#64748b' }}>該当 {data.total.toLocaleString('ja-JP')}件 · {page}/{totalPages}ページ</p>
      </section>

      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(290px,1fr))', gap: 16 }}>
        {data.items.map((player) => (
          <article key={player.id} className="card">
            <Link href={`/players/${player.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
              <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
                {player.photo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={player.photo_url} alt={player.name} width={72} height={72} style={{ borderRadius: 12, objectFit: 'cover', background: '#e2e8f0' }} />
                ) : (
                  <Crest name={player.name} size={72} />
                )}
                <div>
                  <strong>{player.name}</strong>
                  <p style={{ margin: '4px 0' }}>{player.position || '—'} · {player.nationality || '—'}</p>
                  <small style={{ color: player.roster_status === 'verified' ? '#166534' : '#92400e' }}>
                    {player.roster_status === 'verified' ? '現所属確認済み' : '所属情報は暫定'}
                  </small>
                </div>
              </div>
            </Link>

            <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid #e2e8f0' }}>
              <small style={{ color: '#64748b' }}>所属チーム</small>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 5 }}>
                <TeamCrest
                  name={player.team_name || player.team_id}
                  logoUrl={player.team_logo_url}
                  size={24}
                />
                <Link href={`/teams/${player.team_id}`} style={{ fontWeight: 700 }}>
                  {player.team_name || player.team_id}
                </Link>
                {player.shirt_number != null && <span>#{player.shirt_number}</span>}
              </div>
            </div>
          </article>
        ))}
      </section>

      <nav style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 24 }}>
        {page > 1 && <Link href={href(page - 1)}>← 前へ</Link>}
        {page < totalPages && <Link href={href(page + 1)}>次へ →</Link>}
      </nav>
    </>
  );
}
