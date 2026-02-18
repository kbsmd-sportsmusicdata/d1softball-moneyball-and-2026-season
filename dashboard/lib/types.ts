export type TeamRow = {
  season: number;
  run_date: string;
  team_id: string;
  team_name: string;
  conference: string;
  composite_score: number;
  composite_rank: number;
  ops: number;
  whip: number;
  runs_per_game: number;
  offense_z: number;
  pitching_z: number;
  defense_z: number;
  discipline_z: number;
};

export type PlayerRow = {
  season: number;
  run_date: string;
  player_id: string;
  player_name: string;
  team_id: string;
  class_year: string;
  position: string;
  avg: number;
  ops: number;
  iso: number;
};

export type Metadata = {
  schema_version: string;
  run_date: string;
  sources: Array<Record<string, unknown>>;
  warnings: string[];
};
