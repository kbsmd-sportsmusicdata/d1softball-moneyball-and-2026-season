import fs from 'node:fs';
import path from 'node:path';
import type { Metadata, PlayerRow, TeamRow } from './types';

function readJson<T>(filename: string): T {
  const fullPath = path.resolve(process.cwd(), '..', 'data', 'public', 'latest', filename);
  const content = fs.readFileSync(fullPath, 'utf-8');
  return JSON.parse(content) as T;
}

export function getTeams(): TeamRow[] {
  return readJson<TeamRow[]>('teams.json');
}

export function getPlayers(): PlayerRow[] {
  return readJson<PlayerRow[]>('players.json');
}

export function getMetadata(): Metadata {
  return readJson<Metadata>('metadata.json');
}

export function getTrends(): { snapshots: Array<{ run_date: string; teams: Array<{ team_id: string; team_name: string; composite_score: number; composite_rank: number }> }> } {
  const fullPath = path.resolve(process.cwd(), '..', 'data', 'public', 'history', 'team_trends.json');
  if (!fs.existsSync(fullPath)) {
    return { snapshots: [] };
  }
  const content = fs.readFileSync(fullPath, 'utf-8');
  return JSON.parse(content);
}
