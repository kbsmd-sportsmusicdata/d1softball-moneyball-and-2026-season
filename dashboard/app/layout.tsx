import './globals.css';
import Link from 'next/link';
import type { ReactNode } from 'react';

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="page-shell">
          <header className="topbar">
            <Link href="/" className="brand">
              D1 SOFTBALL STATBOOK
            </Link>
            <nav className="nav">
              <Link href="/">Overview</Link>
              <Link href="/players">Players</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
