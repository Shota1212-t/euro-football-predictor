import { api } from '../../lib/api';
import { EmptyState, Header, Stat } from '../../components/ui';

const percent = (value: number | null | undefined) =>
  value == null ? '—' : `${(value * 100).toFixed(2)}%`;
const decimal = (value: number | null | undefined) =>
  value == null ? '—' : value.toFixed(4);

export default async function ModelPerformancePage() {
  const perf = await api.modelPerformance();
  if (!perf) {
    return (
      <>
        <Header title="予測精度" crumb="モデル" />
        <EmptyState message="モデル精度データがありません。" />
      </>
    );
  }

  return (
    <>
      <Header title="予測精度" crumb="モデル" />

      <section className="card">
        <h3>本番モデル</h3>
        <p><strong>{perf.model_name}</strong></p>
        <p style={{ overflowWrap: 'anywhere' }}>{perf.model_version}</p>
        <div className="stats-grid">
          <Stat label="評価試合数" value={perf.total_predictions} />
          <Stat label="正解試合数" value={perf.correct_predictions} />
          <Stat label="使用特徴量" value={perf.feature_count} />
          <Stat label="オッズ" value={perf.production_variant === 'no_odds' ? '不使用' : '使用'} />
          <Stat label="確率校正" value={perf.production_calibration === 'uncalibrated' ? '未校正' : '校正済み'} />
          <Stat label="クラス重み" value={perf.class_weight || '—'} />
        </div>
        <p style={{ color: '#64748b' }}>
          学習日時：{perf.trained_at ? new Date(perf.trained_at).toLocaleString('ja-JP') : '—'}
        </p>
      </section>

      <section className="card">
        <h3>時系列ホールドアウト評価</h3>
        <div className="stats-grid">
          <Stat label="Accuracy" value={percent(perf.overall_accuracy)} />
          <Stat label="Macro F1" value={percent(perf.macro_f1)} />
          <Stat label="Log Loss" value={decimal(perf.log_loss)} />
          <Stat label="Brier Score" value={decimal(perf.brier_score)} />
          <Stat label="ECE" value={decimal(perf.expected_calibration_error)} />
        </div>
        <p>{perf.operational_note}</p>
      </section>

      <section className="card">
        <h3>引き分け検出性能</h3>
        <div className="stats-grid">
          <Stat label="Precision" value={percent(perf.draw_precision)} />
          <Stat label="Recall" value={percent(perf.draw_recall)} />
          <Stat label="F1" value={percent(perf.draw_f1)} />
        </div>
      </section>

      <section className="card">
        <h3>クラス別性能</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>結果</th><th>Precision</th><th>Recall</th><th>F1</th><th>件数</th></tr>
            </thead>
            <tbody>
              {[
                ['ホーム勝利', perf.class_metrics.home_win],
                ['引き分け', perf.class_metrics.draw],
                ['アウェイ勝利', perf.class_metrics.away_win],
              ].map(([label, metrics]) => (
                <tr key={String(label)}>
                  <td>{String(label)}</td>
                  <td>{percent(typeof metrics === 'object' ? metrics.precision : null)}</td>
                  <td>{percent(typeof metrics === 'object' ? metrics.recall : null)}</td>
                  <td>{percent(typeof metrics === 'object' ? metrics['f1-score'] : null)}</td>
                  <td>{typeof metrics === 'object' ? metrics.support : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <h3>評価条件</h3>
        <ul>
          <li>学習データ終了日：{perf.train_end || '—'}</li>
          <li>検証データ開始日：{perf.validation_start || '—'}</li>
          <li>テストデータ開始日：{perf.test_start || '—'}</li>
          <li>除外特徴量：{perf.excluded_features.join(', ') || 'なし'}</li>
        </ul>
        <p>{perf.probability_note}</p>
        <p>{perf.selection_reason}</p>
      </section>
    </>
  );
}
