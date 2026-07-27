import { api } from '../lib/api';
import {
  EmptyState,
  ErrorState,
  Header,
  StaleBanner,
  StatusDot,
} from '../components/ui';

function formatUpdatedAt(value: string | null): string {
  if (!value) return '—';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';

  return date.toLocaleString('ja-JP');
}

export default async function DataStatusPage() {
  const items = await api.dataStatus();

  if (items === null) {
    return (
      <>
        <Header title="データ更新状況" crumb="データ" />
        <ErrorState />
      </>
    );
  }

  const hasStale = items.some((item) => item.is_stale);

  return (
    <>
      <Header title="データ更新状況" crumb="データ" />
      {hasStale && <StaleBanner />}

      {items.length === 0 ? (
        <EmptyState message="データ更新状況がありません。" />
      ) : (
        <section className="card table-wrap">
          <table>
            <thead>
              <tr>
                <th>データソース</th>
                <th>データ種別</th>
                <th>最終更新</th>
                <th>取得件数</th>
                <th>ステータス</th>
                <th>次回予定</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, index) => (
                <tr key={`${item.source}-${item.data_type}-${index}`}>
                  <td>
                    <strong>{item.source}</strong>
                  </td>
                  <td>{item.data_type}</td>
                  <td>{formatUpdatedAt(item.last_updated)}</td>
                  <td>{item.records}</td>
                  <td>
                    <StatusDot status={item.status} />
                    {item.error && (
                      <div style={{ marginTop: 4, color: '#b45309', fontSize: '0.8rem' }}>
                        {item.error}
                      </div>
                    )}
                  </td>
                  <td>{item.next_update ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}
