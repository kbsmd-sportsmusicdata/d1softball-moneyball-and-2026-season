import json
import subprocess
from pathlib import Path


def test_manual_report_build_writes_notebook_html(tmp_path: Path):
    output_dir = tmp_path / "reports" / "d1softball_manual_april2026"
    cmd = [
        "python3",
        "scripts/build_d1softball_manual_report.py",
        "--output-dir",
        str(output_dir),
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    notebook_path = output_dir / "notebook.html"
    report_data_path = output_dir / "report_data.json"

    assert notebook_path.exists()
    assert report_data_path.exists()

    html = notebook_path.read_text()
    report_data = json.loads(report_data_path.read_text())

    assert "Manual workbook / April 2026" in html
    assert "Why this matters" in html
    assert "Texas Tech" in html
    assert "notebook.html" in html
    assert report_data["source_artifacts"]["public_notebook_path"].endswith("/notebook.html")
