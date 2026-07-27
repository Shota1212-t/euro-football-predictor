import Link from 'next/link';
import { api } from '../../../lib/api';
import { EmptyState, ErrorState, Form, Header, TeamCrest } from '../../../components/ui';

const LEAGUES = [
  { id: 'pl', label: 'Premier League' },
  { id: 'laliga', label: 'La Liga' },
  { id: 'seriea', label: 'Serie A' },
  { id: 'bundesliga', label: 'Bundesliga' },
  { id: 'ligue1', label: 'Ligue 1' },
] as const;

const TABS = [
  { id: 'total', label: '総合順位' },
  { id: 'home', label: 'ホーム順位' },
  { id: 'away', label: 'アウェイ順位' },
  { id: 'last5', label: '直近5試合' },
] as const;

type StandingTab = (typeof TABS)[number]['id'];

function isStandingTab(value: string | undefined): value is StandingTab {
  return TABS.some((tab) => tab.id === value);
}

export default async function StandingsPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams: { tab?: string };
}) {
  const tab: StandingTab = isStandingTab(searchParams.tab)
    ? searchParams.tab
    : 'total';
  const [leagues, standings] = await Promise.all([
    api.leagues(),
    api.standings(params.id, tab),
  ]);
  const league = leagues?.find((item) => item.id === params.id);

  return (
    <>
      <Header title={`${league?.name ?? params.id} 順位表`} crumb="順位表" />

      <section className="card">
        <h3 style={{ marginTop: 0 }}>リーグ</h3>
        <nav style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {LEAGUES.map((item) => (
            <Link
              key={item.id}
              href={`/leagues/${item.id}/standings?tab=${tab}`}
              style={{
                padding: '9px 13px',
                borderRadius: 999,
                textDecoration: 'none',
                background: item.id === params.id ? '#2563eb' : '#1e293b',
                color: item.id === params.id ? '#fff' : '#cbd5e1',
                fontWeight: 700,
                border: '1px solid #334155',
              }}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </section>

      <section className="card">
        <h3 style={{ marginTop: 0 }}>表示種別</h3>
        <nav style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {TABS.map((item) => (
            <Link
              key={item.id}
              href={`/leagues/${params.id}/standings?tab=${item.id}`}
              style={{
                padding: '8px 12px',
                borderRadius: 8,
                textDecoration: 'none',
                background: item.id === tab ? '#2563eb' : '#172033',
                color: item.id === tab ? '#fff' : '#cbd5e1',
                fontWeight: 700,
                border: '1px solid #334155',
              }}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </section>

      {standings === null ? (
        <ErrorState message="順位表を取得できませんでした。" />
      ) : standings.length === 0 ? (
        <EmptyState message="順位表データがありません。" />
      ) : (
        <section className="card table-wrap">
          <table>
            <thead>
              <tr>
                {[
                  '順位',
                  'チーム',
                  '試合',
                  '勝',
                  '分',
                  '敗',
                  '得点',
                  '失点',
                  '得失点',
                  '勝点',
                  '直近5',
                ].map((heading) => <th key={heading}>{heading}</th>)}
              </tr>
            </thead>
            <tbody>
              {standings.map((row, index) => {
                const goalDifference = row.goals_for - row.goals_against;
                return (
                  <tr key={row.team_id}>
                    <td><strong>{row.position ?? index + 1}</strong></td>
                    <td><Link href={`/teams/${row.team_id}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}><TeamCrest name={row.team_name} logoUrl={row.team_logo_url} size={32} /><strong>{row.team_name}</strong></Link></td>
                    <td>{row.played}</td>
                    <td>{row.win}</td>
                    <td>{row.draw}</td>
                    <td>{row.loss}</td>
                    <td>{row.goals_for}</td>
                    <td>{row.goals_against}</td>
                    <td>{goalDifference >= 0 ? '+' : ''}{goalDifference}</td>
                    <td><strong>{row.points}</strong></td>
                    <td>{row.recent_form ? <Form value={row.recent_form} /> : '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}
