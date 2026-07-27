import Link from 'next/link';
import { api } from '../lib/api';
import { Crest, EmptyState, ErrorState, Header, TeamCrest } from '../components/ui';

const LEAGUES = [
  ['pl', 'Premier League'],
  ['laliga', 'La Liga'],
  ['seriea', 'Serie A'],
  ['bundesliga', 'Bundesliga'],
  ['ligue1', 'Ligue 1'],
] as const;
const PAGE_SIZE = 24;

function EmploymentBadge({ verified }: { verified: boolean }) {
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '4px 9px',
        borderRadius: 999,
        background: verified ? '#dcfce7' : '#fef3c7',
        color: verified ? '#166534' : '#92400e',
        fontSize: '0.78rem',
        fontWeight: 700,
      }}
    >
      {verified ? '現所属確認済み' : '所属情報は暫定'}
    </span>
  );
}

export default async function ManagersPage({
  searchParams,
}: {
  searchParams: {
    league?: string;
    team?: string;
    role?: string;
    q?: string;
    page?: string;
  };
}) {
  const page = Math.max(1, Number(searchParams.page || '1') || 1);
  const data = await api.managers({
    league_id: searchParams.league,
    team_id: searchParams.team,
    role: searchParams.role,
    search: searchParams.q,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });

  if (!data) {
    return (
      <>
        <Header title="監督一覧" crumb="監督" />
        <ErrorState message="監督一覧を取得できませんでした。" />
      </>
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const pageHref = (targetPage: number) => {
    const params = new URLSearchParams();
    if (searchParams.league) params.set('league', searchParams.league);
    if (searchParams.team) params.set('team', searchParams.team);
    if (searchParams.role) params.set('role', searchParams.role);
    if (searchParams.q) params.set('q', searchParams.q);
    params.set('page', String(targetPage));
    return `/managers?${params.toString()}`;
  };

  return (
    <>
      <Header title="監督一覧" crumb="監督" />

      <section className="card">
        <form
          method="get"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))',
            gap: 12,
          }}
        >
          <select name="league" defaultValue={searchParams.league || ''}>
            <option value="">5大リーグすべて</option>
            {LEAGUES.map(([id, name]) => (
              <option key={id} value={id}>{name}</option>
            ))}
          </select>
          <input name="team" defaultValue={searchParams.team || ''} placeholder="チームID" />
          <input name="role" defaultValue={searchParams.role || ''} placeholder="役職" />
          <input name="q" defaultValue={searchParams.q || ''} placeholder="監督名検索" />
          <button type="submit">絞り込む</button>
        </form>
        <p style={{ color: '#64748b' }}>
          該当 {data.total.toLocaleString('ja-JP')}件 · {page}/{totalPages}ページ
        </p>
      </section>

      <section className="card" style={{ borderLeft: '4px solid #f59e0b' }}>
        <h3 style={{ marginTop: 0 }}>データについて</h3>
        <p style={{ marginBottom: 0 }}>
          football-data.orgでは96クラブすべての現所属監督を確認できませんでした。
          現在表示している監督はTheSportsDBの登録情報を暫定的に使用しています。
          監督成績は未取得のため、0ではなく「—」で表示します。
        </p>
      </section>

      {data.items.length === 0 ? (
        <EmptyState message="条件に一致する監督がいません。" />
      ) : (
        <section
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill,minmax(290px,1fr))',
            gap: 16,
          }}
        >
          {data.items.map((manager) => {
            const verified = manager.employment_verified === true;
            return (
              <article key={manager.id} className="card">
                <Link
                  href={`/managers/${manager.id}`}
                  style={{ textDecoration: 'none', color: 'inherit' }}
                >
                  <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
                    {manager.photo_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={manager.photo_url}
                        alt={manager.name}
                        width={72}
                        height={72}
                        style={{
                          borderRadius: 12,
                          objectFit: 'cover',
                          background: '#e2e8f0',
                        }}
                      />
                    ) : (
                      <Crest name={manager.name} size={72} />
                    )}
                    <div style={{ minWidth: 0 }}>
                      <strong>{manager.name}</strong>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '5px 0' }}>
                        <TeamCrest name={manager.team_name || '所属クラブ未確認'} logoUrl={manager.team_logo_url} size={26} />
                        <span>{manager.team_name || '所属クラブ未確認'}</span>
                      </div>
                      <EmploymentBadge verified={verified} />
                    </div>
                  </div>
                </Link>

                <p style={{ color: '#64748b' }}>
                  {manager.role || 'Manager'} · {manager.nationality || '—'}
                  {manager.age != null ? ` · ${manager.age}歳` : ''}
                </p>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3,1fr)',
                    gap: 8,
                    textAlign: 'center',
                  }}
                >
                  <div><small>試合</small><div><strong>{manager.matches ?? '—'}</strong></div></div>
                  <div><small>勝利</small><div><strong>{manager.wins ?? '—'}</strong></div></div>
                  <div><small>敗戦</small><div><strong>{manager.losses ?? '—'}</strong></div></div>
                </div>
              </article>
            );
          })}
        </section>
      )}

      <nav style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 24 }}>
        {page > 1 && <Link href={pageHref(page - 1)}>← 前へ</Link>}
        {page < totalPages && <Link href={pageHref(page + 1)}>次へ →</Link>}
      </nav>
    </>
  );
}
