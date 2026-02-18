import type { TeamRow } from '@/lib/types';

export function KpiStrip({ teams }: { teams: TeamRow[] }) {
  const topComposite = teams[0];
  const topOps = [...teams].sort((a, b) => b.ops - a.ops)[0];
  const topPitch = [...teams].sort((a, b) => a.whip - b.whip)[0];

  return (
    <div className="kpi-grid">
      <div className="card">
        <div className="meta">Composite Leader</div>
        <div className="kpi-value">#{topComposite.composite_rank}</div>
        <div>{topComposite.team_name}</div>
      </div>
      <div className="card">
        <div className="meta">Best Team OPS</div>
        <div className="kpi-value">{topOps.ops.toFixed(3)}</div>
        <div>{topOps.team_name}</div>
      </div>
      <div className="card">
        <div className="meta">Best Team WHIP</div>
        <div className="kpi-value">{topPitch.whip.toFixed(2)}</div>
        <div>{topPitch.team_name}</div>
      </div>
    </div>
  );
}
