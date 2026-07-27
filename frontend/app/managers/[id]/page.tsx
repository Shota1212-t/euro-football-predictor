import { api } from '../../lib/api';
import { Crest, ErrorState, Form, Header, Stat, TeamCrest } from '../../components/ui';

export default async function ManagerDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const detail = await api.manager(params.id);
  if (!detail) {
    return (
      <>
        <Header title="監督詳細" crumb="監督" />
        <ErrorState message="指定された監督を取得できませんでした。" />
      </>
    );
  }

  const { manager, team, next_match } = detail;
  const statisticsAvailable = manager.statistics_available === true;
  const verified = manager.employment_verified === true;
  const matches = manager.matches ?? null;
  const wins = manager.wins ?? null;
  const draws = manager.draws ?? null;
  const losses = manager.losses ?? null;
  const winRate =
    statisticsAvailable && matches !== null && matches > 0 && wins !== null
      ? `${((wins / matches) * 100).toFixed(1)}%`
      : '—';
  const displayStat = (value: number | null | undefined) =>
    statisticsAvailable && value !== null && value !== undefined ? value : '—';

  return (
    <>
      <Header title="監督詳細" crumb="監督" />

      <section className="card">
        <div style={{ display: 'flex', gap: 18, alignItems: 'center', flexWrap: 'wrap' }}>
          {manager.photo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={manager.photo_url}
              alt={manager.name}
              width={104}
              height={104}
              style={{ borderRadius: 16, objectFit: 'cover', background: '#e2e8f0' }}
            />
          ) : (
            <Crest name={manager.name} size={104} />
          )}
          <div>
            <h3 style={{ margin: '0 0 8px' }}>{manager.name}</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
              {team ? <TeamCrest name={team.name} logoUrl={team.logo_url} color={team.color} size={34} /> : null}
              <p style={{ margin: 0 }}>
                {team?.name ?? '所属クラブ未確認'} · {manager.role ?? '監督'} ·{' '}
                {manager.nationality ?? '—'}
                {manager.appointed ? ` · 就任 ${manager.appointed}` : ''}
              </p>
            </div>
            <span
              style={{
                display: 'inline-block',
                padding: '5px 10px',
                borderRadius: 999,
                background: verified ? '#dcfce7' : '#fef3c7',
                color: verified ? '#166534' : '#92400e',
                fontWeight: 700,
              }}
            >
              {verified ? '現所属確認済み' : '所属情報は暫定'}
            </span>
          </div>
        </div>
      </section>

      {!verified && (
        <section className="card" style={{ borderLeft: '4px solid #f59e0b' }}>
          <h3 style={{ marginTop: 0 }}>所属情報について</h3>
          <p>
            football-data.orgで現所属監督を確認できなかったため、
            TheSportsDBの登録情報を暫定的に表示しています。
            現在の所属と異なる場合があります。
          </p>
          <p style={{ marginBottom: 0, color: '#64748b' }}>
            確認元：{manager.verification_source || manager.data_source || 'TheSportsDB'}
            {manager.last_checked_at
              ? ` · 最終確認 ${new Date(manager.last_checked_at).toLocaleString('ja-JP')}`
              : ''}
          </p>
        </section>
      )}

      <section className="card">
        <h3>今季成績（現在チーム）</h3>
        {!statisticsAvailable && (
          <p style={{ color: '#64748b' }}>
            監督成績はまだ取得していません。未取得値を0としては表示しません。
          </p>
        )}
        <div className="stats-grid">
          <Stat label="試合" value={displayStat(matches)} />
          <Stat label="勝利" value={displayStat(wins)} />
          <Stat label="引分" value={displayStat(draws)} />
          <Stat label="敗戦" value={displayStat(losses)} />
          <Stat label="勝率" value={winRate} />
          <Stat label="平均得点" value={displayStat(manager.avg_goals_for)} />
          <Stat label="平均失点" value={displayStat(manager.avg_goals_against)} />
        </div>

        {statisticsAvailable && manager.recent_form && (
          <>
            <h3>直近5試合</h3>
            <Form value={manager.recent_form} />
          </>
        )}
      </section>

      <section className="card">
        <h3>次の試合</h3>
        {next_match ? (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 12, alignItems: 'center', textAlign: 'center' }}>
              <span style={{ display: 'grid', justifyItems: 'center', gap: 6 }}>
                <TeamCrest name={next_match.home_team.name} logoUrl={next_match.home_team.logo_url} color={next_match.home_team.color} size={38} />
                {next_match.home_team.name}
              </span>
              <strong>vs</strong>
              <span style={{ display: 'grid', justifyItems: 'center', gap: 6 }}>
                <TeamCrest name={next_match.away_team.name} logoUrl={next_match.away_team.logo_url} color={next_match.away_team.color} size={38} />
                {next_match.away_team.name}
              </span>
            </div>
            <p style={{ textAlign: 'center' }}>{new Date(next_match.kickoff).toLocaleString('ja-JP')}</p>
          </div>
        ) : (
          <p>予定されている試合はありません。</p>
        )}
      </section>
    </>
  );
}
