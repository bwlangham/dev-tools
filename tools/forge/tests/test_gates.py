from pathlib import Path

from forge.gates import OUTPUT_LIMIT, failures_summary, run_gates
from forge.task import GateResult


def test_passing_and_failing_gates(tmp_path: Path):
    gates = {"pass": "true", "fail": "echo boom; false"}
    results = run_gates(gates, tmp_path)
    by_name = {g.name: g for g in results}
    assert by_name["pass"].passed is True
    assert by_name["fail"].passed is False
    assert "boom" in by_name["fail"].output


def test_gates_run_in_cwd(tmp_path: Path):
    (tmp_path / "marker").write_text("x")
    results = run_gates({"check": "test -f marker"}, tmp_path)
    assert results[0].passed is True


def test_output_is_truncated(tmp_path: Path):
    results = run_gates({"big": "head -c 100000 /dev/zero | tr '\\0' 'a'"}, tmp_path)
    assert len(results[0].output) <= OUTPUT_LIMIT


def test_failures_summary_only_failures():
    results = [
        GateResult("lint", True, ""),
        GateResult("test", False, "assertion failed"),
    ]
    summary = failures_summary(results)
    assert "lint" not in summary
    assert "test" in summary
    assert "assertion failed" in summary


def test_failures_summary_empty_when_all_pass():
    results = [GateResult("lint", True, ""), GateResult("test", True, "")]
    assert failures_summary(results) == ""
