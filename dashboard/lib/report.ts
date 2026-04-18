import fs from 'node:fs';
import path from 'node:path';
import type { ManualReport, ManualReportFigureSource } from './types';

const DASHBOARD_ROOT = path.resolve(process.cwd());
const REPO_ROOT = path.resolve(DASHBOARD_ROOT, '..');
const PUBLIC_REPORT_DIR = path.resolve(DASHBOARD_ROOT, 'public', 'reports', 'd1softball_manual_april2026');
const SOURCE_REPORT_DIR = path.resolve(REPO_ROOT, 'reports', 'd1softball_manual_april2026');

function readJson<T>(fullPath: string): T {
  const content = fs.readFileSync(fullPath, 'utf-8');
  return JSON.parse(content) as T;
}

function readText(fullPath: string): string {
  return fs.readFileSync(fullPath, 'utf-8');
}

function resolveReportDir(): string {
  if (fs.existsSync(PUBLIC_REPORT_DIR)) return PUBLIC_REPORT_DIR;
  return SOURCE_REPORT_DIR;
}

export function getManualWorkbookReport(): ManualReport | null {
  const reportDir = resolveReportDir();
  const reportDataPath = path.resolve(reportDir, 'report_data.json');
  const metadataPath = path.resolve(reportDir, 'report_metadata.json');
  if (![reportDataPath, metadataPath].every((item) => fs.existsSync(item))) {
    return null;
  }

  try {
    const report = readJson<ManualReport>(reportDataPath);
    const reportMetadata = readJson<ManualReport['report_metadata']>(metadataPath);
    const figures = report.figures.map((figure: ManualReportFigureSource) => {
      const figurePath = path.resolve(reportDir, 'figures', figure.filename);
      return {
        ...figure,
        svg: fs.existsSync(figurePath) ? readText(figurePath) : '',
      };
    });

    return {
      ...report,
      source_artifacts: {
        ...report.source_artifacts,
        public_bundle_dir: '/reports/d1softball_manual_april2026',
        public_report_markdown_path: '/reports/d1softball_manual_april2026/report.md',
        public_report_metadata_path: '/reports/d1softball_manual_april2026/report_metadata.json',
        public_figures_dir: '/reports/d1softball_manual_april2026/figures',
      },
      figures,
      report_metadata: reportMetadata,
    };
  } catch {
    return null;
  }
}
