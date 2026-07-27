import { api } from '../lib/api';
import { EmptyState, ErrorState, Header, MatchCard } from '../components/ui';

const LEAGUE_TABS = [
  { id: undefined, label: 'すべて' },
  { id: 'pl', label: 'Premier League' },
  { id: 'laliga', label: 'La Liga' },
  { id: 'seriea', label: 'Serie A' },
  { id: 'bundesliga', label: 'Bundesliga' },
  { id: 'ligue1', label: 'Ligue 1' },
] as const;

export default async function MatchesPage({
  searchParams,
}: {
  searchParams: { league?: string };
}) {
  const league = searchParams.league;
  const matches = await api.matches({ league });

  return (
    <>
      <Header title="試合予測" crumb="試合予測" />

      <div className="tabs">
        {LEAGUE_TABS.map((tab) => (
          <a
            key={tab.label}
            href={tab.id ? `/matches?league=${tab.id}` : '/matches'}
            className={`tab ${league === tab.id || (!league && !tab.id) ? 'active' : ''}`}
          >
            {tab.label}
          </a>
        ))}
      </div>

      {matches === null ? (
        <ErrorState message="GET /api/v1/matches に失敗しました。" />
      ) : matches.length === 0 ? (
        <EmptyState message="現在、予測対象の試合はありません。" />
      ) : (
        <div className="grid">
          {matches.map((m) => (
            <div className="span6" key={m.id}>
              <MatchCard match={m} />
            </div>
          ))}
        </div>
      )}
    </>
  );
}
