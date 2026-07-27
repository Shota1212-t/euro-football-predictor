import { api } from '../../lib/api';
import { ErrorState, Form, Header, MatchCard, Stat, TeamCrest } from '../../components/ui';

export default async function TeamDetailPage({ params }: { params: { id: string } }) {
  const detail = await api.team(params.id);

  if (!detail) {
    return (
      <>
        <Header title="チーム詳細" />
        <ErrorState message="指定されたチームが見つかりませんでした。" />
      </>
    );
  }

  const { team, manager, players, upcoming_matches, standing } = detail;

  return (
    <>
      <Header title="チーム詳細" crumb={`チーム › ${team.name}`} />

      <section className="card hero">
        <TeamCrest name={team.name} logoUrl={team.logo_url} color={team.color} size={82} />
        <div>
          <h2>{team.name}</h2>
          <span className="muted">
            {team.country ?? '-'} · {team.stadium ?? '-'}
          </span>
          {manager && <p>監督：{manager.name}</p>}
        </div>
      </section>

      {standing && (
        <div className="metricRow" style={{ marginTop: 12, marginBottom: 12 }}>
          <Stat label="勝ち点" value={standing.points} />
          <Stat label="得失点差" value={`${standing.goals_for - standing.goals_against >= 0 ? '+' : ''}${standing.goals_for - standing.goals_against}`} />
          <Stat label="直近5試合" value={standing.recent_form} />
        </div>
      )}

      <div className="grid">
        <section className="card span7">
          <h2>今季成績</h2>
          {standing ? (
            <>
              <div className="metricRow">
                <Stat label="試合" value={standing.played} />
                <Stat label="勝 / 分 / 敗" value={`${standing.win} / ${standing.draw} / ${standing.loss}`} />
                <Stat label="得点 / 失点" value={`${standing.goals_for} / ${standing.goals_against}`} />
              </div>
              <h2 style={{ marginTop: 20 }}>直近5試合</h2>
              <Form value={standing.recent_form} />
            </>
          ) : (
            <p className="muted">順位表データがまだありません。</p>
          )}

          <h2 style={{ marginTop: 20 }}>所属選手</h2>
          {players.length === 0 ? (
            <p className="muted">選手データがまだありません。</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>選手</th>
                  <th>ポジション</th>
                  <th>国籍</th>
                  <th>得点</th>
                  <th>アシスト</th>
                </tr>
              </thead>
              <tbody>
                {players.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <a href={`/players/${p.id}`}>{p.name}</a>
                    </td>
                    <td>{p.position ?? '-'}</td>
                    <td>{p.nationality ?? '-'}</td>
                    <td>{p.goals}</td>
                    <td>{p.assists}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="span5 stack">
          <h2 className="sectionTitle">次の試合</h2>
          {upcoming_matches.length === 0 ? (
            <p className="muted">予測対象の試合はありません。</p>
          ) : (
            upcoming_matches.slice(0, 2).map((m) => <MatchCard key={m.id} match={m} />)
          )}
          {manager && (
            <div className="card">
              <h2>監督</h2>
              <p>
                <a href={`/managers/${manager.id}`}>{manager.name}</a>
              </p>
              <p className="muted">
                {manager.nationality ?? '-'} · 就任 {manager.appointed ?? '-'}
              </p>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
