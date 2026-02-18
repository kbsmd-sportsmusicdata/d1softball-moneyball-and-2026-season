'use client';

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TeamRow } from '@/lib/types';

export function CompositeChart({ teams }: { teams: TeamRow[] }) {
  const data = teams.slice(0, 10).map((team) => ({
    team: team.team_name,
    score: team.composite_score,
  }));

  return (
    <div className="card chart-box">
      <div className="meta">Top 10 Composite Scores</div>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="4 4" />
          <XAxis dataKey="team" hide />
          <YAxis />
          <Tooltip />
          <Bar dataKey="score" fill="#cc2f24" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
