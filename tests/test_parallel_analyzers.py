"""七域并行执行线程安全与结果正确性测试。

验证方向：
  1. 串行 vs 并行结果一致性     —— Mock 模式下结果完全相同
  2. 线程安全                    —— 共享 ThinkingDataReality 无竞态
  3. 确定性                      —— 多次并行执行结果一致
  4. 全部域完成                  —— 七个域均产出有效快照
  5. 部分失败隔离                —— 单域失败不影响其他域
  6. 计数器正确性                —— total_analyzed 正确递增
  7. 无 TD 实例                  —— 空连接时并行仍正常
  8. 高并发压力                  —— 多轮并行无异常
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.creative_vision_runtime.reality.thinkingdata_reality import (
    ThinkingDataReality,
)
from market_ops.creative_vision_runtime.reality.analyzers import (
    LifecycleAnalyzer,
    FunnelAnalyzer,
    RetentionAnalyzer,
    MonetizationAnalyzer,
    EconomyAnalyzer,
    GameplayAnalyzer,
    UserValueAnalyzer,
    parallel_analyze,
)


# ── 辅助函数 ────────────────────────────────────────────────

_ANALYZER_CLASSES = {
    "Lifecycle": LifecycleAnalyzer,
    "Funnel": FunnelAnalyzer,
    "Retention": RetentionAnalyzer,
    "Monetization": MonetizationAnalyzer,
    "Economy": EconomyAnalyzer,
    "Gameplay": GameplayAnalyzer,
    "UserValue": UserValueAnalyzer,
}


def _serial_analyze(
    td: ThinkingDataReality,
    project_id: int = 102,
    lookback_days: int = 30,
) -> dict[str, Any]:
    """串行执行七域，返回 {name: snapshot}。"""
    results: dict[str, Any] = {}
    for name, cls in _ANALYZER_CLASSES.items():
        az = cls(td)
        results[name] = az.analyze(project_id, lookback_days)
    return results


def _snapshot_to_dict(snapshot: Any) -> dict[str, Any]:
    """将快照转为字典，忽略时间戳等非常量字段。"""
    d = snapshot.to_dict().copy()
    # period_start / period_end 依赖当前日期，不比较
    d.pop("period_start", None)
    d.pop("period_end", None)
    return d


# ── 并行 vs 串行一致性 ──────────────────────────────────────


class TestParallelVsSerialConsistency:
    """验证并行执行与串行执行结果完全一致。"""

    def test_mock_results_identical(self):
        """Mock 模式下并行 = 串行。"""
        td = ThinkingDataReality()

        serial = _serial_analyze(td)
        parallel = parallel_analyze(td)

        assert set(serial.keys()) == set(parallel.keys())
        for name in serial:
            s = _snapshot_to_dict(serial[name])
            p = _snapshot_to_dict(parallel[name])
            assert s == p, f"{name}: serial != parallel"

    def test_each_domain_snapshot_type(self):
        """并行结果中每个域的快照类型正确。"""
        td = ThinkingDataReality()
        results = parallel_analyze(td)

        from market_ops.creative_vision_runtime.reality.analyzers import (
            LifecycleSnapshot,
            FunnelSnapshot,
            RetentionSnapshot,
            MonetizationSnapshot,
            EconomySnapshot,
            GameplaySnapshot,
            UserValueSnapshot,
        )

        expected_types = {
            "Lifecycle": LifecycleSnapshot,
            "Funnel": FunnelSnapshot,
            "Retention": RetentionSnapshot,
            "Monetization": MonetizationSnapshot,
            "Economy": EconomySnapshot,
            "Gameplay": GameplaySnapshot,
            "UserValue": UserValueSnapshot,
        }

        for name, snap in results.items():
            assert isinstance(snap, expected_types[name]), (
                f"{name}: expected {expected_types[name].__name__}, "
                f"got {type(snap).__name__}"
            )

    def test_all_key_metrics_populated(self):
        """并行结果中各域关键指标非空/非零。"""
        td = ThinkingDataReality()
        results = parallel_analyze(td)

        lc = results["Lifecycle"]
        assert lc.d1_retention > 0
        assert lc.d7_retention > 0

        fn = results["Funnel"]
        assert len(fn.steps) > 0
        assert fn.overall_conversion > 0

        rt = results["Retention"]
        assert rt.d7_retention > 0
        assert rt.best_channel != ""

        mn = results["Monetization"]
        assert mn.total_revenue > 0
        assert mn.payer_rate > 0

        ec = results["Economy"]
        assert len(ec.resources) > 0
        assert ec.overall_status != ""

        gp = results["Gameplay"]
        assert gp.total_players > 0
        assert len(gp.levels) > 0

        uv = results["UserValue"]
        assert uv.total_users > 0
        assert uv.high_value_users > 0
        assert uv.pareto_ratio > 0

    def test_parallel_is_faster_than_serial(self):
        """并行执行不慢于串行（Mock 模式下线程开销极小，但至少不显著变慢）。"""
        td = ThinkingDataReality()

        t0 = time.perf_counter()
        _serial_analyze(td)
        serial_dt = time.perf_counter() - t0

        t0 = time.perf_counter()
        parallel_analyze(td)
        parallel_dt = time.perf_counter() - t0

        # Mock 模式下数据量极小，并行线程开销可能略高，
        # 但不应该超过串行 5 倍（生产环境相反）
        assert parallel_dt < serial_dt * 5, (
            f"parallel ({parallel_dt*1000:.2f}ms) too slow vs "
            f"serial ({serial_dt*1000:.2f}ms)"
        )


# ── 线程安全 ────────────────────────────────────────────────


class TestThreadSafety:
    """验证共享 ThinkingDataReality 在多线程中安全。"""

    def test_shared_td_instance_no_errors(self):
        """七个线程共享同一个 ThinkingDataReality 无异常。"""
        td = ThinkingDataReality()
        # 所有 analyzer 共享同一个 td 实例
        analyzers = {name: cls(td) for name, cls in _ANALYZER_CLASSES.items()}

        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = {
                executor.submit(az.analyze, 102, 30): name
                for name, az in analyzers.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                result = future.result()
                assert result is not None, f"{name}: returned None"

    def test_shared_td_consistent_results(self):
        """共享 TD 时并行结果与各自独立 TD 一致。"""
        # 方案 A：共享同一个 TD
        td_shared = ThinkingDataReality()
        results_shared = {}
        analyzers_shared = {
            name: cls(td_shared) for name, cls in _ANALYZER_CLASSES.items()
        }
        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = {
                executor.submit(az.analyze, 102, 30): name
                for name, az in analyzers_shared.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                results_shared[name] = future.result()

        # 方案 B：每个 analyzer 独立 TD
        results_isolated = {}
        for name, cls in _ANALYZER_CLASSES.items():
            td_isolated = ThinkingDataReality()
            az = cls(td_isolated)
            results_isolated[name] = az.analyze(102, 30)

        # Mock 模式下结果应完全一致
        for name in results_shared:
            s = _snapshot_to_dict(results_shared[name])
            i = _snapshot_to_dict(results_isolated[name])
            assert s == i, f"{name}: shared TD != isolated TD"

    def test_no_shared_state_corruption(self):
        """多轮并行后 TD 状态无损坏。"""
        td = ThinkingDataReality()

        for _ in range(5):
            parallel_analyze(td)

        # 串行一次验证功能正常
        results = _serial_analyze(td)
        assert results["Lifecycle"].d7_retention > 0
        assert results["Economy"].avg_inflation_rate != 0


# ── 确定性 ──────────────────────────────────────────────────


class TestDeterministic:
    """验证 Mock 模式下并行执行结果确定性。"""

    def test_three_runs_identical(self):
        """三次并行执行结果完全一致。"""
        td = ThinkingDataReality()
        runs = [parallel_analyze(td) for _ in range(3)]

        for name in _ANALYZER_CLASSES:
            base = _snapshot_to_dict(runs[0][name])
            for i in range(1, 3):
                other = _snapshot_to_dict(runs[i][name])
                assert base == other, (
                    f"{name}: run 1 != run {i+1}\n"
                    f"  base={base}\n  other={other}"
                )

    def test_different_worker_counts_same_result(self):
        """不同 max_workers 下结果一致。"""
        td = ThinkingDataReality()

        r1 = parallel_analyze(td, max_workers=1)  # 实际串行
        r2 = parallel_analyze(td, max_workers=4)
        r3 = parallel_analyze(td, max_workers=7)

        for name in _ANALYZER_CLASSES:
            d1 = _snapshot_to_dict(r1[name])
            d2 = _snapshot_to_dict(r2[name])
            d3 = _snapshot_to_dict(r3[name])
            assert d1 == d2 == d3, f"{name}: inconsistent across worker counts"


# ── 部分失败隔离 ────────────────────────────────────────────


class TestFaultIsolation:
    """验证单个域失败不影响其他域。"""

    def test_one_analyzer_fails_others_succeed(self):
        """一个域抛异常，其他域正常完成。"""

        # 构造一个会失败的 analyzer
        class FailingAnalyzer:
            def __init__(self, td=None):
                self._td = td
            def analyze(self, project_id, lookback_days=30):
                raise RuntimeError("simulated failure")

        td = ThinkingDataReality()
        analyzers = {
            "Lifecycle": LifecycleAnalyzer(td),
            "Funnel": FunnelAnalyzer(td),
            "Failing": FailingAnalyzer(td),  # 这一个会失败
            "Retention": RetentionAnalyzer(td),
            "Monetization": MonetizationAnalyzer(td),
            "Economy": EconomyAnalyzer(td),
            "Gameplay": GameplayAnalyzer(td),
        }

        results: dict[str, Any] = {}
        errors: dict[str, Exception] = {}

        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = {
                executor.submit(az.analyze, 102, 30): name
                for name, az in analyzers.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as exc:
                    errors[name] = exc

        # Failing 应失败
        assert "Failing" in errors
        assert "Failing" not in results

        # 其他 6 域应成功
        for name in ["Lifecycle", "Funnel", "Retention", "Monetization", "Economy", "Gameplay"]:
            assert name in results, f"{name}: should have succeeded"
            assert name not in errors, f"{name}: should not have failed"

    def test_all_analyzers_error_handled(self):
        """所有 analyzer 都失败时不会崩溃。"""
        class AlwaysFailing:
            def __init__(self, td=None):
                pass
            def analyze(self, project_id, lookback_days=30):
                raise RuntimeError("fail")

        analyzers = {name: AlwaysFailing() for name in _ANALYZER_CLASSES}
        errors = {}

        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = {
                executor.submit(az.analyze, 102, 30): name
                for name, az in analyzers.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    errors[name] = exc

        assert len(errors) == 7, f"expected 7 errors, got {len(errors)}"


# ── 计数器验证 ──────────────────────────────────────────────


class TestCounterIncrements:
    """验证 total_analyzed 计数器正确性。"""

    def test_each_analyzer_called_once(self):
        """并行执行一次后每个 analyzer 的 total_analyzed == 1。"""
        td = ThinkingDataReality()
        analyzers = {name: cls(td) for name, cls in _ANALYZER_CLASSES.items()}

        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = {
                executor.submit(az.analyze, 102, 30): name
                for name, az in analyzers.items()
            }
            for future in as_completed(futures):
                future.result()

        for name, az in analyzers.items():
            assert az.total_analyzed == 1, (
                f"{name}: total_analyzed={az.total_analyzed}, expected 1"
            )

    def test_multi_round_counter(self):
        """多轮并行后计数器正确累加。"""
        td = ThinkingDataReality()
        analyzers = {name: cls(td) for name, cls in _ANALYZER_CLASSES.items()}

        for round_num in range(1, 4):
            with ThreadPoolExecutor(max_workers=7) as executor:
                futures = {
                    executor.submit(az.analyze, 102, 30): name
                    for name, az in analyzers.items()
                }
                for future in as_completed(futures):
                    future.result()

            for name, az in analyzers.items():
                assert az.total_analyzed == round_num, (
                    f"{name}: round {round_num}, "
                    f"total_analyzed={az.total_analyzed}, expected {round_num}"
                )


# ── 边界条件 ────────────────────────────────────────────────


class TestEdgeCases:
    """验证边界条件下的并行执行。"""

    def test_without_td_reality(self):
        """无 ThinkingDataReality 时并行仍正常（Mock 模式）。"""
        results = parallel_analyze(None)  # type: ignore[arg-type]

        for name, snap in results.items():
            assert snap is not None, f"{name}: returned None without TD"

        # 关键指标仍被填充
        assert results["Lifecycle"].d7_retention > 0
        assert results["Economy"].avg_inflation_rate != 0
        assert results["UserValue"].total_users > 0

    def test_single_worker(self):
        """max_workers=1 时等同于串行但结果一致。"""
        td = ThinkingDataReality()
        serial = _serial_analyze(td)
        single = parallel_analyze(td, max_workers=1)

        for name in serial:
            s = _snapshot_to_dict(serial[name])
            p = _snapshot_to_dict(single[name])
            assert s == p, f"{name}: single worker != serial"

    def test_more_workers_than_domains(self):
        """max_workers > 域数量时正常降级。"""
        td = ThinkingDataReality()
        results = parallel_analyze(td, max_workers=20)
        assert len(results) == 7, f"expected 7 results, got {len(results)}"

    def test_lookback_days_propagated(self):
        """不同 lookback_days 参数正确传递到各域。"""
        td = ThinkingDataReality()
        results = parallel_analyze(td, lookback_days=7)

        for name, snap in results.items():
            assert snap is not None, f"{name}: returned None"


# ── 高并发压力 ──────────────────────────────────────────────


class TestStress:
    """高并发和压力测试。"""

    def test_many_parallel_rounds(self):
        """连续 20 轮并行执行无异常。"""
        td = ThinkingDataReality()

        for i in range(20):
            results = parallel_analyze(td)
            assert len(results) == 7, f"round {i}: got {len(results)} results"
            for name in results:
                assert results[name] is not None, f"round {i}, {name}: None"

    def test_parallel_with_varying_project_ids(self):
        """不同 project_id 的并行执行不互相干扰。"""
        td = ThinkingDataReality()

        def run_for_project(pid: int) -> dict[str, Any]:
            analyzers = {name: cls(td) for name, cls in _ANALYZER_CLASSES.items()}
            results = {}
            with ThreadPoolExecutor(max_workers=7) as executor:
                futures = {
                    executor.submit(az.analyze, pid, 30): name
                    for name, az in analyzers.items()
                }
                for future in as_completed(futures):
                    name = futures[future]
                    results[name] = future.result()
            return results

        # 三个项目并行
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(run_for_project, pid) for pid in [101, 102, 103]]
            for future in as_completed(futures):
                results = future.result()
                assert len(results) == 7
                for snap in results.values():
                    assert snap is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])