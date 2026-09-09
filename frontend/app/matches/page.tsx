'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import { deriveIncorrectPredictions, safePercent } from '../lib/types';
import type { CompletedMatch, CompletedPerformance, MatchPrediction } from '../lib/types';
import { EmptyState, ErrorState, Header, MatchCard } from '../components/ui';

const LEAGUE_TABS = [
  { id: undefined, label: 'すべて' }, { id: 'pl', label: 'Premier League' },
  { id: 'laliga', label: 'La Liga' }, { id: 'seriea', label: 'Serie A' },
  { id: 'bundesliga', label: 'Bundesliga' }, { id: 'ligue1', label: 'Ligue 1' },
] as const;

function ResultLabel({ match }: { match: CompletedMatch }) {
  if (!match.prediction_available || match.prediction_status !== 'recorded') return <strong>予測記録なし</strong>;
  return <><div>実際：{match.actual_result}</div><div>予測：{match.predicted_result}</div><strong>{match.is_correct ? '判定：的中' : '判定：不的中'}</strong></>;
}
function CompletedCard({ match }: { match: CompletedMatch }) {
  const date = new Date(match.kickoff);
  return <article className="match card">
    <div className="muted">{date.toLocaleString('ja-JP')}<span>{match.league_name}</span></div>
    <h3 style={{ textAlign: 'center' }}>{match.home_team.name} {match.home_score} - {match.away_score} {match.away_team.name}</h3>
    <ResultLabel match={match} />
    {match.prediction_available && <>
      <div className="prob"><div className="home" style={{ width: `${match.home_win_probability ?? 0}%` }}>ホーム {match.home_win_probability ?? 0}%</div><div className="draw" style={{ width: `${match.draw_probability ?? 0}%` }}>引分 {match.draw_probability ?? 0}%</div><div className="away" style={{ width: `${match.away_win_probability ?? 0}%` }}>アウェイ {match.away_win_probability ?? 0}%</div></div>
      <div className="muted" style={{ marginTop: 10 }}>confidence: {match.confidence} · data_quality: {match.data_quality} · model: {match.model_version}</div>
    </>}
  </article>;
}

export default function MatchesPage() {
  const [league, setLeague] = useState<string | undefined>();
  const [view, setView] = useState<'upcoming' | 'completed'>('upcoming');
  const [upcoming, setUpcoming] = useState<MatchPrediction[] | null>(null);
  const [completed, setCompleted] = useState<CompletedMatch[] | null>(null);
  const [performance, setPerformance] = useState<CompletedPerformance | null>(null);
  const [upcomingError, setUpcomingError] = useState<string | null>(null);
  const [completedError, setCompletedError] = useState<string | null>(null);
  const [performanceError, setPerformanceError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const loadUpcoming = async () => {
      try {
        const data = await api.matches({ league });
        if (!active) return;
        setUpcoming(data ?? []);
        setUpcomingError(data === null ? '今後の試合の取得に失敗しました。' : null);
      } catch {
        if (!active) return;
        setUpcoming([]);
        setUpcomingError('今後の試合の取得に失敗しました。');
      }
    };

    const loadCompleted = async () => {
      try {
        const data = await api.completedMatches();
        if (!active) return;
        setCompleted(data ?? []);
        setCompletedError(data === null ? '終了済み試合の取得に失敗しました。' : null);
      } catch {
        if (!active) return;
        setCompleted([]);
        setCompletedError('終了済み試合の取得に失敗しました。');
      }
    };

    const loadPerformance = async () => {
      try {
        const data = await api.completedPerformance();
        if (!active) return;
        setPerformance(
          data ?? {
            total_predictions: 0,
            correct_predictions: 0,
            accuracy: 0,
            incorrect_predictions: 0,
          },
        );
        setPerformanceError(data === null ? '成績集計の取得に失敗しました。' : null);
      } catch {
        if (!active) return;
        setPerformance({ total_predictions: 0, correct_predictions: 0, accuracy: 0, incorrect_predictions: 0 });
        setPerformanceError('成績集計の取得に失敗しました。');
      }
    };

    const refresh = async () => {
      setUpcomingError(null);
      setCompletedError(null);
      setPerformanceError(null);

      if (view === 'upcoming') {
        await loadUpcoming();
        return;
      }

      await Promise.all([loadCompleted(), loadPerformance()]);
    };

    void refresh();
    return () => {
      active = false;
    };
  }, [view, league]);

  const filteredCompleted = useMemo(() => completed?.filter(m => !league || m.league_id === league) ?? [], [completed, league]);
  const effectivePerformance = useMemo(() => {
    if (performance) {
      const total = Number(performance.total_predictions ?? 0);
      const correct = Number(performance.correct_predictions ?? 0);
      const inaccurate = deriveIncorrectPredictions(performance);
      return {
        total_predictions: total,
        correct_predictions: correct,
        incorrect_predictions: inaccurate,
        accuracy: total > 0 ? (correct / total) * 100 : 0,
      };
    }
    return { total_predictions: 0, correct_predictions: 0, incorrect_predictions: 0, accuracy: 0 };
  }, [performance]);

  const hasUpcomingError = view === 'upcoming' && upcomingError !== null;
  const hasCompletedError = view === 'completed' && completedError !== null;
  const hasPerformanceError = view === 'completed' && performanceError !== null;

  return <><Header title="試合予測" crumb="試合予測" />
    <div className="tabs"><button className={`tab ${view === 'upcoming' ? 'active' : ''}`} onClick={() => setView('upcoming')}>今後の試合</button><button className={`tab ${view === 'completed' ? 'active' : ''}`} onClick={() => setView('completed')}>終了済み試合</button></div>
    <div className="tabs">{LEAGUE_TABS.map(tab => <button key={tab.label} onClick={() => setLeague(tab.id)} className={`tab ${league === tab.id || (!league && !tab.id) ? 'active' : ''}`}>{tab.label}</button>)}</div>
    {hasUpcomingError ? <ErrorState message={upcomingError ?? '今後の試合の取得に失敗しました。'} /> : view === 'upcoming' ? upcoming === null ? <p>読み込み中...</p> : upcoming.length === 0 ? <EmptyState message="現在、予測対象の試合はありません。" /> : <div className="grid">{upcoming.map(m => <div className="span6" key={m.id}><MatchCard match={m} /></div>)}</div> : <>
      {hasCompletedError ? <ErrorState message={completedError ?? '終了済み試合の取得に失敗しました。'} showBackendHint={false} /> : null}
      {hasPerformanceError ? <ErrorState message={performanceError ?? '成績集計の取得に失敗しました。'} showBackendHint={false} /> : null}
      {completed === null ? <p>読み込み中...</p> : <>
        <div className="card" style={{ marginBottom: 16 }}><b>{league ? 'フィルター中の成績' : '全体成績'}</b><div className="muted">予測記録あり {effectivePerformance.total_predictions}試合 · 的中 {effectivePerformance.correct_predictions} · 不的中 {effectivePerformance.incorrect_predictions} · 的中率 {safePercent(effectivePerformance.accuracy).toFixed(1)}%</div></div>
        {filteredCompleted.length === 0 ? <EmptyState message="終了済み試合データはまだありません" /> : <div className="grid">{filteredCompleted.map(m => <div className="span6" key={m.id}><CompletedCard match={m} /></div>)}</div>}
      </>}
    </>}
  </>;
}
