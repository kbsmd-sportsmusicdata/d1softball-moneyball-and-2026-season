import Link from 'next/link';
import { getManualWorkbookReport } from '@/lib/report';
import type { EDAFinding } from '@/lib/types';

function formatNumber(value: number | null | string, digits = 3): string {
  if (value === null || value === undefined) return 'n/a';
  if (typeof value === 'string') return value;
  if (Number.isNaN(value)) return 'n/a';
  return value.toFixed(digits);
}

function confidenceLabel(value: number): string {
  if (value >= 0.85) return 'High';
  if (value >= 0.7) return 'Medium';
  return 'Watch';
}

function provenanceSummary(provenance: EDAFinding['provenance']): string {
  const parts: string[] = [];
  if (typeof provenance.generation === 'string') parts.push(provenance.generation);
  if (Array.isArray(provenance.metrics_used) && provenance.metrics_used.length > 0) {
    parts.push(`${provenance.metrics_used.length} metrics`);
  }
  return parts.length > 0 ? parts.join(' · ') : 'Workbook-derived';
}

function valueToText(value: unknown): string {
  if (Array.isArray(value)) return value.map((entry) => String(entry)).join(', ');
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (value === null || value === undefined) return 'n/a';
  return String(value);
}

export default function ReportPage() {
  const report = getManualWorkbookReport();

  if (!report) {
    return (
      <main className="report-page">
        <section className="report-hero report-hero-empty">
          <div>
            <div className="report-eyebrow">Manual workbook report</div>
            <h1>Report not found yet</h1>
            <p>
              Run <code>make report</code> to regenerate the markdown, figures, and dashboard payload for the manual
              workbook import.
            </p>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="report-page">
      <section className="report-hero">
        <div className="report-hero-copy">
          <div className="report-eyebrow">Manual workbook / April 2026</div>
          <h1>{report.title}</h1>
          <p className="report-subtitle">{report.subtitle}</p>
          <p className="report-intro-note">{report.intro_note}</p>

          <div className="report-badges">
            <span className="report-badge">Schema {report.schema_version}</span>
            <span className="report-badge">Generated {report.generated_at_utc}</span>
            <span className="report-badge">Notebooks + markdown + SVG charts</span>
          </div>

          <div className="report-method-callout">
            <strong>Method note.</strong> Player batting and player pitching do not need to overlap for this workbook to
            be useful. They are treated as complementary slices rather than a single joined table.
          </div>
        </div>

        <aside className="report-hero-panel">
          <div className="report-panel-heading">
            <span className="meta">At a Glance</span>
            <span className="report-panel-path">Notebook-style output</span>
          </div>
          <div className="report-kpi-grid">
            {report.at_a_glance.map((metric) => (
              <article key={metric.label} className="report-kpi">
                <div className="meta">{metric.label}</div>
                <div className="report-kpi-value">{valueToText(metric.value)}</div>
              </article>
            ))}
          </div>
        </aside>
      </section>

      <section className="report-section">
        <div className="section-title-wrap">
          <div className="section-kicker">Executive Summary</div>
          <h2>How the workbook reads at the top end</h2>
        </div>
        <div className="report-two-col">
          <article className="card report-summary-card">
            <p>{report.executive_summary}</p>
            <div className="report-mini-grid">
              <div>
                <div className="meta">Notebook viewer</div>
                <div className="report-mini-value">
                  <Link href="/eda" className="inline-link">
                    Open analyst run viewer
                  </Link>
                </div>
              </div>
              <div>
                <div className="meta">Static bundle</div>
                <div className="report-mini-value code-inline">{report.source_artifacts.public_bundle_dir}</div>
              </div>
            </div>
          </article>

          <article className="card report-summary-card">
            <div className="meta">What the reader should know</div>
            <ul className="report-bullets">
              <li>The composite ranking and the RPI ranking are related, but not interchangeable.</li>
              <li>Tennessee’s prevention profile is the cleanest innings-qualified staff story in the workbook.</li>
              <li>The top player board is top-heavy enough to make the individual leaderboard meaningful.</li>
              <li>Coverage gaps matter, so this report keeps batting and pitching views separate where needed.</li>
            </ul>
          </article>
        </div>
      </section>

      <section className="report-section">
        <div className="section-title-wrap">
          <div className="section-kicker">Key Scoreboard</div>
          <h2>Top five by composite score</h2>
        </div>
        <div className="card table-wrap report-table-card">
          <table className="table report-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Team</th>
                <th>Composite</th>
                <th>OPS</th>
                <th>ERA</th>
                <th>RPI</th>
              </tr>
            </thead>
            <tbody>
              {report.key_scoreboard.map((row, index) => (
                <tr key={row.team}>
                  <td>{index + 1}</td>
                  <td>{row.team}</td>
                  <td>{formatNumber(row.composite)}</td>
                  <td>{formatNumber(row.ops)}</td>
                  <td>{formatNumber(row.has_pitching ? row.era : null, 2)}</td>
                  <td>{formatNumber(row.rpi, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="report-section">
        <div className="section-title-wrap">
          <div className="section-kicker">Figures</div>
          <h2>Editorial charts from the workbook</h2>
        </div>
        <div className="report-figure-grid">
          {report.figures.map((figure) => (
            <article key={figure.filename} className="card report-figure-card">
              <div className="meta">{figure.title}</div>
              <div className="report-figure-frame" aria-label={figure.alt} dangerouslySetInnerHTML={{ __html: figure.svg }} />
              <p className="report-figure-caption">{figure.caption}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="report-section">
        <div className="section-title-wrap">
          <div className="section-kicker">Storyboard</div>
          <h2>{report.storyboard.arc_title}</h2>
        </div>
        <div className="report-storyboard">
          {report.storyboard.steps.map((step) => (
            <article key={`${step.order}-${step.finding_id}`} className="card report-step-card">
              <div className="report-step-topline">
                <span className="report-step-number">{step.order}</span>
                <span className="report-step-type">{step.step_type}</span>
                <span className="report-step-finding">{step.finding_id}</span>
              </div>
              <h3>{step.title}</h3>
              <p>{step.narrative}</p>
              <div className="report-step-transition">{step.transition}</div>
            </article>
          ))}
        </div>
      </section>

      <section className="report-section">
        <div className="section-title-wrap">
          <div className="section-kicker">Findings</div>
          <h2>8 publishable insights</h2>
        </div>
        <div className="report-finding-grid">
          {report.findings.map((finding) => (
            <article key={finding.id} className="card report-finding-card">
              <div className="report-finding-head">
                <div className="report-finding-meta">
                  <span className="report-pill">{finding.id}</span>
                  <span className="report-pill">{finding.category}</span>
                  <span className="report-pill">{confidenceLabel(finding.confidence)} confidence</span>
                </div>
                <div className="report-provenance">{provenanceSummary(finding.provenance)}</div>
              </div>

              <h3>{finding.title}</h3>
              <p className="report-insight">{finding.insight}</p>

              <div className="report-subsection">
                <div className="meta">Audience</div>
                <div className="report-tag-row">
                  {finding.audience_tags.map((tag) => (
                    <span key={tag} className="report-tag">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              <div className="report-subsection">
                <div className="meta">Evidence</div>
                <dl className="report-evidence">
                  {Object.entries(finding.evidence).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key}</dt>
                      <dd>{valueToText(value)}</dd>
                    </div>
                  ))}
                </dl>
              </div>

              <div className="report-subsection">
                <div className="meta">Visual suggestions</div>
                <ul className="report-visuals">
                  {finding.visual_suggestions.map((visual) => (
                    <li key={`${finding.id}-${visual.chart_type}-${visual.segment}`}>
                      <strong>{visual.chart_type}</strong> {visual.x} vs {visual.y} ({visual.segment}) — {visual.why}
                    </li>
                  ))}
                </ul>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="report-section">
        <div className="section-title-wrap">
          <div className="section-kicker">Deep Dive Queue</div>
          <h2>What to study next</h2>
        </div>
        <div className="report-analysis-grid">
          {report.deeper_analysis.map((item) => (
            <article key={item.question} className="card report-analysis-card">
              <span className="report-analysis-priority">{item.priority}</span>
              <h3>{item.question}</h3>
              <p>{item.importance}</p>
              <div className="report-subsection">
                <div className="meta">Needed data</div>
                <p className="report-mini-copy">{item.needed_data.join(', ')}</p>
              </div>
              <div className="report-subsection">
                <div className="meta">Method</div>
                <p className="report-mini-copy">{item.method}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="report-section">
        <div className="section-title-wrap">
          <div className="section-kicker">Source Notes</div>
          <h2>Coverage and artifact trail</h2>
        </div>
        <div className="report-two-col">
          <article className="card report-summary-card">
            <div className="meta">Data notes</div>
            <ul className="report-bullets">
              {report.data_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </article>

          <article className="card report-summary-card">
            <div className="meta">Source artifacts</div>
            <dl className="report-meta-list">
              <div>
                <dt>Public bundle</dt>
                <dd className="code-inline">{report.source_artifacts.public_bundle_dir}</dd>
              </div>
              <div>
                <dt>Public markdown</dt>
                <dd className="code-inline">{report.source_artifacts.public_report_markdown_path}</dd>
              </div>
              <div>
                <dt>Public metadata</dt>
                <dd className="code-inline">{report.source_artifacts.public_report_metadata_path}</dd>
              </div>
              <div>
                <dt>Public figures</dt>
                <dd className="code-inline">{report.source_artifacts.public_figures_dir}</dd>
              </div>
              <div>
                <dt>Report directory</dt>
                <dd className="code-inline">{report.source_artifacts.report_dir}</dd>
              </div>
            </dl>
            <div className="report-meta-foot">
              Figures: {report.report_metadata.figure_count} | Dataset rows: {report.coverage.team_rows} teams /{' '}
              {report.coverage.player_rows} players
            </div>
          </article>
        </div>
      </section>
    </main>
  );
}
