import { notFound } from 'next/navigation';
import { TeamRadar } from '@/components/team-radar';
import { TrendLine } from '@/components/trend-line';
import { getPlayers, getTeams, getTrends } from '@/lib/data';

export function generateStaticParams() {
  const teams = getTeams();
  return teams.map((team) => ({ teamId: team.team_id }));
}

export default function TeamProfilePage({ params }: { params: { teamId: string } }) {
  const teams = getTeams();
  const team = teams.find((t) => t.team_id === params.teamId);
  if (!team) {
    notFound();
  }

  const players = getPlayers()
    .filter((p) => p.team_id === team.team_id)
    .sort((a, b) => b.ops - a.ops);

  const trends = getTrends();
  const teamTrend = trends.snapshots
    .map((snap) => ({
      run_date: snap.run_date,
      composite_score: snap.teams.find((t) => t.team_id === team.team_id)?.composite_score ?? team.composite_score,
    }))
    .slice(-12);

  return (
    <main>
      <h2 className="section-title">{team.team_name} Team Profile</h2>
      <div className="hero">
        <div className="card">
          <div className="meta">Composite Rank</div>
          <div className="kpi-value">#{team.composite_rank}</div>
          <div className="meta">Composite Score {team.composite_score.toFixed(3)}</div>
          <p>
            OPS {team.ops.toFixed(3)} | WHIP {team.whip.toFixed(2)} | R/G {team.runs_per_game.toFixed(2)}
          </p>
        </div>
        <TeamRadar
          offense={team.offense_z}
          pitching={team.pitching_z}
          defense={team.defense_z}
          discipline={team.discipline_z}
        />
      </div>

      <h3 className="section-title">Recent Composite Trend</h3>
      <TrendLine data={teamTrend} />

      <h3 className="section-title">Top Players</h3>
      <div className="card table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Player</th>
              <th>Class</th>
              <th>Pos</th>
              <th>AVG</th>
              <th>OPS</th>
              <th>ISO</th>
            </tr>
          </thead>
          <tbody>
            {players.map((player) => (
              <tr key={player.player_id}>
                <td>{player.player_name}</td>
                <td>{player.class_year}</td>
                <td>{player.position}</td>
                <td>{player.avg.toFixed(3)}</td>
                <td>{player.ops.toFixed(3)}</td>
                <td>{player.iso.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
