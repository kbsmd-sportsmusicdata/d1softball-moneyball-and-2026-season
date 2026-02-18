'use client';

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export function TrendLine({ data }: { data: Array<{ run_date: string; composite_score: number }> }) {
  return (
    <div className="card chart-box">
      <div className="meta">Composite Trend</div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data}>
          <XAxis dataKey="run_date" />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="composite_score" stroke="#cc2f24" strokeWidth={3} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
