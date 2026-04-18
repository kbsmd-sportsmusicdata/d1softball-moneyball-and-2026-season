import fs from 'node:fs';
import path from 'node:path';
import type {
  EDAArtifacts,
  EDADeeperAnalysisItem,
  EDAFinding,
  EDALatestPointer,
  EDARunMetadata,
  EDAStoryboard,
  Metadata,
  PlayerRow,
  TeamRow,
} from './types';

const REPO_ROOT = path.resolve(process.cwd(), '..');
type TeamTrends = {
  snapshots: Array<{
    run_date: string;
    teams: Array<{ team_id: string; team_name: string; composite_score: number; composite_rank: number }>;
  }>;
};

function readJson<T>(fullPath: string): T {
  const content = fs.readFileSync(fullPath, 'utf-8');
  return JSON.parse(content) as T;
}

function readLatestPublicJson<T>(filename: string): T {
  const fullPath = path.resolve(REPO_ROOT, 'data', 'public', 'latest', filename);
  return readJson<T>(fullPath);
}

export function getTeams(): TeamRow[] {
  return readLatestPublicJson<TeamRow[]>('teams.json');
}

export function getPlayers(): PlayerRow[] {
  return readLatestPublicJson<PlayerRow[]>('players.json');
}

export function getMetadata(): Metadata {
  return readLatestPublicJson<Metadata>('metadata.json');
}

export function getTrends(): TeamTrends {
  const fullPath = path.resolve(REPO_ROOT, 'data', 'public', 'history', 'team_trends.json');
  if (!fs.existsSync(fullPath)) {
    return { snapshots: [] };
  }
  return readJson<TeamTrends>(fullPath);
}

function resolveEdaRunDir(latest: EDALatestPointer): string {
  if (path.isAbsolute(latest.run_path)) {
    return latest.run_path;
  }
  return path.resolve(REPO_ROOT, latest.run_path);
}

export function getLatestEdaArtifacts(): EDAArtifacts | null {
  const latestPath = path.resolve(REPO_ROOT, 'eda_runs', 'latest.json');
  if (!fs.existsSync(latestPath)) {
    return null;
  }

  try {
    const latest = readJson<EDALatestPointer>(latestPath);
    const runDir = resolveEdaRunDir(latest);

    const metadataPath = path.resolve(runDir, 'run_metadata.json');
    const findingsPath = path.resolve(runDir, 'findings.json');
    const storyboardPath = path.resolve(runDir, 'storyboard.json');
    const deeperPath = path.resolve(runDir, 'deeper_analysis.json');

    if (![metadataPath, findingsPath, storyboardPath, deeperPath].every((p) => fs.existsSync(p))) {
      return null;
    }

    return {
      latest,
      metadata: readJson<EDARunMetadata>(metadataPath),
      findings: readJson<EDAFinding[]>(findingsPath),
      storyboard: readJson<EDAStoryboard>(storyboardPath),
      deeperAnalysis: readJson<EDADeeperAnalysisItem[]>(deeperPath),
    };
  } catch {
    return null;
  }
}
