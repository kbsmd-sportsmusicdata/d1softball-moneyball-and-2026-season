import { getLatestEdaArtifacts } from '@/lib/data';

function confidenceLabel(value: number): string {
  if (value >= 0.85) return 'High';
  if (value >= 0.7) return 'Medium';
  return 'Watch';
}

export default function EdaPage() {
  const artifacts = getLatestEdaArtifacts();

  if (!artifacts) {
    return (
      <main>
        <h2 className="section-title">EDA Analyst Runs</h2>
        <div className="card">
          <p>No EDA runs found yet.</p>
          <p className="meta">
            Run <code>python3 scripts/eda_analyst_agent.py</code> to generate notebook-style artifacts, then refresh this page.
          </p>
        </div>
      </main>
    );
  }

  const notebookPath = `${artifacts.latest.run_path}/run_log.ipynb`;

  return (
    <main>
      <h2 className="section-title">EDA Analyst Runs</h2>
      <section className="hero">
        <div className="card">
          <div className="meta">Latest Run</div>
          <h3>{artifacts.metadata.run_id}</h3>
          <p className="meta">Label: {artifacts.metadata.run_label}</p>
          <p className="meta">Profile: {artifacts.metadata.config.profile_name}</p>
          <p className="meta">Dataset: {artifacts.metadata.source.dataset_label}</p>
          <p>
            Teams: {artifacts.metadata.source.teams_rows} | Players: {artifacts.metadata.source.players_rows}
          </p>
          <p className="meta">Generated: {artifacts.metadata.generated_at_utc}</p>
          <p className="meta">
            Notebook artifact:{' '}
            <a href={notebookPath} className="inline-link">
              {notebookPath}
            </a>
          </p>
        </div>
        <div className="card">
          <div className="meta">Run Outputs</div>
          <p>Findings: {artifacts.metadata.outputs.findings_count}</p>
          <p>Storyboard steps: {artifacts.metadata.outputs.storyboard_steps}</p>
          <p>Deeper analysis queue: {artifacts.metadata.outputs.deeper_analysis_count}</p>
          {artifacts.metadata.warnings.length > 0 ? (
            <ul className="eda-list">
              {artifacts.metadata.warnings.map((warning) => (
                <li key={warning}>Warning: {warning}</li>
              ))}
            </ul>
          ) : (
            <p className="meta">No run warnings.</p>
          )}
        </div>
      </section>

      <h3 className="section-title">Key Findings</h3>
      <section className="eda-grid">
        {artifacts.findings.map((finding) => (
          <article key={finding.id} className="card eda-card">
            <div className="meta">
              {finding.id} | {finding.category} | {confidenceLabel(finding.confidence)} confidence
            </div>
            <h4>{finding.title}</h4>
            <p>{finding.insight}</p>
            <div className="meta">Audience: {finding.audience_tags.join(', ')}</div>
            <ul className="eda-list">
              {finding.visual_suggestions.map((visual) => (
                <li key={`${finding.id}-${visual.chart_type}-${visual.x}-${visual.y}`}>
                  {visual.chart_type}: {visual.x} vs {visual.y} ({visual.segment})
                </li>
              ))}
            </ul>
          </article>
        ))}
      </section>

      <h3 className="section-title">Storyboard Arc</h3>
      <section className="card">
        <h4>{artifacts.storyboard.arc_title}</h4>
        <ol className="eda-list">
          {artifacts.storyboard.steps.map((step) => (
            <li key={`step-${step.order}`}>
              <strong>{step.order}. {step.step_type}</strong> ({step.finding_id}) {step.narrative}
              <div className="meta">Transition: {step.transition}</div>
            </li>
          ))}
        </ol>
      </section>

      <h3 className="section-title">Deeper Analysis Backlog</h3>
      <section className="card">
        <ul className="eda-list">
          {artifacts.deeperAnalysis.map((item) => (
            <li key={`${item.priority}-${item.question}`}>
              <strong>[{item.priority}] {item.question}</strong>
              <div>{item.importance}</div>
              <div className="meta">Method: {item.method}</div>
              <div className="meta">Needed data: {item.needed_data.join(', ')}</div>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
