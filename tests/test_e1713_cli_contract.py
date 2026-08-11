from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

EXPECTED_ENTRY_POINTS = {
    "market-ops": "market_ops.cli:main",
    "market-ops-control": "market_ops.product.server:main",
    "market-ops-doctor": "market_ops.product.doctor:main",
}


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = str(SRC_DIR)
    existing = env.get("PYTHONPATH", "")
    if existing:
        pythonpath = f"{pythonpath}{os.pathsep}{existing}"
    env["PYTHONPATH"] = pythonpath
    return env


def _run_cli_module(module: str, args: list[str]) -> subprocess.CompletedProcess:
    """运行 CLI 模块，用 sys.path.append 避免 src/operator 覆盖标准库 operator.

    PYTHONPATH 会把 src/ 放在标准库之前，导致 src/operator 包覆盖
    Python 标准库 operator 模块，引发 circular import。
    用 sys.path.append 把 src/ 放在标准库之后，避免冲突。
    用 runpy.run_module 保持 python -m 的语义（__name__ == '__main__'）。
    """
    script = (
        f"import sys; sys.path.append(r'{SRC_DIR}'); "
        f"import runpy; runpy.run_module('{module}', run_name='__main__')"
    )
    return subprocess.run(
        [sys.executable, "-c", script, *args],
        capture_output=True, text=True, timeout=30,
        cwd=str(PROJECT_ROOT),
    )


# ---------------------------------------------------------------------------
# test_script_entry_points_defined
# ---------------------------------------------------------------------------

def test_script_entry_points_defined():
    """Verify pyproject.toml declares all 3 console_scripts entry points
    with the correct module:function paths."""
    with open(PYPROJECT_PATH, "rb") as fh:
        data = tomllib.load(fh)

    scripts = data["project"]["scripts"]
    for name, expected_path in EXPECTED_ENTRY_POINTS.items():
        assert name in scripts, f"Missing entry point: {name}"
        assert scripts[name] == expected_path, (
            f"Wrong path for {name}: expected {expected_path}, got {scripts[name]}"
        )


# ---------------------------------------------------------------------------
# test_cli_module_importable
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module_name", [
    "market_ops.cli",
    "market_ops.product.server",
    "market_ops.product.doctor",
])
def test_cli_module_importable(module_name: str):
    """Verify each CLI module can be imported without error."""
    try:
        mod = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if module_name == "market_ops.cli" and "Crypto" in str(exc):
            pytest.skip("pycryptodome not installed — known external dependency")
        raise
    assert hasattr(mod, "main"), f"{module_name} is missing main()"


# ---------------------------------------------------------------------------
# test_market_ops_cli_help
# ---------------------------------------------------------------------------

def test_market_ops_cli_help():
    """Running `python -m market_ops.cli --help` must exit 0 and list
    available subcommands."""
    result = _run_cli_module("market_ops.cli", ["--help"])
    if result.returncode != 0 and "Crypto" in result.stderr:
        pytest.skip("pycryptodome not installed — known external dependency")
    assert result.returncode == 0, (
        f"CLI help exited {result.returncode}\nstderr:\n{result.stderr}"
    )
    assert result.stdout, "CLI help produced no output"
    # argparse with required subparsers lists positional arguments
    assert "{" in result.stdout, "CLI help should list subcommand choices"


# ---------------------------------------------------------------------------
# test_market_ops_control_help
# ---------------------------------------------------------------------------

def test_market_ops_control_help():
    """Running `python -m market_ops.product.server --help` must exit 0."""
    result = _run_cli_module("market_ops.product.server", ["--help"])
    assert result.returncode == 0, (
        f"Control help exited {result.returncode}\nstderr:\n{result.stderr}"
    )
    assert "--host" in result.stdout
    assert "--port" in result.stdout


# ---------------------------------------------------------------------------
# test_market_ops_doctor_json_output
# ---------------------------------------------------------------------------

def test_market_ops_doctor_json_output(tmp_path: Path):
    """Running `python -m market_ops.product.doctor --root <tmpdir>` must
    produce valid JSON containing status and version fields."""
    result = _run_cli_module("market_ops.product.doctor", ["--root", str(tmp_path)])
    stdout = result.stdout.strip()
    assert stdout, "Doctor produced no output"

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"Doctor output is not valid JSON (exit={result.returncode})\n"
            f"stdout:\n{stdout}\nstderr:\n{result.stderr}\nerror: {exc}"
        )

    assert "status" in payload, "Doctor JSON missing 'status' field"
    assert "version" in payload, "Doctor JSON missing 'version' field"
    assert isinstance(payload["status"], str)
    assert isinstance(payload["version"], str)
    assert payload["status"] in ("ready", "degraded", "blocked"), (
        f"Unexpected status: {payload['status']}"
    )


__all__ = [
    "test_script_entry_points_defined",
    "test_cli_module_importable",
    "test_market_ops_cli_help",
    "test_market_ops_control_help",
    "test_market_ops_doctor_json_output",
]