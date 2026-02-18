import { CompositeChart } from '@/components/composite-chart';
import { KpiStrip } from '@/components/kpi-strip';
import { TeamTable } from '@/components/team-table';
import { getMetadata, getTeams } from '@/lib/data';

export default function HomePage() {
  const teams = getTeams();
  const metadata = getMetadata();

  return (
    <main>
      <section className="hero">
        <KpiStrip teams={teams} />
        <div className="card">
          <div className="meta">Last Updated</div>
          <h3>{metadata.run_date}</h3>
          <div className="badge">
            <span className="badge-dot" />
            Schema {metadata.schema_version}
          </div>
          <p className="meta">Top 25 by ESPN/USA Softball. Team + player metrics with weighted composite model.</p>
        </div>
      </section>

      <h2 className="section-title">Composite Leaderboard</h2>
      <CompositeChart teams={teams} />

      <h2 className="section-title">Team Table</h2>
      <TeamTable teams={teams} />
    </main>
  );
}
