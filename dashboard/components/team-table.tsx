import Link from 'next/link';
import type { TeamRow } from '@/lib/types';

export function TeamTable({ teams }: { teams: TeamRow[] }) {
  return (
    <div className="card table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Team</th>
            <th>Composite</th>
            <th>OPS</th>
            <th>WHIP</th>
            <th>R/G</th>
          </tr>
        </thead>
        <tbody>
          {teams.map((team) => (
            <tr key={team.team_id}>
              <td>{team.composite_rank}</td>
              <td>
                <Link href={`/team/${team.team_id}/`}>{team.team_name}</Link>
              </td>
              <td>{team.composite_score.toFixed(3)}</td>
              <td>{team.ops.toFixed(3)}</td>
              <td>{team.whip.toFixed(2)}</td>
              <td>{team.runs_per_game.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
