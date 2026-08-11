"""Run pipeline with captured output."""
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "scripts/run_pipeline.py", "--project", "P04", "--days", "7"],
    capture_output=True,
    text=True,
    cwd="c:/Users/ethan/Downloads/project_slim",
    timeout=120,
)

print("=== STDOUT ===")
print(result.stdout[-5000:] if len(result.stdout) > 5000 else result.stdout)
print("=== STDERR ===")
print(result.stderr[-5000:] if len(result.stderr) > 5000 else result.stderr)
print(f"=== EXIT CODE: {result.returncode} ===")