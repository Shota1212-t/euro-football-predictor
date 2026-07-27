import { api } from '../../lib/api';
import { Crest, ErrorState, Header, Stat, TeamCrest } from '../../components/ui';

export default async function PlayerDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const detail = await api.player(params.id);

  if (!detail) {
    return (
      <>
        <Header title="選手詳細" crumb="選手" />
        <ErrorState message="選手情報を取得できませんでした。" />
      </>
    );
  }

  const { player, team, next_match, data_notice } = detail;
  const isVerified = player.roster_status === 'verified';
  const displayStat = (value: number | null | undefined) =>
    value === null || value === undefined ? '—' : value;

  return (
    <>
      <Header title="選手詳細" crumb="選手" />

      <section className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          {player.photo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={player.photo_url}
              alt={player.name}
              width={112}
              height={112}
              style={{
                borderRadius: 16,
                objectFit: 'cover',
                background: '#e2e8f0',
              }}
            />
          ) : (
            <Crest name={player.name} size={112} />
          )}

          <div>
            <h3>{player.name}</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
              {team ? (
                <TeamCrest name={team.name} logoUrl={team.logo_url} color={team.color} size={32} />
              ) : null}
              <p style={{ margin: 0 }}>
                {team?.name ?? '-'} · {player.position ?? '-'} ·{' '}
                {player.nationality ?? '-'}
                {player.shirt_number ? ` · #${player.shirt_number}` : ''}
              </p>
            </div>
            <p
              style={{
                display: 'inline-block',
                margin: '8px 0 0',
                padding: '4px 9px',
                borderRadius: 999,
                background: isVerified ? '#dcfce7' : '#fef3c7',
                color: isVerified ? '#166534' : '#92400e',
                fontSize: '0.8rem',
                fontWeight: 700,
              }}
            >
              {isVerified ? '現所属確認済み' : '所属情報は暫定'}
            </p>
          </div>
        </div>

        <p style={{ marginTop: 16, color: '#64748b', fontSize: '0.9rem' }}>
          {data_notice}
        </p>
      </section>

      <section className="card">
        <h3>基本情報</h3>
        <div className="stats-grid">
          <Stat label="年齢" value={player.age ?? '—'} />
          <Stat label="生年月日" value={player.date_of_birth ?? '—'} />
          <Stat label="身長" value={player.height || '—'} />
          <Stat label="体重" value={player.weight || '—'} />
        </div>
      </section>

      <section className="card">
        <h3>今季成績</h3>
        {!player.statistics_available && (
          <p style={{ color: '#64748b' }}>
            シーズン成績はまだ取得していません。未取得値を0としては表示しません。
          </p>
        )}
        <div className="stats-grid">
          <Stat label="出場" value={displayStat(player.appearances)} />
          <Stat label="得点" value={displayStat(player.goals)} />
          <Stat label="アシスト" value={displayStat(player.assists)} />
          <Stat label="警告" value={displayStat(player.yellow_cards)} />
          <Stat label="退場" value={displayStat(player.red_cards)} />
        </div>
      </section>

      {(player.description_ja || player.description_en) && (
        <section className="card">
          <h3>プロフィール</h3>
          <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
            {player.description_ja || player.description_en}
          </p>
        </section>
      )}

      <section className="card">
        <h3>次の試合</h3>
        {next_match ? (
          <>
            {(() => {
              const opponent = next_match.home_team.id === player.team_id
                ? next_match.away_team
                : next_match.home_team;
              return (
                <p style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                  <TeamCrest name={opponent.name} logoUrl={opponent.logo_url} color={opponent.color} size={32} />
                  <span>vs {opponent.name}</span>
                </p>
              );
            })()}
            <strong>
              {new Date(next_match.kickoff).toLocaleString('ja-JP')}
            </strong>
          </>
        ) : (
          <p>予定されている試合はありません。</p>
        )}
      </section>
    </>
  );
}
