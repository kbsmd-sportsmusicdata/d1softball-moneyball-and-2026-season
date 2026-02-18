'use client';

import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from 'recharts';

export function TeamRadar({
  offense,
  pitching,
  defense,
  discipline,
}: {
  offense: number;
  pitching: number;
  defense: number;
  discipline: number;
}) {
  const data = [
    { metric: 'Offense', value: offense },
    { metric: 'Pitching', value: pitching },
    { metric: 'Defense', value: defense },
    { metric: 'Discipline', value: discipline },
  ];

  return (
    <div className="card chart-box">
      <div className="meta">Component Radar</div>
      <ResponsiveContainer width="100%" height={250}>
        <RadarChart outerRadius="70%" data={data}>
          <PolarGrid />
          <PolarAngleAxis dataKey="metric" />
          <Radar dataKey="value" fill="#efb321" fillOpacity={0.5} stroke="#cc2f24" />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
