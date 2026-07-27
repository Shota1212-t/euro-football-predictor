import './globals.css';
import type { Metadata } from 'next';
import { Sidebar } from './components/ui';

export const metadata: Metadata = {
  title: 'Euro Football Predictor',
  description: '欧州5大リーグ予測分析プラットフォーム',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>
        <Sidebar />
        <main className="main">{children}</main>
      </body>
    </html>
  );
}
