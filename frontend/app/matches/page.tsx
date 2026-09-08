'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
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
  const [error, setError] = useState(false);
  useEffect(() => { let active=true; setError(false); (async () => {
    if (view==='upcoming') { const data=await api.matches({league}); if(!active)return; setUpcoming(data); setError(data===null); }
    else { const [rows, perf]=await Promise.all([api.completedMatches(), api.completedPerformance()]); if(!active)return; setCompleted(rows); setPerformance(perf); setError(rows===null || perf===null); }
  })(); return ()=>{active=false}; }, [view, league]);
  const filteredCompleted = useMemo(() => completed?.filter(m => !league || m.league_id===league) ?? [], [completed, league]);
  const scoped = useMemo(() => { const recorded=filteredCompleted.filter(x=>x.prediction_available && x.prediction_status==='recorded'); const correct=recorded.filter(x=>x.is_correct).length; return {total:recorded.length,correct,accuracy:recorded.length ? correct/recorded.length*100 : 0}; }, [filteredCompleted]);
  return <><Header title="試合予測" crumb="試合予測" />
    <div className="tabs"><button className={`tab ${view==='upcoming'?'active':''}`} onClick={()=>setView('upcoming')}>今後の試合</button><button className={`tab ${view==='completed'?'active':''}`} onClick={()=>setView('completed')}>終了済み試合</button></div>
    <div className="tabs">{LEAGUE_TABS.map(tab=><button key={tab.label} onClick={()=>setLeague(tab.id)} className={`tab ${league===tab.id || (!league&&!tab.id)?'active':''}`}>{tab.label}</button>)}</div>
    {error ? <ErrorState message="試合データの取得に失敗しました。" /> : view==='upcoming' ? upcoming===null ? <p>読み込み中...</p> : upcoming.length===0 ? <EmptyState message="現在、予測対象の試合はありません。" /> : <div className="grid">{upcoming.map(m=><div className="span6" key={m.id}><MatchCard match={m}/></div>)}</div> : completed===null ? <p>読み込み中...</p> : <>
      <div className="card" style={{ marginBottom: 16 }}><b>{league ? 'フィルター中の成績' : '全体成績'}</b><div className="muted">予測記録あり {scoped.total}試合 · 的中 {scoped.correct} · 不的中 {scoped.total-scoped.correct} · 的中率 {scoped.accuracy.toFixed(1)}%</div></div>
      {filteredCompleted.length===0 ? <EmptyState message="終了済み試合はありません。"/> : <div className="grid">{filteredCompleted.map(m=><div className="span6" key={m.id}><CompletedCard match={m}/></div>)}</div>}
    </>}
  </>;
}
