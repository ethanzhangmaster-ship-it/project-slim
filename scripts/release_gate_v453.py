"""Release Gate V4.5.3"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def print_header():
    print("=" * 60)
    print("Blueprint Engine V4.5.3 Production Runtime Gate")
    print("=" * 60)
    print()


def print_result(name: str, passed: bool):
    status = "PASS" if passed else "FAIL"
    symbol = "✓" if passed else "✗"
    print(f"  {symbol} {name:<30} {status}")


def check_connector_contract() -> bool:
    try:
        from src.market_ops.video_generation.connectors.connector_registry import connector_registry
        from src.market_ops.video_generation.connectors.base_connector import BaseConnector, ConnectorResult

        platforms = connector_registry.list_platforms()
        assert len(platforms) >= 4

        for platform in platforms:
            connector = connector_registry.create(platform)
            assert isinstance(connector, BaseConnector)
            result = connector.submit({"prompt": "test"})
            assert isinstance(result, ConnectorResult)
            assert result.job_id != ""
            status = connector.status(result.job_id)
            assert hasattr(status, "status")
        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_async_worker() -> bool:
    try:
        import asyncio
        from src.market_ops.video_generation.workers.async_worker import AsyncWorker

        async def test_worker():
            worker = AsyncWorker()
            result = await worker.submit_task("test_task", {"input": "test"})
            assert result["task_id"] == "test_task"
            assert result["status"] == "completed"
            return True

        return asyncio.run(test_worker())
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_task_dag() -> bool:
    try:
        from src.market_ops.video_generation.dag.task_graph import TaskGraph
        from src.market_ops.video_generation.dag.dependency import TaskNode

        graph = TaskGraph()
        graph.add_node(TaskNode(task_id="task1", task_type="image", priority=10))
        graph.add_node(TaskNode(task_id="task2", task_type="video", depends_on=["task1"], priority=9))

        assert not graph.has_cycles()
        sorted_ids = graph.topological_sort()
        assert sorted_ids.index("task1") < sorted_ids.index("task2")

        ready = graph.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].task_id == "task1"

        graph.mark_completed("task1")
        ready = graph.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].task_id == "task2"

        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_platform_router() -> bool:
    try:
        from src.market_ops.video_generation.router.platform_router import PlatformRouter

        router = PlatformRouter()
        decision = router.route({
            "style": "cinematic",
            "duration": 10,
            "budget": 100,
            "motion": "complex",
        })

        assert decision.platform != ""
        assert decision.score > 0
        assert decision.reason != ""
        assert len(decision.alternatives) > 0

        decision2 = router.suggest_platform({"style": "game", "budget": 5})
        assert decision2.platform != ""

        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_memory_system() -> bool:
    try:
        import tempfile
        from src.market_ops.video_generation.memory.generation_memory import GenerationMemory, GenerationRecord
        from src.market_ops.video_generation.memory.winner_memory import WinnerMemory

        with tempfile.TemporaryDirectory() as tmpdir:
            gen_dir = str(Path(tmpdir) / "generation")
            win_dir = str(Path(tmpdir) / "winner")

            memory = GenerationMemory(gen_dir)
            record = GenerationRecord(
                blueprint_id="V001",
                scene_id="S01",
                platform="kling",
                prompt_dna="close_up + fast_zoom",
                ctr=3.8,
            )
            memory.add_record(record)
            assert memory.get_record(record.record_id) is not None

            winners = memory.get_winners()
            assert len(winners) >= 1

            winner_memory = WinnerMemory(win_dir)
            winner_memory.learn({"prompt_dna": "close_up + fast_zoom", "platform": "kling", "ctr": 3.8})
            assert winner_memory.get_stats()["total_patterns"] >= 1

        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_embedding() -> bool:
    try:
        from src.market_ops.video_generation.embedding.video_encoder import VideoEncoder
        from src.market_ops.video_generation.embedding.similarity_search import SimilaritySearch

        encoder = VideoEncoder()
        embedding = encoder.encode("/tmp/test.mp4")
        assert len(embedding.embedding) == 512

        search = SimilaritySearch()
        search.add("test1", embedding.embedding, {"video_path": "/tmp/test.mp4"})

        query_embedding = [0.1] * 512
        results = search.search(query_embedding, top_k=1)
        assert len(results) == 1

        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_ab_generator() -> bool:
    try:
        from src.market_ops.video_generation.experiment.variant_generator import VariantGenerator
        from src.market_ops.video_generation.experiment.ab_manager import ABManager

        generator = VariantGenerator()
        base = {"id": "V001", "style": "cinematic"}
        variants = generator.generate_variants(base, count=3)
        assert len(variants) == 3
        assert variants[0]["variant_id"] == "V001-A"
        assert "prompt_dna" in variants[0]

        with tempfile.TemporaryDirectory() as tmpdir:
            ab_manager = ABManager(tmpdir)
            exp = ab_manager.create_experiment("V001", ["V001-A", "V001-B"])
            ab_manager.record_metrics(exp.experiment_id, "V001-A", {"ctr": 2.5, "views": 1000})
            ab_manager.record_metrics(exp.experiment_id, "V001-B", {"ctr": 3.8, "views": 1000})
            winner = ab_manager.determine_winner(exp.experiment_id)
            assert winner == "V001-B"

        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_analytics() -> bool:
    try:
        import tempfile
        from src.market_ops.video_generation.analytics.analytics_storage import AnalyticsStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AnalyticsStorage(tmpdir)
            storage.insert_generation({
                "blueprint_id": "V001",
                "scene_id": "S01",
                "platform": "veo",
                "status": "completed",
                "cost": 1.5,
                "quality_score": 85.5,
            })

            stats = storage.get_daily_stats()
            assert stats["total"] >= 1
            assert stats["completed"] >= 1

        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_monitoring() -> bool:
    try:
        from src.market_ops.video_generation.monitor.metrics import MetricsCollector
        from src.market_ops.video_generation.monitor.alert import AlertManager

        collector = MetricsCollector()
        collector.record_request("veo", success=True, latency=10.5, cost=1.5)
        collector.record_request("veo", success=False, latency=30.0, error="timeout")

        stats = collector.get_aggregated_stats()
        assert stats["total_requests"] == 2

        alert_manager = AlertManager()
        alerts = alert_manager.check_and_alert(stats)
        alert_stats = alert_manager.get_stats()
        assert "total_alerts" in alert_stats

        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def check_ci() -> bool:
    try:
        from src.market_ops.video_generation.connectors.connector_registry import connector_registry
        from src.market_ops.video_generation.router.platform_router import PlatformRouter
        from src.market_ops.video_generation.memory.generation_memory import GenerationMemory

        assert len(connector_registry.list_platforms()) >= 4

        router = PlatformRouter()
        decision = router.route({"style": "cinematic", "budget": 100})
        assert decision.platform in connector_registry.list_platforms()

        return True
    except (AssertionError, Exception) as e:
        print(f"    Error: {e}")
        return False


def main():
    print_header()

    checks = [
        ("Connector Contract", check_connector_contract),
        ("Async Worker", check_async_worker),
        ("Task DAG", check_task_dag),
        ("Platform Router", check_platform_router),
        ("Memory System", check_memory_system),
        ("Embedding", check_embedding),
        ("AB Generator", check_ab_generator),
        ("Analytics", check_analytics),
        ("Monitoring", check_monitoring),
        ("CI", check_ci),
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
        print("V4.5.3 Production Runtime Ready")
        print()
        return 0
    else:
        print()
        print(f"FAILED: {total - passed} check(s) failed")
        print()
        return 1


if __name__ == "__main__":
    import tempfile
    sys.exit(main())
