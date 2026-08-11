"""Run pipeline with full traceback."""
import subprocess
import sys
import traceback

result = subprocess.run(
    [sys.executable, "-u", "scripts/run_pipeline.py", "--project", "P04", "--days", "7"],
    capture_output=True,
    text=True,
    cwd="c:/Users/ethan/Downloads/project_slim",
    timeout=120,
)

stderr = result.stderr
# Find the actual error (not the data dump)
lines = stderr.split('\n')
error_lines = []
for line in lines:
    if 'Error' in line or 'Error' in line or 'Traceback' in line or 'File "' in line or 'raise' in line or 'duckdb' in line.lower() or 'Constraint' in line or 'constraint' in line:
        error_lines.append(line)

print("=== STDERR (filtered) ===")
for l in error_lines[:30]:
    print(l)

print("\n=== First 20 lines of STDERR ===")
for l in lines[:20]:
    print(l)

print(f"\n=== EXIT CODE: {result.returncode} ===")