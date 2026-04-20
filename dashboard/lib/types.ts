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

export type EDALatestPointer = {
  schema_version: string;
  run_id: string;
  run_path: string;
  generated_at_utc: string;
};

export type EDAVisualSuggestion = {
  chart_type: string;
  x: string;
  y: string;
  segment: string;
  why: string;
};

export type EDAFinding = {
  id: string;
  title: string;
  category: string;
  insight: string;
  evidence: Record<string, unknown>;
  confidence: number;
  audience_tags: string[];
  visual_suggestions: EDAVisualSuggestion[];
  provenance: Record<string, unknown>;
};

export type EDAStoryboard = {
  arc_title: string;
  audience_tags: string[];
  steps: Array<{
    order: number;
    finding_id: string;
    step_type: string;
    narrative: string;
    transition: string;
  }>;
};

export type EDADeeperAnalysisItem = {
  question: string;
  importance: string;
  needed_data: string[];
  method: string;
  priority: string;
};

export type EDAArtifacts = {
  latest: EDALatestPointer;
  metadata: EDARunMetadata;
  findings: EDAFinding[];
  storyboard: EDAStoryboard;
  deeperAnalysis: EDADeeperAnalysisItem[];
};

export type ManualReportFigureSource = {
  filename: string;
  title: string;
  caption: string;
  alt: string;
};

export type ManualReportFigure = ManualReportFigureSource & {
  svg: string;
};

export type ManualReportScoreboardRow = {
  team: string;
  composite: number;
  ops: number;
  era: number | null;
  has_pitching: boolean;
  rpi: number | null;
};

export type ManualReport = {
  schema_version: string;
  report_id: string;
  title: string;
  subtitle: string;
  intro_note: string;
  generated_at_utc: string;
  at_a_glance: Array<{
    label: string;
    value: number | string;
  }>;
  executive_summary: string;
  key_scoreboard: ManualReportScoreboardRow[];
  storyboard: {
    arc_title: string;
    audience_tags: string[];
    steps: Array<{
      order: number;
      finding_id: string;
      step_type: string;
      title: string;
      narrative: string;
      transition: string;
    }>;
  };
  findings: EDAFinding[];
  deeper_analysis: EDADeeperAnalysisItem[];
  figures: ManualReportFigure[];
  data_notes: string[];
  source_artifacts: {
    eda_run_dir: string;
    report_dir: string;
    report_markdown_path: string;
    report_metadata_path: string;
    report_notebook_path: string;
    public_bundle_dir: string;
    public_notebook_path: string;
    public_report_markdown_path: string;
    public_report_metadata_path: string;
    public_figures_dir: string;
  };
  coverage: {
    team_rows: number;
    player_rows: number;
    teams_with_pitching: number;
    composite_vs_rpi_correlation: number;
  };
  report_metadata: {
    teams_path: string;
    players_path: string;
    rpi_path: string;
    eda_run_dir: string;
    figure_count: number;
  };
};

export type EDARunMetadata = {
  schema_version: string;
  run_id: string;
  run_label: string;
  generated_at_utc: string;
  source: {
    mode: string;
    profile_name: string;
    dataset_label: string;
    dataset_version: string | null;
    source_root: string;
    teams_path: string;
    players_path: string;
    teams_rows: number;
    players_rows: number;
  };
  config: {
    profile_name: string;
    max_findings: number;
    llm_enabled: boolean;
    llm_model: string;
    qualification_rules: Array<Record<string, unknown>>;
  };
  outputs: {
    findings_count: number;
    storyboard_steps: number;
    deeper_analysis_count: number;
  };
  warnings: string[];
};
