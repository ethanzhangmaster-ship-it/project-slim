"""Release Gate V4.5.2"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def print_header():
    print("=" * 60)
    print("Blueprint Engine V4.5.2 Generation Orchestrator Gate")
    print("=" * 60)
    print()


def print_result(name: str, passed: bool):
    status = "PASS" if passed else "FAIL"
    symbol = "✓" if passed else "✗"
    print(f"  {symbol} {name:<30} {status}")


def check_task_schema() -> bool:
    try:
        from src.market_ops.video_generation.orchestrator.generation_task import GenerationTask
        from src.market_ops.video_generation.orchestrator.generation_state import GenerationStatus

        task = GenerationTask(
            blueprint_id="V001",
            scene_id="S01",
            platform="veo",
            priority=8,
        )
        assert task.task_id != ""
        assert task.status == GenerationStatus.CREATED
        assert task.can_transition_to(GenerationStatus.QUEUED)
        task.transition_to(GenerationStatus.QUEUED)
        task_dict = task.to_dict()
        assert "task_id" in task_dict
        assert "status" in task_dict
        assert "platform" in task_dict
        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_queue_system() -> bool:
    try:
        from src.market_ops.video_generation.queue.priority_queue import PriorityQueue
        from src.market_ops.video_generation.orchestrator.generation_task import GenerationTask

        q = PriorityQueue()
        t1 = GenerationTask(blueprint_id="V", scene_id="S1", platform="veo", priority=5)
        t2 = GenerationTask(blueprint_id="V", scene_id="S2", platform="veo", priority=10)

        q.enqueue(t1)
        q.enqueue(t2)
        assert q.size() == 2

        first = q.dequeue()
        assert first is not None
        assert first.priority == 10
        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_executor_contract() -> bool:
    try:
        from src.market_ops.video_generation.executors.executor_registry import executor_registry
        from src.market_ops.video_generation.executors.base_executor import BaseExecutor, ExecutorResult

        platforms = executor_registry.list_platforms()
        assert len(platforms) >= 4

        for platform in platforms:
            executor = executor_registry.create(platform)
            assert isinstance(executor, BaseExecutor)
            result = executor.submit({"prompt": "test"})
            assert isinstance(result, ExecutorResult)
            assert result.job_id != ""
        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_retry_logic() -> bool:
    try:
        from src.market_ops.video_generation.retry.retry_manager import RetryManager
        from src.market_ops.video_generation.retry.retry_policy import RetryPolicy
        from src.market_ops.video_generation.orchestrator.generation_task import GenerationTask

        policy = RetryPolicy(max_retries=3)
        manager = RetryManager(policy)

        task = GenerationTask(blueprint_id="V", scene_id="S1", platform="veo")
        assert manager.should_retry(task, "timeout error")

        retried = manager.retry(task, "timeout error")
        assert retried is not None
        assert task.retry_count == 1
        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_cost_guard() -> bool:
    try:
        from src.market_ops.video_generation.cost.cost_guard import CostGuard
        from src.market_ops.video_generation.cost.budget_manager import BudgetManager
        from src.market_ops.video_generation.cost.cost_predictor import CostPredictor
        from src.market_ops.video_generation.orchestrator.generation_task import GenerationTask

        budget = BudgetManager(daily_budget=100)
        guard = CostGuard(budget)

        task = GenerationTask(blueprint_id="V", scene_id="S1", platform="veo",
                              prompt={"duration": 5}, priority=5)

        decision = guard.check_task(task)
        assert hasattr(decision, "allowed")
        assert hasattr(decision, "reason")

        prediction = CostPredictor.predict("veo", 5)
        assert "estimated_cost" in prediction
        assert "gpu_required" in prediction
        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_database() -> bool:
    try:
        import tempfile
        from src.market_ops.video_generation.storage.generation_storage import GenerationStorage
        from src.market_ops.video_generation.orchestrator.generation_task import GenerationTask

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = GenerationStorage(str(db_path))

            task = GenerationTask(
                blueprint_id="V001",
                scene_id="S01",
                platform="veo",
                prompt={"test": True},
            )
            storage.save_task(task)

            loaded = storage.get_task(task.task_id)
            assert loaded is not None
            assert loaded.platform == "veo"

            stats = storage.get_stats()
            assert "total_tasks" in stats
        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_output_manager() -> bool:
    try:
        import tempfile
        from src.market_ops.video_generation.assets.asset_manager import AssetManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = AssetManager(tmpdir)
            asset = manager.register_asset(
                task_id="test_task",
                video_path="/tmp/test.mp4",
                platform="veo",
                quality_score=85.5,
            )
            assert asset.asset_id != ""

            loaded = manager.get_asset(asset.asset_id)
            assert loaded is not None
            assert loaded.quality_score == 85.5

            stats = manager.get_stats()
            assert "total_assets" in stats
        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_qa_pipeline() -> bool:
    try:
        from src.market_ops.video_generation.qa.qa_pipeline import QAPipeline, QAResult

        qa = QAPipeline()
        result = qa.evaluate("test_task_001")
        assert isinstance(result, QAResult)
        assert 0 <= result.overall_score <= 100
        assert 0 <= result.technical_score <= 100
        assert 0 <= result.creative_score <= 100
        assert result.recommendation in {"pass", "review", "fail"}
        assert "task_id" in result.to_dict()
        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_dashboard() -> bool:
    try:
        from src.market_ops.video_generation.dashboard.generation_dashboard import GenerationDashboard

        dashboard = GenerationDashboard()
        data = dashboard.get_today_summary()
        assert hasattr(data, "total_generated")
        assert hasattr(data, "total_cost")
        assert hasattr(data, "success_rate")
        text = dashboard.render_text()
        assert len(text) > 0
        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_ci_entry() -> bool:
    try:
        from src.market_ops.video_generation.orchestrator.generation_orchestrator import GenerationOrchestrator

        orch = GenerationOrchestrator()
        task = orch.create_task(
            blueprint_id="V001",
            scene_id="S01",
            platform="veo",
            prompt={"test": True},
        )
        assert task.task_id != ""
        assert orch.submit_task(task.task_id)
        assert orch.start_task(task.task_id)
        assert orch.complete_task(task.task_id, {"result": "ok"}, cost=1.0)

        stats = orch.get_stats()
        assert stats.completed_tasks == 1
        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def main():
    print_header()

    checks = [
        ("Task Schema", check_task_schema),
        ("Queue System", check_queue_system),
        ("Executor Contract", check_executor_contract),
        ("Retry Logic", check_retry_logic),
        ("Cost Guard", check_cost_guard),
        ("Database", check_database),
        ("Output Manager", check_output_manager),
        ("QA Pipeline", check_qa_pipeline),
        ("Dashboard", check_dashboard),
        ("CI Entry", check_ci_entry),
    ]

    results = []
    for name, check_func in checks:
        passed = check_func()
        print_result(name, passed)
        results.append(passed)

    total = len(results)
    passed = sum(results)

    print()
    print("=" * 60)
    print(f"TOTAL  {passed} / {total} PASS")
    print("=" * 60)

    if passed == total:
        print()
        print("V4.5.2 Generation Orchestrator Ready")
        print()
        return 0
    else:
        print()
        print(f"FAILED: {total - passed} check(s) failed")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
