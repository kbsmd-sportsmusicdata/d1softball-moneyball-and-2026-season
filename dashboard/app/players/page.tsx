import { getPlayers, getTeams } from '@/lib/data';

export default function PlayersPage() {
  const teams = getTeams();
  const teamMap = new Map(teams.map((t) => [t.team_id, t.team_name]));
  const players = getPlayers().sort((a, b) => b.ops - a.ops);

  return (
    <main>
      <h2 className="section-title">Player Leaderboard</h2>
      <div className="card table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Player</th>
              <th>Team</th>
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
                <td>{teamMap.get(player.team_id) ?? player.team_id}</td>
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
