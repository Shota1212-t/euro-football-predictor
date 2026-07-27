import { api } from '../lib/api';
import { EmptyState, ErrorState, Header } from '../components/ui';

export default async function DataSourcesPage() {
  const sources = await api.dataSources();

  if (sources === null) {
    return (
      <>
        <Header title="データソース" crumb="データソース" />
        <ErrorState message="GET /api/v1/data-sources に失敗しました。" />
      </>
    );
  }

  return (
    <>
      <Header title="データソース" crumb="データソース" />
      {sources.length === 0 ? (
        <EmptyState message="データソース情報がまだ登録されていません。" />
      ) : (
        <div className="sourceGrid">
          {sources.map((source) => (
            <article className="card source" key={source.name}>
              <b>{source.name}</b>
              <p>{source.purpose}</p>
              <div className="muted">取得データ：{source.data_fetched}</div>
              <div className="muted" style={{ marginTop: 6 }}>
                更新頻度：{source.update_frequency}
              </div>
              {source.notes && (
                <div className="muted" style={{ marginTop: 10 }}>
                  {source.notes}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </>
  );
}
