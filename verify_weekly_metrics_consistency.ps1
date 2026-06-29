$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = "C:\Users\ethan\AppData\Local\Programs\Python\Python310\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$runtimeDir = Join-Path $root "output\runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$tempPy = Join-Path $runtimeDir "verify_weekly_metrics_consistency_tmp.py"

$script = @'
import json
import re
from pathlib import Path

active = Path("output/active")

def latest(pattern: str) -> Path:
    files = sorted(active.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit(f"missing file for pattern: {pattern}")
    return files[0]

pre_send_path = latest("pre_send_summary_*.json")
summary_path = latest("card_preview_summary_*.json")
market_path = latest("card_preview_market_*.json")

pre_send = json.loads(pre_send_path.read_text(encoding="utf-8"))
summary = json.loads(summary_path.read_text(encoding="utf-8"))
market = json.loads(market_path.read_text(encoding="utf-8"))

pre_send_text = json.dumps(pre_send, ensure_ascii=False)
summary_text = json.dumps(summary, ensure_ascii=False)
market_text = json.dumps(market, ensure_ascii=False)

def pick_required(values: list[str], text: str) -> str:
    for value in values:
        if value in text:
            return value
    return ""

# Use final published company metrics that should appear in all deliverables.
expected_spend = pick_required(["15937", "15933", "15930"], pre_send_text)
expected_revenue = pick_required(["23414", "23407", "23405"], pre_send_text)
expected_roi = pick_required(["1.47", "1.54"], pre_send_text)

if not (expected_spend and expected_revenue and expected_roi):
    raise SystemExit("could not infer expected company metrics from pre_send_summary")

checks = [
    ("summary spend", expected_spend, summary_text),
    ("summary revenue", expected_revenue, summary_text),
    ("summary roi", expected_roi, summary_text),
    ("market spend", expected_spend, market_text),
    ("market revenue", expected_revenue, market_text),
    ("market roi", expected_roi, market_text),
]

failures = []
for label, value, haystack in checks:
    if value not in haystack:
        failures.append(f"{label} missing expected value {value}")

report_lines = [
    "# Weekly Metrics Consistency",
    "",
    f"Status: {'PASS' if not failures else 'FAIL'}",
    f"Pre-send summary: {pre_send_path}",
    f"Summary card: {summary_path}",
    f"Market card: {market_path}",
    "",
    "Expected company metrics:",
    f"- spend: {expected_spend}",
    f"- revenue: {expected_revenue}",
    f"- roi: {expected_roi}",
    "",
]

if failures:
    report_lines.append("Failures:")
    report_lines.extend(f"- {item}" for item in failures)
else:
    report_lines.append("All company metrics matched across checked artifacts.")

out_md = active / "weekly_metrics_consistency_latest.md"
out_json = active / "weekly_metrics_consistency_latest.json"
payload = {
    "passed": not failures,
    "expected": {
        "spend": expected_spend,
        "revenue": expected_revenue,
        "roi": expected_roi,
    },
    "files": {
        "pre_send_summary": str(pre_send_path),
        "summary_card": str(summary_path),
        "market_card": str(market_path),
    },
    "failures": failures,
}
out_md.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

print(out_md)
if failures:
    raise SystemExit(1)
'@

[System.IO.File]::WriteAllText($tempPy, $script, (New-Object System.Text.UTF8Encoding($false)))
& $python $tempPy
if ($LASTEXITCODE -ne 0) {
    throw "weekly metrics consistency check failed"
}
