import { Fragment } from 'react';
import { api } from '../../lib/api';
import {
  ErrorState,
  FatigueBadge,
  Header,
  Probability,
  TeamCrest,
} from '../../components/ui';
import type { FatigueDetail } from '../../lib/types';

const RESULT_LABELS: Record<string, string> = {
  'Home Win': 'ホーム勝利',
  Draw: '引き分け',
  'Away Win': 'アウェイ勝利',
};

const STATUS_LABELS: Record<string, string> = {
  available: '取得済み',
  partial: '一部取得',
  partial_last_event_only: '直前1試合のみ補完',
  not_available: '取得不可',
  unknown: '不明',
};

function formatFeatureValue(value: number | null): string {
  if (value === null || Number.isNaN(value)) return '—';
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function yesNo(value: boolean): string {
  return value ? 'はい' : 'いいえ';
}

function dataStatus(value?: string): string {
  return value ? STATUS_LABELS[value] ?? value : '不明';
}

function FatigueDetails({
  teamName,
  fatigue,
}: {
  teamName: string;
  fatigue: FatigueDetail;
}) {
  return (
    <article
      style={{
        border: '1px solid #334155',
        borderRadius: 12,
        padding: 16,
        minWidth: 0,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          gap: 12,
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        <strong>{teamName}</strong>
        <FatigueBadge fatigue={fatigue} />
      </div>

      <dl
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(150px, 1fr) auto',
          gap: '8px 14px',
          margin: '16px 0 0',
        }}
      >
        <dt>直近7日の全公式戦</dt>
        <dd style={{ margin: 0 }}><strong>{fatigue.matches_last_7d}試合</strong></dd>
        <dt>うち追加大会</dt>
        <dd style={{ margin: 0 }}>{fatigue.extra_matches_last_7d ?? 0}試合</dd>
        <dt>直近14日の全公式戦</dt>
        <dd style={{ margin: 0 }}><strong>{fatigue.matches_last_14d}試合</strong></dd>
        <dt>うち追加大会</dt>
        <dd style={{ margin: 0 }}>{fatigue.extra_matches_last_14d ?? 0}試合</dd>
        <dt>最終公式戦から</dt>
        <dd style={{ margin: 0 }}>
          {fatigue.days_since_last_match != null
            ? `${fatigue.days_since_last_match}日`
            : '—'}
        </dd>
        <dt>最後の追加大会</dt>
        <dd style={{ margin: 0, textAlign: 'right' }}>
          {fatigue.last_extra_competition ?? '該当なし／未取得'}
        </dd>
        <dt>追加大会データ元</dt>
        <dd style={{ margin: 0, textAlign: 'right' }}>
          {fatigue.last_extra_match_source ?? '—'}
        </dd>
        <dt>欧州大会直後</dt>
        <dd style={{ margin: 0 }}>{yesNo(fatigue.after_european_competition)}</dd>
        <dt>国内カップ直後</dt>
        <dd style={{ margin: 0 }}>{yesNo(fatigue.after_domestic_cup)}</dd>
        <dt>延長戦・PK戦確認済み</dt>
        <dd style={{ margin: 0 }}>{yesNo(fatigue.had_extra_time_or_penalties)}</dd>
      </dl>

      <details style={{ marginTop: 14 }}>
        <summary style={{ cursor: 'pointer', fontWeight: 700 }}>
          データ取得範囲
        </summary>
        <ul style={{ marginBottom: 0 }}>
          <li>Champions League：{dataStatus(fatigue.european_competition_data_status)}</li>
          <li>国内カップ等：{dataStatus(fatigue.domestic_cup_data_status)}</li>
          <li>延長戦・PK戦：{dataStatus(fatigue.extra_time_data_status)}</li>
          <li>
            完全性：{fatigue.official_matches_data_completeness ===
            'league_and_champions_league_with_partial_cup_supplement'
              ? 'リーグ戦＋CL公式データ＋カップ戦部分補完'
              : 'リーグ戦のみ'}
          </li>
        </ul>
      </details>
    </article>
  );
}

export default async function MatchDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const match = await api.match(params.id);
  if (!match) {
    return (
      <>
        <Header title="試合詳細" crumb="試合予測" />
        <ErrorState message="指定された試合を取得できませんでした。" />
      </>
    );
  }

  const kickoff = new Date(match.kickoff);
  const explanations = match.explanations ?? [];
  const predictedResult =
    RESULT_LABELS[match.predicted_result] ?? match.predicted_result;

  return (
    <>
      <Header title="試合詳細" crumb="試合予測" />

      <section className="card">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr auto 1fr',
            gap: 20,
            alignItems: 'center',
            textAlign: 'center',
          }}
        >
          <div style={{ display: 'grid', justifyItems: 'center', gap: 8 }}>
            <TeamCrest name={match.home_team.name} logoUrl={match.home_team.logo_url} color={match.home_team.color} size={72} />
            <strong>{match.home_team.name}</strong>
          </div>
          <div>
            <div>
              {kickoff.toLocaleDateString('ja-JP', {
                month: 'numeric',
                day: 'numeric',
                weekday: 'short',
              })}
            </div>
            <div>
              {kickoff.toLocaleTimeString('ja-JP', {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </div>
            <strong>VS</strong>
          </div>
          <div style={{ display: 'grid', justifyItems: 'center', gap: 8 }}>
            <TeamCrest name={match.away_team.name} logoUrl={match.away_team.logo_url} color={match.away_team.color} size={72} />
            <strong>{match.away_team.name}</strong>
          </div>
        </div>
        <p style={{ textAlign: 'center', marginTop: 18 }}>
          予測結果：<strong>{predictedResult}</strong>（信頼度 {match.confidence}）
        </p>
        <Probability match={match} />
      </section>

      <section className="card">
        <h3>チーム比較</h3>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr auto 1fr',
            gap: 12,
            alignItems: 'center',
          }}
        >
          {match.comparison.map((row, index) => (
            <Fragment key={`${row.label}-${index}`}>
              <strong style={{ textAlign: 'right' }}>{row.home_value}</strong>
              <span style={{ color: '#64748b', textAlign: 'center' }}>{row.label}</span>
              <strong>{row.away_value}</strong>
            </Fragment>
          ))}
        </div>
      </section>

      <section className="card">
        <h3>疲労指数</h3>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
            gap: 16,
          }}
        >
          <FatigueDetails teamName={match.home_team.name} fatigue={match.home_fatigue} />
          <FatigueDetails teamName={match.away_team.name} fatigue={match.away_fatigue} />
        </div>
        <p style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: 0 }}>
          疲労指数はリーグ戦と取得可能な追加大会を基準に算出しています。
          Champions Leagueは公式データ、その他の欧州大会・国内カップは直前1試合の部分補完です。
          「いいえ」は、取得範囲内で直前該当を確認できなかったことを示します。
        </p>
      </section>

      <section className="card">
        <h3>予測根拠</h3>
        <ul>
          {match.reasons.map((reason, index) => (
            <li key={`${reason}-${index}`}>{reason}</li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h3>予測に影響した主な要因（SHAP）</h3>
        {explanations.length === 0 ? (
          <p>この試合ではSHAP説明を生成できませんでした。</p>
        ) : (
          <ol style={{ paddingLeft: 22 }}>
            {explanations.map((explanation, index) => {
              const supports = explanation.impact === 'supports';
              return (
                <li key={`${explanation.feature}-${index}`} style={{ marginBottom: 16 }}>
                  <strong>{explanation.label}</strong>
                  <div>入力値：{formatFeatureValue(explanation.value)}</div>
                  <div
                    style={{
                      color: supports ? '#166534' : '#b91c1c',
                      fontWeight: 700,
                    }}
                  >
                    {supports ? '予測を支持' : '予測を抑制'}：{explanation.text}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
        <p style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: 0 }}>
          {match.explanation_note ||
            'SHAP値はモデル内部の出力への寄与を示すもので、勝敗確率がその数値分だけ変化したことを意味しません。'}
        </p>
      </section>

      {match.h2h_summary && (
        <section className="card">
          <h3>直近対戦成績（H2H）</h3>
          <p>{match.h2h_summary}</p>
        </section>
      )}

      {match.odds && (
        <section className="card">
          <h3>オッズ</h3>
          <p>ホーム勝利：<strong>{match.odds.home}</strong></p>
          <p>引き分け：<strong>{match.odds.draw}</strong></p>
          <p>アウェイ勝利：<strong>{match.odds.away}</strong></p>
        </section>
      )}
    </>
  );
}
