'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
import {
  LayoutDashboard,
  CalendarRange,
  Trophy,
  Users,
  Shield,
  UserRoundCog,
  Target,
  Database,
  BookOpen,
} from 'lucide-react';
import type { FatigueDetail, MatchPrediction } from '../lib/types';

// ---------------------------------------------------------------------------
// サイドバー / ヘッダー（UI設計書 2.2 / 2.3）
// ---------------------------------------------------------------------------

const NAV_ITEMS = [
  { href: '/', label: 'ダッシュボード', icon: LayoutDashboard },
  { href: '/matches', label: '試合予測', icon: CalendarRange },
  { href: '/leagues/pl/standings', label: '順位表', icon: Trophy },
  { href: '/leagues/pl/rankings', label: '選手ランキング', icon: Users },
  { href: '/teams', label: 'チーム一覧', icon: Shield },
  { href: '/players', label: '選手一覧', icon: Users },
  { href: '/managers', label: '監督一覧', icon: UserRoundCog },
  { href: '/model/performance', label: '予測精度', icon: Target },
  { href: '/data-status', label: 'データ更新状況', icon: Database },
  { href: '/data-sources', label: 'データソース', icon: BookOpen },
] as const;

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="side">
      <div className="brand">
        <span className="ball">⚽</span>
        <div>
          <b>
            Euro Football
            <br className="mobileHide" /> Predictor
          </b>
          <small>欧州5大リーグ予測分析</small>
        </div>
      </div>
      <nav>
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active =
            href === '/'
              ? pathname === '/'
              : label === '順位表'
                ? pathname.startsWith('/leagues/') && pathname.endsWith('/standings')
                : label === '選手ランキング'
                  ? pathname.startsWith('/leagues/') && pathname.endsWith('/rankings')
                  : pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link key={href} href={href} className={active ? 'active' : ''}>
              <Icon size={17} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

export function Header({ title, crumb }: { title: string; crumb?: string }) {
  const now = new Date();
  const seasonStartYear = now.getMonth() >= 6 ? now.getFullYear() : now.getFullYear() - 1;
  const seasonLabel = `${seasonStartYear}/${seasonStartYear + 1}`;

  return (
    <div className="top">
      <div>
        <div className="crumb">ホーム {crumb ? `› ${crumb}` : ''}</div>
        <h1>{title}</h1>
      </div>
      <div className="controls">
        <button type="button">{seasonLabel}⌄</button>
        <button type="button">日本語⌄</button>
        <span className="updated">● データ連携済み</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 画面状態（UI設計書 19章：Loading / Empty / Error / Data Stale）
// ---------------------------------------------------------------------------

export function ErrorState({ message }: { message?: string }) {
  return (
    <div className="card state state-error">
      <p>
        データ取得に失敗しました。バックエンドAPI（{process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}）
        が起動しているか確認してください。
      </p>
      {message && <p className="muted">{message}</p>}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="card state state-empty">
      <p>{message}</p>
    </div>
  );
}

export function StaleBanner() {
  return (
    <div className="stale-banner">
      最終更新から24時間以上経過しています。最新データではない可能性があります。
    </div>
  );
}

// ---------------------------------------------------------------------------
// 汎用パーツ
// ---------------------------------------------------------------------------

export function Crest({ name, color, size = 40 }: { name: string; color?: string; size?: number }) {
  const initials = name
    .split(' ')
    .map((word) => word[0])
    .join('')
    .slice(0, 3);
  return (
    <span
      className="crest"
      style={{ width: size, height: size, background: color || '#334155', fontSize: size * 0.25 }}
    >
      {initials}
    </span>
  );
}

export function TeamCrest({ name, logoUrl, color, size = 40 }: { name: string; logoUrl?: string | null; color?: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  if (!logoUrl || failed) return <Crest name={name} color={color} size={size} />;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={logoUrl}
      alt={`${name} エンブレム`}
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(true)}
      style={{ width: size, height: size, objectFit: 'contain', flex: `0 0 ${size}px` }}
    />
  );
}

export function Form({ value }: { value: string }) {
  return (
    <span className="form">
      {value.split('').map((result, i) => (
        <i key={i} className={result}>
          {result}
        </i>
      ))}
    </span>
  );
}

export function FatigueBadge({ fatigue }: { fatigue: FatigueDetail }) {
  const levelClass = fatigue.level === 'Low' ? 'low' : fatigue.level === 'Medium' ? 'mid' : 'high';
  return (
    <span className={`fatigue ${levelClass}`}>
      {fatigue.index}/100 · {fatigue.level}
    </span>
  );
}

export function Probability({ match }: { match: MatchPrediction }) {
  return (
    <div>
      <div className="prob">
        <div style={{ width: `${match.home_win_probability}%` }} className="home">
          {match.home_win_probability}%
        </div>
        <div style={{ width: `${match.draw_probability}%` }} className="draw">
          {match.draw_probability}%
        </div>
        <div style={{ width: `${match.away_win_probability}%` }} className="away">
          {match.away_win_probability}%
        </div>
      </div>
      <p
        title="確率校正を採用すると引き分け検出性能が大きく低下したため、現在は未校正モデルを使用しています。"
        style={{
          margin: '6px 0 0',
          color: 'var(--muted, #64748b)',
          fontSize: '0.75rem',
          lineHeight: 1.4,
          textAlign: 'right',
        }}
      >
        ※ モデル出力による未校正の参考確率です
      </p>
    </div>
  );
}

export function MatchCard({ match }: { match: MatchPrediction }) {
  const kickoff = new Date(match.kickoff);
  const dateLabel = kickoff.toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric', weekday: 'short' });
  const timeLabel = kickoff.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });

  return (
    <Link href={`/matches/${match.id}`} className="match card">
      <div className="muted">
        {dateLabel} {timeLabel}
        <span>{match.league_name}</span>
      </div>
      <div className="versus">
        <div>
          <TeamCrest name={match.home_team.name} logoUrl={match.home_team.logo_url} color={match.home_team.color} />
          <b>{match.home_team.name}</b>
        </div>
        <em>VS</em>
        <div>
          <TeamCrest name={match.away_team.name} logoUrl={match.away_team.logo_url} color={match.away_team.color} />
          <b>{match.away_team.name}</b>
        </div>
      </div>
      <Probability match={match} />
      <div className="prediction">
        予測：<b>{match.predicted_result}</b>
        <span>信頼度 {match.confidence}</span>
      </div>
    </Link>
  );
}

export function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <b>{value}</b>
      {sub && <small>{sub}</small>}
    </div>
  );
}

export function StatusDot({ status }: { status: string }) {
  return <span className={`status ${status}`}>{status}</span>;
}
