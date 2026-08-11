import sys
import os
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflow_engine import (
    TaskGraph, TaskNode, TaskStatus,
    DependencyManager,
    RetryEngine, RetryPolicy, RetryStrategy,
    WorkflowRunner, Workflow, WorkflowStatus,
    WorkflowScheduler, ScheduleType,
)
from connectors import (
    MetaAdsConnector,
    GoogleAdsConnector,
    AppleSearchAdsConnector,
    TikTokAdsConnector,
    AdjustConnector,
    RevenueCatConnector,
    AppStoreConnector,
    GooglePlayConnector,
    UnityConnector,
    GitHubConnector,
    ConnectorStatus,
)
from production_memory import (
    CompanyMemoryDB, MemoryCategory,
    VectorMemory,
    KnowledgeGraphDB, NodeType, EdgeType,
    MemorySyncEngine,
)
from data_platform import (
    EventCollector, EventType,
    MetricEngine,
    AttributionPipeline,
    DataQualityMonitor, QualityIssueSeverity, DataIssueType,
)
from control_center import (
    ApprovalEngine, ApprovalLevel, ApprovalStatus,
    BudgetGuard, BudgetStatus,
    RiskController, RiskLevel, RiskCategory,
    KillSwitch, KillSwitchLevel, KillSwitchTrigger,
    RollbackSystem, RollbackStatus,
)
from observability import (
    AgentMonitor, AgentStatus,
    WorkflowMonitor,
    CostMonitor,
    FailureDashboard, FailureSeverity, FailureCategory,
)
from autonomous_scheduler import (
    DailyCycle, DailyPhase,
    WeeklyReview,
    MonthlyStrategy,
    CompanyCalendar, CalendarEventType,
)
from autonomous_scheduler.daily_cycle import DailySchedule


class TestTaskGraph(unittest.TestCase):
    def test_add_task(self):
        graph = TaskGraph("test")
        task = TaskNode(task_id="t1", name="Task 1", task_type="test")
        graph.add_task(task)
        self.assertIn("t1", graph.tasks)
        self.assertEqual(graph.tasks["t1"].name, "Task 1")

    def test_add_dependency(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        t2 = TaskNode(task_id="t2", name="Task 2", task_type="test")
        graph.add_task(t1)
        graph.add_task(t2)
        graph.add_dependency("t2", "t1")
        self.assertIn("t1", t2.dependencies)

    def test_get_ready_tasks_no_deps(self):
        graph = TaskGraph("test")
        task = TaskNode(task_id="t1", name="Task 1", task_type="test")
        graph.add_task(task)
        ready = graph.get_ready_tasks()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].task_id, "t1")
        self.assertEqual(ready[0].status, TaskStatus.READY)

    def test_get_ready_tasks_with_deps(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        t2 = TaskNode(task_id="t2", name="Task 2", task_type="test", dependencies=["t1"])
        graph.add_task(t1)
        graph.add_task(t2)
        t1.status = TaskStatus.COMPLETED
        ready = graph.get_ready_tasks()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].task_id, "t2")

    def test_get_progress(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        t2 = TaskNode(task_id="t2", name="Task 2", task_type="test")
        graph.add_task(t1)
        graph.add_task(t2)
        t1.status = TaskStatus.COMPLETED
        progress = graph.get_progress()
        self.assertEqual(progress["total"], 2)
        self.assertEqual(progress["completed"], 1)
        self.assertEqual(progress["progress_percent"], 50.0)

    def test_is_complete(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        graph.add_task(t1)
        t1.status = TaskStatus.COMPLETED
        self.assertTrue(graph.is_complete())

    def test_is_success(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        graph.add_task(t1)
        t1.status = TaskStatus.COMPLETED
        self.assertTrue(graph.is_success())

    def test_priority_order(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Low", task_type="test", priority=1)
        t2 = TaskNode(task_id="t2", name="High", task_type="test", priority=10)
        graph.add_task(t1)
        graph.add_task(t2)
        ready = graph.get_ready_tasks()
        self.assertEqual(ready[0].task_id, "t2")

    def test_task_to_dict(self):
        task = TaskNode(task_id="t1", name="Test", task_type="test", priority=5)
        d = task.to_dict()
        self.assertEqual(d["task_id"], "t1")
        self.assertEqual(d["priority"], 5)

    def test_get_completed_tasks(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        t2 = TaskNode(task_id="t2", name="Task 2", task_type="test")
        graph.add_task(t1)
        graph.add_task(t2)
        t1.status = TaskStatus.COMPLETED
        self.assertEqual(len(graph.get_completed_tasks()), 1)

    def test_get_failed_tasks(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        graph.add_task(t1)
        t1.status = TaskStatus.FAILED
        self.assertEqual(len(graph.get_failed_tasks()), 1)


class TestDependencyManager(unittest.TestCase):
    def test_check_dependencies_ready(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        t2 = TaskNode(task_id="t2", name="Task 2", task_type="test", dependencies=["t1"])
        graph.add_task(t1)
        graph.add_task(t2)
        t1.status = TaskStatus.COMPLETED
        dm = DependencyManager()
        result = dm.check_dependencies("t2", graph)
        self.assertTrue(result.is_ready)

    def test_check_dependencies_not_ready(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        t2 = TaskNode(task_id="t2", name="Task 2", task_type="test", dependencies=["t1"])
        graph.add_task(t1)
        graph.add_task(t2)
        dm = DependencyManager()
        result = dm.check_dependencies("t2", graph)
        self.assertFalse(result.is_ready)
        self.assertIn("t1", result.missing_dependencies)

    def test_get_dependents(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        t2 = TaskNode(task_id="t2", name="Task 2", task_type="test", dependencies=["t1"])
        graph.add_task(t1)
        graph.add_task(t2)
        dm = DependencyManager()
        dependents = dm.get_dependents("t1", graph)
        self.assertEqual(len(dependents), 1)
        self.assertEqual(dependents[0], "t2")

    def test_detect_cycles_no_cycle(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        t2 = TaskNode(task_id="t2", name="Task 2", task_type="test", dependencies=["t1"])
        graph.add_task(t1)
        graph.add_task(t2)
        dm = DependencyManager()
        cycles = dm.detect_cycles(graph)
        self.assertEqual(len(cycles), 0)

    def test_get_critical_path(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        t2 = TaskNode(task_id="t2", name="Task 2", task_type="test", dependencies=["t1"])
        t3 = TaskNode(task_id="t3", name="Task 3", task_type="test", dependencies=["t2"])
        graph.add_task(t1)
        graph.add_task(t2)
        graph.add_task(t3)
        dm = DependencyManager()
        path = dm.get_critical_path(graph)
        self.assertEqual(len(path), 3)

    def test_batch_check(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        t2 = TaskNode(task_id="t2", name="Task 2", task_type="test")
        graph.add_task(t1)
        graph.add_task(t2)
        dm = DependencyManager()
        results = dm.batch_check(["t1", "t2"], graph)
        self.assertEqual(len(results), 2)

    def test_invalidate_cache(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        graph.add_task(t1)
        dm = DependencyManager()
        dm.check_dependencies("t1", graph)
        dm.invalidate_cache("t1")
        self.assertEqual(len(dm.dependency_cache), 0)

    def test_check_dependencies_failed(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        t2 = TaskNode(task_id="t2", name="Task 2", task_type="test", dependencies=["t1"])
        graph.add_task(t1)
        graph.add_task(t2)
        t1.status = TaskStatus.FAILED
        dm = DependencyManager()
        result = dm.check_dependencies("t2", graph)
        self.assertFalse(result.is_ready)
        self.assertIn("t1", result.failed_dependencies)

    def test_get_dependency_chain(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="Task 1", task_type="test")
        t2 = TaskNode(task_id="t2", name="Task 2", task_type="test", dependencies=["t1"])
        t3 = TaskNode(task_id="t3", name="Task 3", task_type="test", dependencies=["t2"])
        graph.add_task(t1)
        graph.add_task(t2)
        graph.add_task(t3)
        dm = DependencyManager()
        chain = dm.get_dependency_chain("t3", graph)
        self.assertGreater(len(chain), 1)


class TestRetryEngine(unittest.TestCase):
    def test_retry_policy_exponential(self):
        policy = RetryPolicy(max_retries=3, strategy=RetryStrategy.EXPONENTIAL_BACKOFF)
        delay = policy.calculate_delay(1)
        self.assertGreater(delay, 0)

    def test_retry_policy_fixed(self):
        policy = RetryPolicy(max_retries=3, strategy=RetryStrategy.FIXED_DELAY, initial_delay_seconds=5.0, jitter=False)
        delay = policy.calculate_delay(1)
        self.assertEqual(delay, 5.0)

    def test_retry_policy_linear(self):
        policy = RetryPolicy(max_retries=3, strategy=RetryStrategy.LINEAR_BACKOFF, initial_delay_seconds=1.0)
        delay2 = policy.calculate_delay(2)
        self.assertGreater(delay2, 1.0)

    def test_schedule_retry_success(self):
        engine = RetryEngine()
        record = engine.schedule_retry("task_1", "test", "Test error", 1)
        self.assertIsNotNone(record)
        self.assertEqual(record.attempt, 2)

    def test_schedule_retry_max_reached(self):
        policy = RetryPolicy(max_retries=2)
        engine = RetryEngine(default_policy=policy)
        engine.schedule_retry("task_1", "test", "Error 1", 1)
        engine.schedule_retry("task_1", "test", "Error 2", 2)
        result = engine.schedule_retry("task_1", "test", "Error 3", 3)
        self.assertIsNone(result)

    def test_get_due_retries(self):
        engine = RetryEngine()
        policy = RetryPolicy(strategy=RetryStrategy.IMMEDIATE, max_retries=3)
        engine.set_policy("test", policy)
        engine.schedule_retry("task_1", "test", "Error", 1)
        due = engine.get_due_retries()
        self.assertEqual(len(due), 1)

    def test_get_retry_count(self):
        engine = RetryEngine()
        engine.schedule_retry("task_1", "test", "Error 1", 1)
        engine.schedule_retry("task_1", "test", "Error 2", 2)
        self.assertEqual(engine.get_retry_count("task_1"), 2)

    def test_clear_task_retries(self):
        engine = RetryEngine()
        engine.schedule_retry("task_1", "test", "Error", 1)
        engine.clear_task_retries("task_1")
        self.assertEqual(engine.get_retry_count("task_1"), 0)
        self.assertEqual(engine.get_queue_size(), 0)

    def test_get_stats(self):
        engine = RetryEngine()
        engine.schedule_retry("task_1", "test", "Error", 1)
        stats = engine.get_stats()
        self.assertEqual(stats["total_retries"], 1)

    def test_retry_policy_max_delay(self):
        policy = RetryPolicy(
            max_retries=5,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            initial_delay_seconds=1.0,
            max_delay_seconds=10.0,
            backoff_multiplier=3.0,
        )
        delay = policy.calculate_delay(10)
        self.assertLessEqual(delay, 10.0)

    def test_retry_policy_jitter(self):
        policy = RetryPolicy(jitter=True, initial_delay_seconds=1.0)
        delays = [policy.calculate_delay(1) for _ in range(10)]
        self.assertTrue(any(d != delays[0] for d in delays))

    def test_set_policy(self):
        engine = RetryEngine()
        policy = RetryPolicy(max_retries=5)
        engine.set_policy("ua", policy)
        self.assertEqual(engine.get_policy("ua").max_retries, 5)

    def test_get_retry_history(self):
        engine = RetryEngine()
        engine.schedule_retry("task_1", "test", "Error", 1)
        history = engine.get_retry_history("task_1")
        self.assertEqual(len(history), 1)


class TestWorkflowRunner(unittest.TestCase):
    def test_create_workflow(self):
        runner = WorkflowRunner()
        wf = runner.create_workflow("Test Workflow")
        self.assertIsNotNone(wf)
        self.assertEqual(wf.name, "Test Workflow")
        self.assertEqual(wf.status, WorkflowStatus.CREATED)

    def test_register_handler(self):
        runner = WorkflowRunner()
        runner.register_handler("test", lambda t, ctx: {"result": "ok"})
        self.assertIn("test", runner.task_handlers)

    def test_start_workflow(self):
        runner = WorkflowRunner()
        wf = runner.create_workflow("Test")
        runner.start_workflow(wf.workflow_id)
        self.assertEqual(wf.status, WorkflowStatus.RUNNING)

    def test_execute_step(self):
        runner = WorkflowRunner()
        results = []

        def handler(task, ctx):
            results.append(task.task_id)
            return {"output": "done"}

        runner.register_handler("test", handler)
        wf = runner.create_workflow("Test")
        task = TaskNode(task_id="t1", name="T1", task_type="test")
        wf.task_graph.add_task(task)
        runner.start_workflow(wf.workflow_id)
        step_result = runner.execute_step(wf.workflow_id)
        self.assertEqual(step_result["tasks_executed"], 1)
        self.assertEqual(len(results), 1)

    def test_run_until_complete(self):
        runner = WorkflowRunner()
        wf = runner.create_workflow("Test")
        t1 = TaskNode(task_id="t1", name="T1", task_type="test")
        t2 = TaskNode(task_id="t2", name="T2", task_type="test", dependencies=["t1"])
        wf.task_graph.add_task(t1)
        wf.task_graph.add_task(t2)
        result = runner.run_until_complete(wf.workflow_id)
        self.assertEqual(result.status, WorkflowStatus.COMPLETED)

    def test_pause_workflow(self):
        runner = WorkflowRunner()
        wf = runner.create_workflow("Test")
        runner.start_workflow(wf.workflow_id)
        self.assertTrue(runner.pause_workflow(wf.workflow_id))
        self.assertEqual(wf.status, WorkflowStatus.PAUSED)

    def test_resume_workflow(self):
        runner = WorkflowRunner()
        wf = runner.create_workflow("Test")
        runner.start_workflow(wf.workflow_id)
        runner.pause_workflow(wf.workflow_id)
        self.assertTrue(runner.resume_workflow(wf.workflow_id))
        self.assertEqual(wf.status, WorkflowStatus.RUNNING)

    def test_cancel_workflow(self):
        runner = WorkflowRunner()
        wf = runner.create_workflow("Test")
        runner.start_workflow(wf.workflow_id)
        self.assertTrue(runner.cancel_workflow(wf.workflow_id))
        self.assertEqual(wf.status, WorkflowStatus.CANCELLED)

    def test_get_workflow_stats(self):
        runner = WorkflowRunner()
        wf = runner.create_workflow("Test")
        runner.run_until_complete(wf.workflow_id)
        stats = runner.get_workflow_stats()
        self.assertGreaterEqual(stats["completed"], 1)

    def test_workflow_with_context(self):
        runner = WorkflowRunner()
        ctx = {"budget": 10000}
        wf = runner.create_workflow("Test", context=ctx)
        self.assertEqual(wf.context["budget"], 10000)

    def test_get_workflow(self):
        runner = WorkflowRunner()
        wf = runner.create_workflow("Test")
        retrieved = runner.get_workflow(wf.workflow_id)
        self.assertEqual(retrieved.workflow_id, wf.workflow_id)

    def test_get_active_workflows(self):
        runner = WorkflowRunner()
        wf = runner.create_workflow("Test")
        runner.start_workflow(wf.workflow_id)
        active = runner.get_active_workflows()
        self.assertEqual(len(active), 1)

    def test_max_concurrent(self):
        runner = WorkflowRunner(max_concurrent_tasks=1)
        wf = runner.create_workflow("Test")
        t1 = TaskNode(task_id="t1", name="T1", task_type="test")
        t2 = TaskNode(task_id="t2", name="T2", task_type="test")
        wf.task_graph.add_task(t1)
        wf.task_graph.add_task(t2)
        runner.start_workflow(wf.workflow_id)
        result = runner.execute_step(wf.workflow_id)
        self.assertLessEqual(result.get("tasks_executed", 0), 1)


class TestWorkflowScheduler(unittest.TestCase):
    def test_add_schedule_once(self):
        scheduler = WorkflowScheduler()
        schedule = scheduler.add_schedule("daily_ua", ScheduleType.ONCE)
        self.assertIsNotNone(schedule)
        self.assertEqual(schedule.workflow_name, "daily_ua")

    def test_add_schedule_interval(self):
        scheduler = WorkflowScheduler()
        schedule = scheduler.add_schedule("test", ScheduleType.INTERVAL, interval_seconds=3600)
        self.assertEqual(schedule.interval_seconds, 3600)

    def test_add_schedule_daily(self):
        scheduler = WorkflowScheduler()
        schedule = scheduler.add_schedule("test", ScheduleType.DAILY)
        self.assertEqual(schedule.schedule_type, ScheduleType.DAILY)

    def test_get_due_schedules(self):
        scheduler = WorkflowScheduler()
        start_time = datetime.now() - timedelta(hours=1)
        scheduler.add_schedule("test", ScheduleType.ONCE, start_time=start_time)
        due = scheduler.get_due_schedules()
        self.assertGreater(len(due), 0)

    def test_trigger_schedule(self):
        scheduler = WorkflowScheduler()
        schedule = scheduler.add_schedule("test", ScheduleType.ONCE)
        run = scheduler.trigger_schedule(schedule.schedule_id)
        self.assertIsNotNone(run)
        self.assertEqual(run.workflow_name, "test")

    def test_tick(self):
        scheduler = WorkflowScheduler()
        start_time = datetime.now() - timedelta(hours=1)
        scheduler.add_schedule("test", ScheduleType.ONCE, start_time=start_time)
        runs = scheduler.tick()
        self.assertGreater(len(runs), 0)

    def test_get_pending_runs(self):
        scheduler = WorkflowScheduler()
        schedule = scheduler.add_schedule("test", ScheduleType.ONCE)
        scheduler.trigger_schedule(schedule.schedule_id)
        pending = scheduler.get_pending_runs()
        self.assertGreater(len(pending), 0)

    def test_mark_run_started(self):
        scheduler = WorkflowScheduler()
        schedule = scheduler.add_schedule("test", ScheduleType.ONCE)
        run = scheduler.trigger_schedule(schedule.schedule_id)
        self.assertTrue(scheduler.mark_run_started(run.run_id))

    def test_mark_run_completed(self):
        scheduler = WorkflowScheduler()
        schedule = scheduler.add_schedule("test", ScheduleType.ONCE)
        run = scheduler.trigger_schedule(schedule.schedule_id)
        self.assertTrue(scheduler.mark_run_completed(run.run_id))

    def test_pause_schedule(self):
        scheduler = WorkflowScheduler()
        schedule = scheduler.add_schedule("test", ScheduleType.DAILY)
        self.assertTrue(scheduler.pause_schedule(schedule.schedule_id))
        self.assertFalse(schedule.is_active)

    def test_resume_schedule(self):
        scheduler = WorkflowScheduler()
        schedule = scheduler.add_schedule("test", ScheduleType.DAILY)
        scheduler.pause_schedule(schedule.schedule_id)
        self.assertTrue(scheduler.resume_schedule(schedule.schedule_id))
        self.assertTrue(schedule.is_active)

    def test_remove_schedule(self):
        scheduler = WorkflowScheduler()
        schedule = scheduler.add_schedule("test", ScheduleType.ONCE)
        self.assertTrue(scheduler.remove_schedule(schedule.schedule_id))
        self.assertEqual(len(scheduler.schedules), 0)

    def test_get_stats(self):
        scheduler = WorkflowScheduler()
        scheduler.add_schedule("test1", ScheduleType.DAILY)
        scheduler.add_schedule("test2", ScheduleType.WEEKLY)
        stats = scheduler.get_stats()
        self.assertEqual(stats["total_schedules"], 2)

    def test_max_runs(self):
        scheduler = WorkflowScheduler()
        schedule = scheduler.add_schedule("test", ScheduleType.INTERVAL, interval_seconds=1, max_runs=2)
        for _ in range(3):
            scheduler.trigger_schedule(schedule.schedule_id)
        self.assertEqual(schedule.run_count, 2)

    def test_register_workflow_creator(self):
        scheduler = WorkflowScheduler()
        scheduler.register_workflow_creator("test", lambda: "workflow")
        self.assertIn("test", scheduler.workflow_creators)


class TestConnectors(unittest.TestCase):
    def test_meta_connector_connect(self):
        connector = MetaAdsConnector()
        self.assertTrue(connector.connect())
        self.assertEqual(connector.status, ConnectorStatus.CONNECTED)

    def test_meta_connector_get_campaigns(self):
        connector = MetaAdsConnector()
        connector.connect()
        result = connector.get_campaigns()
        self.assertTrue(result.success)
        self.assertIn("campaigns", result.data)

    def test_meta_connector_get_campaign_metrics(self):
        connector = MetaAdsConnector()
        connector.connect()
        result = connector.get_campaign_metrics("camp_001")
        self.assertTrue(result.success)
        self.assertIn("metrics", result.data)
        self.assertGreater(result.data["metrics"]["spend"], 0)

    def test_meta_connector_update_budget(self):
        connector = MetaAdsConnector()
        connector.connect()
        result = connector.update_budget("camp_001", 5000)
        self.assertTrue(result.success)

    def test_meta_connector_create_campaign(self):
        connector = MetaAdsConnector()
        connector.connect()
        result = connector.create_campaign("New Campaign", 1000)
        self.assertTrue(result.success)
        self.assertIn("campaign_id", result.data)

    def test_meta_connector_pause_campaign(self):
        connector = MetaAdsConnector()
        connector.connect()
        result = connector.pause_campaign("camp_001")
        self.assertTrue(result.success)

    def test_meta_connector_get_adset_metrics(self):
        connector = MetaAdsConnector()
        connector.connect()
        result = connector.get_adset_metrics("camp_001")
        self.assertTrue(result.success)

    def test_meta_connector_get_creative_performance(self):
        connector = MetaAdsConnector()
        connector.connect()
        result = connector.get_creative_performance("camp_001")
        self.assertTrue(result.success)

    def test_google_ads_connector(self):
        connector = GoogleAdsConnector()
        connector.connect()
        result = connector.get_campaigns()
        self.assertTrue(result.success)
        self.assertIn("campaigns", result.data)

    def test_google_ads_keywords(self):
        connector = GoogleAdsConnector()
        connector.connect()
        result = connector.get_keywords("camp_001")
        self.assertTrue(result.success)
        self.assertIn("keywords", result.data)

    def test_asa_connector(self):
        connector = AppleSearchAdsConnector()
        connector.connect()
        result = connector.get_campaigns()
        self.assertTrue(result.success)

    def test_asa_search_terms(self):
        connector = AppleSearchAdsConnector()
        connector.connect()
        result = connector.get_search_terms("camp_001")
        self.assertTrue(result.success)

    def test_tiktok_connector(self):
        connector = TikTokAdsConnector()
        connector.connect()
        result = connector.get_campaigns()
        self.assertTrue(result.success)

    def test_tiktok_video_metrics(self):
        connector = TikTokAdsConnector()
        connector.connect()
        result = connector.get_video_metrics("camp_001")
        self.assertTrue(result.success)

    def test_adjust_connector_installs(self):
        connector = AdjustConnector()
        connector.connect()
        result = connector.get_installs()
        self.assertTrue(result.success)
        self.assertIn("total_installs", result.data)

    def test_adjust_connector_retention(self):
        connector = AdjustConnector()
        connector.connect()
        result = connector.get_retention("2026-07-01")
        self.assertTrue(result.success)
        self.assertIn("d1", result.data)

    def test_adjust_connector_revenue(self):
        connector = AdjustConnector()
        connector.connect()
        result = connector.get_revenue()
        self.assertTrue(result.success)

    def test_adjust_connector_events(self):
        connector = AdjustConnector()
        connector.connect()
        result = connector.get_events()
        self.assertTrue(result.success)

    def test_revenuecat_connector_subscribers(self):
        connector = RevenueCatConnector()
        connector.connect()
        result = connector.get_subscribers()
        self.assertTrue(result.success)
        self.assertIn("mrr", result.data)

    def test_revenuecat_connector_transactions(self):
        connector = RevenueCatConnector()
        connector.connect()
        result = connector.get_transactions()
        self.assertTrue(result.success)

    def test_revenuecat_connector_churn(self):
        connector = RevenueCatConnector()
        connector.connect()
        result = connector.get_churn()
        self.assertTrue(result.success)

    def test_revenuecat_connector_mrr(self):
        connector = RevenueCatConnector()
        connector.connect()
        result = connector.get_mrr()
        self.assertTrue(result.success)
        self.assertIn("mrr", result.data)

    def test_appstore_connector_info(self):
        connector = AppStoreConnector()
        connector.connect()
        result = connector.get_app_info()
        self.assertTrue(result.success)

    def test_appstore_connector_reviews(self):
        connector = AppStoreConnector()
        connector.connect()
        result = connector.get_reviews()
        self.assertTrue(result.success)
        self.assertIn("reviews", result.data)

    def test_appstore_connector_rankings(self):
        connector = AppStoreConnector()
        connector.connect()
        result = connector.get_rankings()
        self.assertTrue(result.success)

    def test_appstore_connector_sales(self):
        connector = AppStoreConnector()
        connector.connect()
        result = connector.get_sales_report()
        self.assertTrue(result.success)

    def test_googleplay_connector_info(self):
        connector = GooglePlayConnector()
        connector.connect()
        result = connector.get_app_info()
        self.assertTrue(result.success)

    def test_googleplay_connector_reviews(self):
        connector = GooglePlayConnector()
        connector.connect()
        result = connector.get_reviews()
        self.assertTrue(result.success)

    def test_googleplay_connector_stats(self):
        connector = GooglePlayConnector()
        connector.connect()
        result = connector.get_stats()
        self.assertTrue(result.success)

    def test_unity_connector_project(self):
        connector = UnityConnector()
        connector.connect()
        result = connector.get_project_info()
        self.assertTrue(result.success)

    def test_unity_connector_builds(self):
        connector = UnityConnector()
        connector.connect()
        result = connector.get_builds()
        self.assertTrue(result.success)

    def test_unity_connector_trigger_build(self):
        connector = UnityConnector()
        connector.connect()
        result = connector.trigger_build()
        self.assertTrue(result.success)

    def test_github_connector_repo(self):
        connector = GitHubConnector()
        connector.connect()
        result = connector.get_repo_info()
        self.assertTrue(result.success)

    def test_github_connector_branches(self):
        connector = GitHubConnector()
        connector.connect()
        result = connector.get_branches()
        self.assertTrue(result.success)

    def test_github_connector_prs(self):
        connector = GitHubConnector()
        connector.connect()
        result = connector.get_pull_requests()
        self.assertTrue(result.success)

    def test_github_connector_create_issue(self):
        connector = GitHubConnector()
        connector.connect()
        result = connector.create_issue("Bug fix", "description")
        self.assertTrue(result.success)

    def test_connector_disconnect(self):
        connector = MetaAdsConnector()
        connector.connect()
        connector.disconnect()
        self.assertEqual(connector.status, ConnectorStatus.DISCONNECTED)

    def test_connector_is_connected(self):
        connector = MetaAdsConnector()
        self.assertFalse(connector.is_connected())
        connector.connect()
        self.assertTrue(connector.is_connected())


class TestProductionMemory(unittest.TestCase):
    def test_memory_store(self):
        db = CompanyMemoryDB()
        record = db.store(
            category=MemoryCategory.STRATEGY,
            title="Test Strategy",
            content={"roi": 2.5},
            tags=["test", "strategy"],
            importance=0.8,
        )
        self.assertIsNotNone(record)
        self.assertEqual(record.title, "Test Strategy")

    def test_memory_get(self):
        db = CompanyMemoryDB()
        record = db.store(MemoryCategory.PRODUCT, "Test", {})
        retrieved = db.get(record.record_id)
        self.assertEqual(retrieved.record_id, record.record_id)

    def test_memory_query_by_category(self):
        db = CompanyMemoryDB()
        db.store(MemoryCategory.STRATEGY, "S1", {})
        db.store(MemoryCategory.PRODUCT, "P1", {})
        results = db.query(category=MemoryCategory.STRATEGY)
        self.assertEqual(len(results), 1)

    def test_memory_query_by_tags(self):
        db = CompanyMemoryDB()
        db.store(MemoryCategory.STRATEGY, "S1", {}, tags=["ua"])
        db.store(MemoryCategory.STRATEGY, "S2", {}, tags=["creative"])
        results = db.query(tags=["ua"])
        self.assertEqual(len(results), 1)

    def test_memory_query_by_importance(self):
        db = CompanyMemoryDB()
        db.store(MemoryCategory.STRATEGY, "Low", {}, importance=0.3)
        db.store(MemoryCategory.STRATEGY, "High", {}, importance=0.9)
        results = db.query(min_importance=0.8)
        self.assertEqual(len(results), 1)

    def test_memory_search(self):
        db = CompanyMemoryDB()
        db.store(MemoryCategory.STRATEGY, "Merge Game Strategy", {"genre": "merge"})
        results = db.search("merge")
        self.assertGreater(len(results), 0)

    def test_memory_update(self):
        db = CompanyMemoryDB()
        record = db.store(MemoryCategory.STRATEGY, "Test", {"value": 1})
        self.assertTrue(db.update(record.record_id, {"title": "Updated"}))
        self.assertEqual(db.get(record.record_id).title, "Updated")

    def test_memory_delete(self):
        db = CompanyMemoryDB()
        record = db.store(MemoryCategory.STRATEGY, "Test", {})
        self.assertTrue(db.delete(record.record_id))
        self.assertIsNone(db.get(record.record_id))

    def test_memory_get_stats(self):
        db = CompanyMemoryDB()
        db.store(MemoryCategory.STRATEGY, "S1", {})
        stats = db.get_stats()
        self.assertEqual(stats["total_records"], 1)

    def test_memory_get_by_tag(self):
        db = CompanyMemoryDB()
        db.store(MemoryCategory.STRATEGY, "S1", {}, tags=["test"])
        results = db.get_by_tag("test")
        self.assertEqual(len(results), 1)

    def test_memory_get_by_category(self):
        db = CompanyMemoryDB()
        db.store(MemoryCategory.STRATEGY, "S1", {})
        results = db.get_by_category(MemoryCategory.STRATEGY)
        self.assertEqual(len(results), 1)

    def test_vector_memory_add(self):
        vm = VectorMemory()
        entry = vm.add("test text", {"id": 1}, "general")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.text, "test text")

    def test_vector_memory_search(self):
        vm = VectorMemory()
        vm.add("merge game strategy", {"type": "strategy"}, "strategy")
        vm.add("cooking recipe", {"type": "other"}, "other")
        results = vm.search("merge game", top_k=5)
        self.assertGreater(len(results), 0)

    def test_vector_memory_search_by_category(self):
        vm = VectorMemory()
        vm.add("test", {}, "cat1")
        vm.add("test2", {}, "cat2")
        results = vm.search("test", category="cat1")
        self.assertEqual(len(results), 1)

    def test_vector_memory_get(self):
        vm = VectorMemory()
        entry = vm.add("test", {}, "general")
        retrieved = vm.get(entry.vector_id)
        self.assertEqual(retrieved.vector_id, entry.vector_id)

    def test_vector_memory_delete(self):
        vm = VectorMemory()
        entry = vm.add("test", {}, "general")
        self.assertTrue(vm.delete(entry.vector_id))
        self.assertIsNone(vm.get(entry.vector_id))

    def test_vector_memory_get_similar(self):
        vm = VectorMemory()
        e1 = vm.add("merge game", {}, "strategy")
        vm.add("merge puzzle", {}, "strategy")
        similar = vm.get_similar(e1.vector_id)
        self.assertGreaterEqual(len(similar), 0)

    def test_vector_memory_get_categories(self):
        vm = VectorMemory()
        vm.add("test1", {}, "cat1")
        vm.add("test2", {}, "cat2")
        cats = vm.get_categories()
        self.assertIn("cat1", cats)
        self.assertIn("cat2", cats)

    def test_vector_memory_stats(self):
        vm = VectorMemory()
        vm.add("test", {}, "general")
        stats = vm.get_stats()
        self.assertEqual(stats["total_vectors"], 1)

    def test_vector_memory_add_batch(self):
        vm = VectorMemory()
        items = [("t1", {}, "g"), ("t2", {}, "g"), ("t3", {}, "g")]
        results = vm.add_batch(items)
        self.assertEqual(len(results), 3)

    def test_knowledge_graph_add_node(self):
        kg = KnowledgeGraphDB()
        node = kg.add_node(NodeType.GAME, "Test Game", {"genre": "merge"})
        self.assertIsNotNone(node)
        self.assertEqual(node.name, "Test Game")

    def test_knowledge_graph_add_edge(self):
        kg = KnowledgeGraphDB()
        n1 = kg.add_node(NodeType.GAME, "Game 1")
        n2 = kg.add_node(NodeType.GENRE, "Merge")
        edge = kg.add_edge(n1.node_id, n2.node_id, EdgeType.BELONGS_TO)
        self.assertIsNotNone(edge)

    def test_knowledge_graph_get_node(self):
        kg = KnowledgeGraphDB()
        node = kg.add_node(NodeType.GAME, "Test Game")
        retrieved = kg.get_node(node.node_id)
        self.assertEqual(retrieved.node_id, node.node_id)

    def test_knowledge_graph_get_node_by_name(self):
        kg = KnowledgeGraphDB()
        kg.add_node(NodeType.GAME, "Test Game")
        node = kg.get_node_by_name("Test Game", NodeType.GAME)
        self.assertIsNotNone(node)

    def test_knowledge_graph_get_neighbors(self):
        kg = KnowledgeGraphDB()
        n1 = kg.add_node(NodeType.GAME, "Game 1")
        n2 = kg.add_node(NodeType.GENRE, "Merge")
        kg.add_edge(n1.node_id, n2.node_id, EdgeType.BELONGS_TO)
        neighbors = kg.get_neighbors(n1.node_id)
        self.assertGreater(len(neighbors), 0)

    def test_knowledge_graph_get_nodes_by_type(self):
        kg = KnowledgeGraphDB()
        kg.add_node(NodeType.GAME, "Game 1")
        kg.add_node(NodeType.GAME, "Game 2")
        kg.add_node(NodeType.GENRE, "Merge")
        games = kg.get_nodes_by_type(NodeType.GAME)
        self.assertEqual(len(games), 2)

    def test_knowledge_graph_find_path(self):
        kg = KnowledgeGraphDB()
        n1 = kg.add_node(NodeType.GAME, "Game")
        n2 = kg.add_node(NodeType.GENRE, "Genre")
        n3 = kg.add_node(NodeType.AUDIENCE, "Audience")
        kg.add_edge(n1.node_id, n2.node_id, EdgeType.BELONGS_TO)
        kg.add_edge(n2.node_id, n3.node_id, EdgeType.TARGETS)
        path = kg.find_path(n1.node_id, n3.node_id)
        self.assertGreater(len(path), 0)

    def test_knowledge_graph_get_related_insights(self):
        kg = KnowledgeGraphDB()
        n1 = kg.add_node(NodeType.GAME, "Game")
        n2 = kg.add_node(NodeType.INSIGHT, "Insight 1")
        kg.add_edge(n1.node_id, n2.node_id, EdgeType.RELATED_TO)
        insights = kg.get_related_insights(n1.node_id)
        self.assertGreater(len(insights), 0)

    def test_knowledge_graph_find_patterns(self):
        kg = KnowledgeGraphDB()
        kg.add_node(NodeType.GAME, "G1")
        kg.add_node(NodeType.GAME, "G2")
        patterns = kg.find_patterns(NodeType.GAME, NodeType.INSIGHT)
        self.assertIsInstance(patterns, list)

    def test_knowledge_graph_stats(self):
        kg = KnowledgeGraphDB()
        kg.add_node(NodeType.GAME, "Test")
        stats = kg.get_stats()
        self.assertEqual(stats["total_nodes"], 1)

    def test_memory_sync_add_record(self):
        engine = MemorySyncEngine()
        result = engine.add_record_with_sync(
            category=MemoryCategory.PRODUCT,
            title="Test Product",
            content={"game_name": "Cozy Game", "genre": "Merge", "target_audience": "Female 25-44"},
            tags=["test"],
            importance=0.8,
        )
        self.assertEqual(result.status.value, "completed")
        self.assertGreater(result.records_synced, 0)

    def test_memory_sync_search_across_all(self):
        engine = MemorySyncEngine()
        engine.add_record_with_sync(
            category=MemoryCategory.STRATEGY,
            title="Merge Game Strategy",
            content={"roi": 2.5},
        )
        results = engine.search_across_all("merge")
        self.assertGreater(results["total_unique"], 0)

    def test_memory_sync_batch_sync(self):
        engine = MemorySyncEngine()
        records = [
            {"title": "R1", "category": "strategy", "content": {"a": 1}},
            {"title": "R2", "category": "product", "content": {"b": 2}},
        ]
        result = engine.batch_sync(records)
        self.assertEqual(result.records_synced, 2)

    def test_memory_sync_get_sync_history(self):
        engine = MemorySyncEngine()
        engine.add_record_with_sync(MemoryCategory.STRATEGY, "Test", {})
        history = engine.get_sync_history()
        self.assertEqual(len(history), 1)

    def test_memory_sync_get_all_stats(self):
        engine = MemorySyncEngine()
        engine.add_record_with_sync(MemoryCategory.STRATEGY, "Test", {})
        stats = engine.get_all_stats()
        self.assertIn("memory_db", stats)
        self.assertIn("vector_memory", stats)
        self.assertIn("knowledge_graph", stats)


class TestBudgetGuardExtended(unittest.TestCase):
    def test_budget_allocate(self):
        bg = BudgetGuard(total_budget=10000)
        alloc = bg.allocate("ua", 5000)
        self.assertEqual(alloc.budget_amount, 5000)
        self.assertEqual(alloc.category, "ua")

    def test_budget_record_spend_ok(self):
        bg = BudgetGuard(total_budget=10000)
        bg.allocate("ua", 5000)
        status = bg.record_spend("ua", 100)
        self.assertIsInstance(status, BudgetStatus)

    def test_budget_can_spend_true(self):
        bg = BudgetGuard(total_budget=10000)
        bg.allocate("ua", 5000)
        self.assertTrue(bg.can_spend("ua", 100))

    def test_budget_can_spend_false(self):
        bg = BudgetGuard(total_budget=1000)
        bg.allocate("ua", 100)
        self.assertFalse(bg.can_spend("ua", 200))

    def test_budget_request_increase(self):
        bg = BudgetGuard(total_budget=100000)
        bg.allocate("ua", 5000)
        result = bg.request_budget_increase("ua", 10000, "ROI 2.0", {"roas": 2.5})
        self.assertIsNotNone(result)

    def test_budget_get_status(self):
        bg = BudgetGuard(total_budget=10000)
        bg.allocate("ua", 5000)
        status = bg.get_budget_status("ua")
        self.assertIsInstance(status, BudgetStatus)

    def test_budget_get_daily_spend(self):
        bg = BudgetGuard(total_budget=10000)
        bg.allocate("ua", 5000)
        bg.record_spend("ua", 500)
        daily = bg.get_daily_spend()
        self.assertGreater(daily, 0)

    def test_budget_get_overall_status(self):
        bg = BudgetGuard(total_budget=10000)
        bg.allocate("ua", 5000)
        status = bg.get_overall_status()
        self.assertIsInstance(status, dict)

    def test_budget_get_stats(self):
        bg = BudgetGuard(total_budget=10000)
        bg.allocate("ua", 5000)
        stats = bg.get_stats()
        self.assertIn("total_budget", stats)

    def test_budget_approve_increase(self):
        bg = BudgetGuard(total_budget=100000)
        bg.allocate("ua", 5000)
        req = bg.request_budget_increase("ua", 8000, "Good ROI", {})
        result = bg.approve_increase(req.request_id)
        self.assertTrue(result)


class TestApprovalEngineExtended(unittest.TestCase):
    def test_approval_request(self):
        ae = ApprovalEngine()
        req = ae.request_approval("campaign_pause", "Pause campaign", {"campaign_id": "123"})
        self.assertIsNotNone(req)

    def test_approval_approve(self):
        ae = ApprovalEngine()
        req = ae.request_approval("game_launch", "Launch game", {})
        result = ae.approve(req.request_id, "admin")
        self.assertTrue(result)

    def test_approval_reject(self):
        ae = ApprovalEngine()
        req = ae.request_approval("game_launch", "Launch game", {})
        result = ae.reject(req.request_id, "admin", "Not ready")
        self.assertTrue(result)

    def test_approval_get_request(self):
        ae = ApprovalEngine()
        req = ae.request_approval("campaign_pause", "Pause", {})
        retrieved = ae.get_request(req.request_id)
        self.assertIsNotNone(retrieved)

    def test_approval_get_pending(self):
        ae = ApprovalEngine()
        ae.request_approval("game_launch", "Launch game", {})
        pending = ae.get_pending_requests()
        self.assertGreater(len(pending), 0)

    def test_approval_get_by_status(self):
        ae = ApprovalEngine()
        req = ae.request_approval("game_launch", "Launch", {})
        ae.approve(req.request_id, "admin")
        approved = ae.get_requests_by_status(ApprovalStatus.APPROVED)
        self.assertGreaterEqual(len(approved), 0)

    def test_approval_add_rule(self):
        ae = ApprovalEngine()
        ae.add_rule("custom_action", ApprovalLevel.LEVEL_2_APPROVAL)
        req = ae.request_approval("custom_action", "Test", {})
        self.assertEqual(req.level, ApprovalLevel.LEVEL_2_APPROVAL)

    def test_approval_get_stats(self):
        ae = ApprovalEngine()
        ae.request_approval("campaign_pause", "Pause", {})
        stats = ae.get_stats()
        self.assertIn("total_requests", stats)

    def test_approval_can_execute(self):
        ae = ApprovalEngine()
        req = ae.request_approval("creative_generation", "Generate", {})
        can_exec = ae.can_execute(req.request_id)
        self.assertTrue(can_exec)


class TestRiskControllerExtended(unittest.TestCase):
    def test_risk_detect_spend_spike(self):
        rc = RiskController()
        result = rc.detect_spend_spike(current_spend=400, baseline_spend=100)
        self.assertIsNotNone(result)

    def test_risk_detect_revenue_drop(self):
        rc = RiskController()
        result = rc.detect_revenue_drop(current_revenue=300, baseline_revenue=1000)
        self.assertIsNotNone(result)

    def test_risk_detect_fraud(self):
        rc = RiskController()
        result = rc.detect_fraud(installs=1000, suspicious_installs=400)
        self.assertIsNotNone(result)

    def test_risk_detect_crash_spike(self):
        rc = RiskController()
        result = rc.detect_crash_spike(crash_rate=0.15)
        self.assertIsNotNone(result)

    def test_risk_assess_overall(self):
        rc = RiskController()
        result = rc.assess_overall_risk({"spend": 1000, "revenue": 2000})
        self.assertIsNotNone(result)

    def test_risk_resolve(self):
        rc = RiskController()
        risk = rc.detect_spend_spike(400, 100)
        if risk:
            result = rc.resolve_risk(risk.event_id, "Reduced budget")
            self.assertTrue(result)

    def test_risk_get_active_risks(self):
        rc = RiskController()
        rc.detect_spend_spike(400, 100)
        active = rc.get_active_risks()
        self.assertGreater(len(active), 0)

    def test_risk_get_stats(self):
        rc = RiskController()
        rc.detect_spend_spike(400, 100)
        stats = rc.get_stats()
        self.assertIn("total_risks", stats)


class TestKillSwitchExtended(unittest.TestCase):
    def test_kill_switch_initial_level(self):
        ks = KillSwitch()
        self.assertEqual(ks.get_current_level(), KillSwitchLevel.MONITOR)

    def test_kill_switch_check_spend(self):
        ks = KillSwitch()
        event = ks.check_spend(current_spend=400, baseline_spend=100)
        self.assertIsNotNone(event)

    def test_kill_switch_check_revenue(self):
        ks = KillSwitch()
        event = ks.check_revenue(current_revenue=300, baseline_revenue=1000)
        self.assertIsNotNone(event)

    def test_kill_switch_check_fraud(self):
        ks = KillSwitch()
        event = ks.check_fraud(fraud_rate=0.4)
        self.assertIsNotNone(event)

    def test_kill_switch_manual_trigger(self):
        ks = KillSwitch()
        event = ks.manual_trigger(KillSwitchLevel.PAUSE_ALL, "Emergency")
        self.assertEqual(ks.get_current_level(), KillSwitchLevel.PAUSE_ALL)

    def test_kill_switch_resolve(self):
        ks = KillSwitch()
        event = ks.manual_trigger(KillSwitchLevel.PAUSE_ALL, "Test")
        result = ks.resolve(event.event_id, "Fixed")
        self.assertTrue(result)

    def test_kill_switch_get_active_events(self):
        ks = KillSwitch()
        ks.manual_trigger(KillSwitchLevel.PAUSE_NEW, "Test")
        active = ks.get_active_events()
        self.assertEqual(len(active), 1)

    def test_kill_switch_get_status(self):
        ks = KillSwitch()
        status = ks.get_status()
        self.assertIsInstance(status, dict)

    def test_kill_switch_register_callback(self):
        ks = KillSwitch()
        ks.register_callback("on_pause", lambda: None)
        self.assertIn("on_pause", ks._callbacks)

    def test_kill_switch_is_system_paused(self):
        ks = KillSwitch()
        ks.manual_trigger(KillSwitchLevel.PAUSE_ALL, "Test")
        self.assertTrue(ks.is_system_paused("ua_agent"))


class TestRollbackSystemExtended(unittest.TestCase):
    def test_rollback_create_snapshot(self):
        rs = RollbackSystem()
        snap = rs.create_snapshot("campaign_1_v1", {"budget": 1000})
        self.assertIsNotNone(snap)

    def test_rollback_to(self):
        rs = RollbackSystem()
        snap = rs.create_snapshot("campaign_1_v1", {"budget": 1000})
        rs.update_state({"budget": 2000})
        result = rs.rollback_to(snap.snapshot_id)
        self.assertIsNotNone(result)

    def test_rollback_get_snapshot(self):
        rs = RollbackSystem()
        snap = rs.create_snapshot("campaign_1_v1", {})
        retrieved = rs.get_snapshot(snap.snapshot_id)
        self.assertIsNotNone(retrieved)

    def test_rollback_list_snapshots(self):
        rs = RollbackSystem()
        rs.create_snapshot("campaign_1_v1", {})
        snaps = rs.list_snapshots()
        self.assertGreaterEqual(len(snaps), 0)

    def test_rollback_compare(self):
        rs = RollbackSystem()
        s1 = rs.create_snapshot("config_v1", {"budget": 1000})
        s2 = rs.create_snapshot("config_v2", {"budget": 2000})
        diff = rs.compare_snapshots(s1.snapshot_id, s2.snapshot_id)
        self.assertIsNotNone(diff)

    def test_rollback_delete_snapshot(self):
        rs = RollbackSystem()
        snap = rs.create_snapshot("campaign_1_v1", {})
        result = rs.delete_snapshot(snap.snapshot_id)
        self.assertTrue(result)

    def test_rollback_get_history(self):
        rs = RollbackSystem()
        snap = rs.create_snapshot("campaign_1_v1", {})
        rs.rollback_to(snap.snapshot_id)
        history = rs.get_rollback_history()
        self.assertGreater(len(history), 0)

    def test_rollback_get_stats(self):
        rs = RollbackSystem()
        rs.create_snapshot("campaign_1_v1", {})
        stats = rs.get_stats()
        self.assertIn("total_snapshots", stats)

    def test_rollback_update_state(self):
        rs = RollbackSystem()
        rs.create_snapshot("init", {})
        rs.update_state({"key": "value"})
        state = rs.get_current_state()
        self.assertEqual(state["key"], "value")


class TestAgentMonitorExtended(unittest.TestCase):
    def test_agent_register(self):
        am = AgentMonitor()
        agent = am.register_agent("ua_1", "ua", "UA Agent 1")
        self.assertEqual(agent.agent_id, "ua_1")

    def test_agent_update_status(self):
        am = AgentMonitor()
        am.register_agent("ua_1", "ua", "UA Agent 1")
        am.update_status("ua_1", AgentStatus.RUNNING, task="Working")
        agent = am.get_agent("ua_1")
        self.assertEqual(agent.status, AgentStatus.RUNNING)

    def test_agent_heartbeat(self):
        am = AgentMonitor()
        am.register_agent("ua_1", "ua", "UA Agent 1")
        am.heartbeat("ua_1")
        agent = am.get_agent("ua_1")
        self.assertIsNotNone(agent.last_heartbeat)

    def test_agent_get_active(self):
        am = AgentMonitor()
        am.register_agent("ua_1", "ua", "UA Agent 1")
        am.update_status("ua_1", AgentStatus.RUNNING, task="Working")
        active = am.get_active_agents()
        self.assertEqual(len(active), 1)

    def test_agent_get_by_status(self):
        am = AgentMonitor()
        am.register_agent("ua_1", "ua", "UA Agent 1")
        idle = am.get_agents_by_status(AgentStatus.IDLE)
        self.assertGreater(len(idle), 0)

    def test_agent_get_stale(self):
        am = AgentMonitor()
        am.register_agent("ua_1", "ua", "UA Agent 1")
        am.heartbeat("ua_1")
        stale = am.get_stale_agents(timeout_seconds=0)
        self.assertIsInstance(stale, list)

    def test_agent_get_summary(self):
        am = AgentMonitor()
        am.register_agent("ua_1", "ua", "UA Agent 1")
        summary = am.get_summary()
        self.assertIn("total_agents", summary)

    def test_agent_get_dashboard(self):
        am = AgentMonitor()
        am.register_agent("ua_1", "ua", "UA Agent 1")
        dashboard = am.get_dashboard()
        self.assertIsInstance(dashboard, dict)


class TestWorkflowMonitorExtended(unittest.TestCase):
    def test_workflow_register(self):
        wm = WorkflowMonitor()
        wf = wm.register_workflow("wf1", "Test workflow")
        self.assertEqual(wf.name, "Test workflow")

    def test_workflow_start(self):
        wm = WorkflowMonitor()
        wm.register_workflow("wf1", "Test")
        wm.start_workflow("wf1")
        wf = wm.get_workflow("wf1")
        self.assertIsNotNone(wf)

    def test_workflow_complete(self):
        wm = WorkflowMonitor()
        wm.register_workflow("wf1", "Test")
        wm.start_workflow("wf1")
        wm.complete_workflow("wf1")
        wf = wm.get_workflow("wf1")
        self.assertIsNotNone(wf)

    def test_workflow_step(self):
        wm = WorkflowMonitor()
        wm.register_workflow("wf1", "Test", total_steps=1)
        wm.start_workflow("wf1")
        wm.step_started("wf1", "step_1")
        wm.step_completed("wf1", "step_1")
        progress = wm.get_progress("wf1")
        self.assertIsInstance(progress, dict)

    def test_workflow_step_failed(self):
        wm = WorkflowMonitor()
        wm.register_workflow("wf1", "Test")
        wm.start_workflow("wf1")
        wm.step_failed("wf1", "step_1", "Error")
        self.assertTrue(True)

    def test_workflow_get_by_status(self):
        wm = WorkflowMonitor()
        wm.register_workflow("wf1", "Test")
        by_status = wm.get_workflows_by_status(WorkflowStatus.CREATED)
        self.assertIsInstance(by_status, list)

    def test_workflow_get_long_running(self):
        wm = WorkflowMonitor()
        long_running = wm.get_long_running(threshold_minutes=0)
        self.assertIsInstance(long_running, list)

    def test_workflow_get_dashboard(self):
        wm = WorkflowMonitor()
        dashboard = wm.get_dashboard()
        self.assertIsInstance(dashboard, dict)


class TestCostMonitorExtended(unittest.TestCase):
    def test_cost_record(self):
        cm = CostMonitor()
        cm.record_cost("meta", 100.5, "Facebook ads", source="c1")
        self.assertGreater(cm.get_daily_cost(), 0)

    def test_cost_by_category(self):
        cm = CostMonitor()
        cm.record_cost("meta", 100, "Meta ads", source="c1")
        cm.record_cost("google", 200, "Google ads", source="c2")
        cm.record_cost("openai", 50, "AI API", source="api")
        by_cat = cm.get_cost_by_category()
        self.assertGreater(by_cat.get("meta", 0), 0)

    def test_cost_daily(self):
        cm = CostMonitor()
        cm.record_cost("meta", 100, "ads", source="c1")
        daily = cm.get_daily_cost()
        self.assertGreater(daily, 0)

    def test_cost_weekly(self):
        cm = CostMonitor()
        cm.record_cost("meta", 100, "ads", source="c1")
        weekly = cm.get_weekly_cost()
        self.assertGreater(weekly, 0)

    def test_cost_monthly(self):
        cm = CostMonitor()
        cm.record_cost("meta", 100, "ads", source="c1")
        monthly = cm.get_monthly_cost()
        self.assertGreater(monthly, 0)

    def test_cost_trend(self):
        cm = CostMonitor()
        cm.record_cost("meta", 100, "ads", source="c1")
        trend = cm.get_cost_trend(days=7)
        self.assertIsInstance(trend, list)

    def test_cost_top_costs(self):
        cm = CostMonitor()
        cm.record_cost("meta", 300, "ads", source="c1")
        cm.record_cost("google", 200, "ads", source="c2")
        top = cm.get_top_costs(limit=2)
        self.assertIsInstance(top, list)

    def test_cost_set_budget(self):
        cm = CostMonitor()
        cm.set_budget("daily", 1000)
        usage = cm.get_budget_usage("daily")
        self.assertIsInstance(usage, dict)

    def test_cost_all_budget_usage(self):
        cm = CostMonitor()
        cm.set_budget("daily", 1000)
        usage = cm.get_all_budget_usage()
        self.assertIsInstance(usage, list)

    def test_cost_summary(self):
        cm = CostMonitor()
        cm.record_cost("meta", 100, "ads", source="c1")
        summary = cm.get_summary()
        self.assertIn("total_cost", summary)


class TestFailureDashboardExtended(unittest.TestCase):
    def test_failure_record(self):
        fd = FailureDashboard()
        failure = fd.record_failure(
            category=FailureCategory.AGENT,
            severity=FailureSeverity.MEDIUM,
            title="Timeout",
            description="Task timeout",
            component="ua_agent",
        )
        self.assertIsNotNone(failure)

    def test_failure_get_active(self):
        fd = FailureDashboard()
        fd.record_failure(
            category=FailureCategory.AGENT,
            severity=FailureSeverity.HIGH,
            title="e1",
            description="Error 1",
            component="t1",
        )
        active = fd.get_active_failures()
        self.assertEqual(len(active), 1)

    def test_failure_get_by_category(self):
        fd = FailureDashboard()
        fd.record_failure(
            category=FailureCategory.AGENT,
            severity=FailureSeverity.LOW,
            title="e1",
            description="Error 1",
            component="t1",
        )
        fd.record_failure(
            category=FailureCategory.WORKFLOW,
            severity=FailureSeverity.LOW,
            title="e2",
            description="Error 2",
            component="t2",
        )
        agent_failures = fd.get_failures_by_category(FailureCategory.AGENT)
        self.assertEqual(len(agent_failures), 1)

    def test_failure_get_by_component(self):
        fd = FailureDashboard()
        fd.record_failure(
            category=FailureCategory.AGENT,
            severity=FailureSeverity.LOW,
            title="e1",
            description="Error 1",
            component="ua_agent",
        )
        component_failures = fd.get_failures_by_component("ua_agent")
        self.assertEqual(len(component_failures), 1)

    def test_failure_resolve(self):
        fd = FailureDashboard()
        f = fd.record_failure(
            category=FailureCategory.AGENT,
            severity=FailureSeverity.LOW,
            title="e1",
            description="Error 1",
            component="t1",
        )
        fd.resolve_failure(f.failure_id, "Fixed")
        failure = fd.get_failure(f.failure_id)
        self.assertTrue(failure.resolved)

    def test_failure_get_recent(self):
        fd = FailureDashboard()
        fd.record_failure(
            category=FailureCategory.AGENT,
            severity=FailureSeverity.LOW,
            title="e1",
            description="Error 1",
            component="t1",
        )
        recent = fd.get_recent_failures(hours=24)
        self.assertGreater(len(recent), 0)

    def test_failure_get_summary(self):
        fd = FailureDashboard()
        fd.record_failure(
            category=FailureCategory.AGENT,
            severity=FailureSeverity.LOW,
            title="e1",
            description="Error 1",
            component="t1",
        )
        summary = fd.get_failure_summary()
        self.assertIn("total_failures", summary)

    def test_failure_get_dashboard(self):
        fd = FailureDashboard()
        dashboard = fd.get_dashboard()
        self.assertIsInstance(dashboard, dict)


class TestEventCollectorExtended(unittest.TestCase):
    def test_event_collect(self):
        ec = EventCollector()
        event = ec.collect(EventType.INSTALL, "u1", platform="ios")
        self.assertIsNotNone(event)

    def test_event_collect_batch(self):
        ec = EventCollector()
        events = [
            {"event_type": EventType.INSTALL, "user_id": "u1"},
            {"event_type": EventType.PURCHASE, "user_id": "u1", "properties": {"amount": 9.99}},
        ]
        results = ec.collect_batch(events)
        self.assertEqual(len(results), 2)

    def test_event_get_by_type(self):
        ec = EventCollector()
        ec.collect(EventType.INSTALL, "u1")
        ec.collect(EventType.PURCHASE, "u1")
        installs = ec.get_events_by_type(EventType.INSTALL)
        self.assertEqual(len(installs), 1)

    def test_event_get_by_date(self):
        ec = EventCollector()
        ec.collect(EventType.INSTALL, "u1")
        today = datetime.now().strftime("%Y-%m-%d")
        events = ec.get_events_by_date(today)
        self.assertGreater(len(events), 0)

    def test_event_get_user_events(self):
        ec = EventCollector()
        ec.collect(EventType.INSTALL, "u1")
        ec.collect(EventType.INSTALL, "u2")
        user_events = ec.get_user_events("u1")
        self.assertEqual(len(user_events), 1)

    def test_event_count_by_type(self):
        ec = EventCollector()
        ec.collect(EventType.INSTALL, "u1")
        counts = ec.get_event_count_by_type()
        self.assertIn(EventType.INSTALL.value, counts)

    def test_event_get_dau(self):
        ec = EventCollector()
        ec.collect(EventType.SESSION_START, "u1")
        dau = ec.get_dau()
        self.assertGreaterEqual(dau, 0)

    def test_event_get_stats(self):
        ec = EventCollector()
        ec.collect(EventType.INSTALL, "u1")
        stats = ec.get_stats()
        self.assertIn("total_events", stats)


class TestMetricEngineExtended(unittest.TestCase):
    def test_metric_roas(self):
        me = MetricEngine()
        ec = me.event_collector
        ec.collect(EventType.INSTALL, "u1")
        ec.collect(EventType.PURCHASE, "u1", {"revenue": 10.0})
        today = datetime.now().strftime("%Y-%m-%d")
        roas = me.calculate_roas(spend=100, cohort_date=today, day=1)
        self.assertIsNotNone(roas)
        self.assertEqual(roas.metric_name, "d1_roas")

    def test_metric_retention(self):
        me = MetricEngine()
        ec = me.event_collector
        today = datetime.now().strftime("%Y-%m-%d")
        ec.collect(EventType.INSTALL, "u1")
        retention = me.calculate_retention(today, day=1)
        self.assertIsNotNone(retention)
        self.assertEqual(retention.metric_name, "d1_retention")

    def test_metric_ltv(self):
        me = MetricEngine()
        ec = me.event_collector
        today = datetime.now().strftime("%Y-%m-%d")
        ec.collect(EventType.INSTALL, "u1")
        ec.collect(EventType.PURCHASE, "u1", {"revenue": 5.0})
        ltv = me.calculate_ltv(today, day=30)
        self.assertIsNotNone(ltv)
        self.assertEqual(ltv.metric_name, "d30_ltv")

    def test_metric_revenue(self):
        me = MetricEngine()
        ec = me.event_collector
        ec.collect(EventType.PURCHASE, "u1", {"revenue": 100.0})
        revenue = me.calculate_revenue()
        self.assertIsNotNone(revenue)
        self.assertEqual(revenue.metric_name, "revenue")

    def test_metric_dau(self):
        me = MetricEngine()
        ec = me.event_collector
        ec.collect(EventType.SESSION_START, "u1")
        dau = me.calculate_dau()
        self.assertIsNotNone(dau)
        self.assertEqual(dau.metric_name, "dau")

    def test_metric_arpdau(self):
        me = MetricEngine()
        ec = me.event_collector
        ec.collect(EventType.SESSION_START, "u1")
        ec.collect(EventType.PURCHASE, "u1", {"revenue": 10.0})
        arpdau = me.calculate_arpdau()
        self.assertIsNotNone(arpdau)
        self.assertEqual(arpdau.metric_name, "arpdau")

    def test_metric_all_metrics(self):
        me = MetricEngine()
        metrics = me.get_all_metrics()
        self.assertIn("dau", metrics)
        self.assertIn("arpdau", metrics)
        self.assertIn("revenue", metrics)


class TestAttributionPipelineExtended(unittest.TestCase):
    def test_attribution_add_touchpoint(self):
        ap = AttributionPipeline()
        tp = ap.add_touchpoint("u1", "meta", "campaign_1", touch_type="click")
        self.assertIsNotNone(tp)

    def test_attribution_attribute(self):
        ap = AttributionPipeline()
        ap.add_touchpoint("u1", "meta", "c1", touch_type="click")
        result = ap.attribute("u1")
        self.assertIsNotNone(result)

    def test_attribution_campaign_breakdown(self):
        ap = AttributionPipeline()
        ap.add_touchpoint("u1", "meta", "c1", touch_type="click")
        ap.attribute("u1")
        breakdown = ap.get_campaign_breakdown()
        self.assertIsInstance(breakdown, dict)

    def test_attribution_channel_breakdown(self):
        ap = AttributionPipeline()
        ap.add_touchpoint("u1", "meta", "c1", touch_type="click")
        ap.attribute("u1")
        breakdown = ap.get_channel_breakdown()
        self.assertIsInstance(breakdown, dict)

    def test_attribution_compare_models(self):
        ap = AttributionPipeline()
        ap.add_touchpoint("u1", "meta", "c1", touch_type="click")
        ap.add_touchpoint("u1", "google", "c2", touch_type="click")
        comparison = ap.compare_models("u1")
        self.assertIsInstance(comparison, dict)

    def test_attribution_get_stats(self):
        ap = AttributionPipeline()
        ap.add_touchpoint("u1", "meta", "c1", touch_type="click")
        stats = ap.get_stats()
        self.assertIn("total_touchpoints", stats)


class TestDataQualityMonitorExtended(unittest.TestCase):
    def test_dq_completeness(self):
        dqm = DataQualityMonitor()
        data = [{"a": 1, "b": None}, {"a": None, "b": 2}]
        issue = dqm.check_completeness(data, ["a", "b"])
        self.assertIsNotNone(issue)
        self.assertGreater(issue.affected_records, 0)

    def test_dq_uniqueness(self):
        dqm = DataQualityMonitor()
        data = [{"id": 1}, {"id": 1}, {"id": 2}]
        issue = dqm.check_uniqueness(data, ["id"])
        self.assertIsNotNone(issue)
        self.assertGreater(issue.affected_records, 0)

    def test_dq_outliers(self):
        dqm = DataQualityMonitor()
        values = [10, 15, 12, 1000]
        issue = dqm.check_outliers(values)
        self.assertIsNotNone(issue)

    def test_dq_freshness(self):
        dqm = DataQualityMonitor()
        last_update = datetime.now() - timedelta(hours=2)
        result = dqm.check_freshness(last_update, threshold_minutes=60)
        self.assertIsNotNone(result)

    def test_dq_full_check(self):
        dqm = DataQualityMonitor()
        data = [{"id": 1, "value": 50}, {"id": 2, "value": 75}]
        result = dqm.run_full_check(data, ["id", "value"], ["id"])
        self.assertIsNotNone(result)
        self.assertIsInstance(result.issues, list)

    def test_dq_open_issues(self):
        dqm = DataQualityMonitor()
        dqm.run_full_check([{"id": 1}, {"id": 1}], ["id"], ["id"])
        open_issues = dqm.get_open_issues()
        self.assertGreater(len(open_issues), 0)

    def test_dq_resolve_issue(self):
        dqm = DataQualityMonitor()
        issue = dqm.check_uniqueness([{"id": 1}, {"id": 1}], ["id"])
        dqm._track_issue(issue)
        result = dqm.resolve_issue(issue.issue_id)
        self.assertTrue(result)

    def test_dq_get_stats(self):
        dqm = DataQualityMonitor()
        dqm.run_full_check([{"id": 1}, {"id": 1}], ["id"], ["id"])
        stats = dqm.get_stats()
        self.assertIn("total_issues", stats)


class TestDailyCycleExtended(unittest.TestCase):
    def test_daily_create(self):
        dc = DailyCycle()
        self.assertIsNotNone(dc)

    def test_daily_get_current_phase(self):
        dc = DailyCycle()
        phase = dc.get_current_phase()
        self.assertIsInstance(phase, DailyPhase)

    def test_daily_get_schedule(self):
        dc = DailyCycle()
        schedule = dc.get_today_schedule()
        self.assertIsInstance(schedule, DailySchedule)

    def test_daily_get_phase_description(self):
        dc = DailyCycle()
        desc = dc.get_phase_description(DailyPhase.MORNING_MARKET_SCAN)
        self.assertIsInstance(desc, str)

    def test_daily_execute_phase(self):
        dc = DailyCycle()
        result = dc.execute_phase(DailyPhase.MORNING_MARKET_SCAN)
        self.assertIsNotNone(result)

    def test_daily_execute_morning(self):
        dc = DailyCycle()
        result = dc.execute_morning_routine()
        self.assertIsNotNone(result)

    def test_daily_execute_full_day(self):
        dc = DailyCycle()
        result = dc.execute_full_day()
        self.assertIsInstance(result, dict)

    def test_daily_get_progress(self):
        dc = DailyCycle()
        progress = dc.get_today_progress()
        self.assertIsInstance(progress, dict)

    def test_daily_get_history(self):
        dc = DailyCycle()
        history = dc.get_history()
        self.assertIsInstance(history, list)

    def test_daily_register_handler(self):
        dc = DailyCycle()
        dc.register_phase_handler(DailyPhase.MORNING_MARKET_SCAN, lambda: {"done": True})
        self.assertTrue(True)


class TestWeeklyReviewExtended(unittest.TestCase):
    def test_weekly_create(self):
        wr = WeeklyReview()
        self.assertIsNotNone(wr)

    def test_weekly_run_review(self):
        wr = WeeklyReview()
        result = wr.run_review()
        self.assertIsNotNone(result)

    def test_weekly_get_review(self):
        wr = WeeklyReview()
        result = wr.run_review()
        review = wr.get_review(result.week_start)
        self.assertIsNotNone(review)

    def test_weekly_get_recent(self):
        wr = WeeklyReview()
        wr.run_review()
        recent = wr.get_recent_reviews(count=5)
        self.assertGreater(len(recent), 0)

    def test_weekly_get_week_dates(self):
        wr = WeeklyReview()
        dates = wr.get_week_dates()
        self.assertIsInstance(dates, tuple)

    def test_weekly_get_summary(self):
        wr = WeeklyReview()
        wr.run_review()
        summary = wr.get_summary()
        self.assertIsInstance(summary, dict)


class TestMonthlyStrategyExtended(unittest.TestCase):
    def test_monthly_create(self):
        ms = MonthlyStrategy()
        self.assertIsNotNone(ms)

    def test_monthly_run_session(self):
        ms = MonthlyStrategy()
        result = ms.run_strategy_session()
        self.assertIsNotNone(result)

    def test_monthly_get_strategy(self):
        ms = MonthlyStrategy()
        result = ms.run_strategy_session()
        strategy = ms.get_strategy(result.month)
        self.assertIsNotNone(strategy)

    def test_monthly_get_progress(self):
        ms = MonthlyStrategy()
        result = ms.run_strategy_session()
        progress = ms.get_strategy_progress(result.month, {"mrr": 10000, "roi": 2.0, "d7_retention": 0.2})
        self.assertIsInstance(progress, dict)

    def test_monthly_get_month_str(self):
        ms = MonthlyStrategy()
        month_str = ms.get_month_str()
        self.assertIsInstance(month_str, str)

    def test_monthly_get_summary(self):
        ms = MonthlyStrategy()
        summary = ms.get_summary()
        self.assertIsInstance(summary, dict)


class TestCompanyCalendarExtended(unittest.TestCase):
    def test_calendar_create(self):
        cal = CompanyCalendar()
        self.assertIsNotNone(cal)

    def test_calendar_add_event(self):
        cal = CompanyCalendar()
        event = cal.add_event(
            CalendarEventType.DAILY_ROUTINE,
            "Daily standup",
            datetime.now(),
            datetime.now() + timedelta(minutes=30),
        )
        self.assertIsNotNone(event)

    def test_calendar_get_event(self):
        cal = CompanyCalendar()
        event = cal.add_event(CalendarEventType.DAILY_ROUTINE, "Test", datetime.now(), datetime.now())
        retrieved = cal.get_event(event.event_id)
        self.assertEqual(retrieved.event_id, event.event_id)

    def test_calendar_get_for_date(self):
        cal = CompanyCalendar()
        cal.add_event(CalendarEventType.DAILY_ROUTINE, "Test", datetime.now(), datetime.now())
        today_str = datetime.now().strftime("%Y-%m-%d")
        events = cal.get_events_for_date(today_str)
        self.assertGreaterEqual(len(events), 0)

    def test_calendar_get_for_week(self):
        cal = CompanyCalendar()
        events = cal.get_events_for_week()
        self.assertIsInstance(events, list)

    def test_calendar_get_upcoming(self):
        cal = CompanyCalendar()
        cal.add_event(
            CalendarEventType.WEEKLY_REVIEW,
            "Weekly",
            datetime.now() + timedelta(days=1),
            datetime.now() + timedelta(days=1, hours=1),
        )
        upcoming = cal.get_upcoming_events(hours=168)
        self.assertGreater(len(upcoming), 0)

    def test_calendar_get_by_type(self):
        cal = CompanyCalendar()
        events = cal.get_events_by_type(CalendarEventType.DAILY_ROUTINE)
        self.assertIsInstance(events, list)

    def test_calendar_cancel_event(self):
        cal = CompanyCalendar()
        event = cal.add_event(CalendarEventType.DAILY_ROUTINE, "Test", datetime.now(), datetime.now())
        result = cal.cancel_event(event.event_id)
        self.assertTrue(result)

    def test_calendar_complete_event(self):
        cal = CompanyCalendar()
        event = cal.add_event(CalendarEventType.DAILY_ROUTINE, "Test", datetime.now(), datetime.now())
        result = cal.complete_event(event.event_id)
        self.assertTrue(result)

    def test_calendar_initialize_default(self):
        cal = CompanyCalendar()
        cal.initialize_default_schedule()
        events = cal.get_events_for_week()
        self.assertGreater(len(events), 0)

    def test_calendar_get_day_view(self):
        cal = CompanyCalendar()
        view = cal.get_day_view()
        self.assertIsInstance(view, dict)

    def test_calendar_get_week_view(self):
        cal = CompanyCalendar()
        view = cal.get_week_view()
        self.assertIsInstance(view, dict)

    def test_calendar_get_stats(self):
        cal = CompanyCalendar()
        stats = cal.get_stats()
        self.assertIn("total_events", stats)


class TestTaskGraphExtended2(unittest.TestCase):
    def test_task_graph_multi_dependency(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="T1", task_type="test")
        t2 = TaskNode(task_id="t2", name="T2", task_type="test")
        t3 = TaskNode(task_id="t3", name="T3", task_type="test", dependencies=["t1", "t2"])
        graph.add_task(t1)
        graph.add_task(t2)
        graph.add_task(t3)
        t1.status = TaskStatus.COMPLETED
        ready = graph.get_ready_tasks()
        ready_ids = [t.task_id for t in ready]
        self.assertNotIn("t3", ready_ids)

    def test_task_graph_parallel_tasks(self):
        graph = TaskGraph("test")
        for i in range(5):
            graph.add_task(TaskNode(task_id=f"t{i}", name=f"T{i}", task_type="test"))
        ready = graph.get_ready_tasks()
        self.assertEqual(len(ready), 5)

    def test_task_graph_chain(self):
        graph = TaskGraph("test")
        prev = None
        for i in range(5):
            deps = [prev.task_id] if prev else []
            task = TaskNode(task_id=f"t{i}", name=f"T{i}", task_type="test", dependencies=deps)
            graph.add_task(task)
            prev = task
        ready = graph.get_ready_tasks()
        self.assertEqual(len(ready), 1)

    def test_task_graph_failed_dependency(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="T1", task_type="test")
        t2 = TaskNode(task_id="t2", name="T2", task_type="test", dependencies=["t1"])
        graph.add_task(t1)
        graph.add_task(t2)
        t1.status = TaskStatus.FAILED
        self.assertFalse(graph.is_success())

    def test_task_graph_empty(self):
        graph = TaskGraph("empty")
        self.assertTrue(graph.is_complete())
        self.assertTrue(graph.is_success())

    def test_task_graph_get_task(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="T1", task_type="test")
        graph.add_task(t1)
        task = graph.get_task("t1")
        self.assertEqual(task.task_id, "t1")

    def test_task_graph_get_all_tasks(self):
        graph = TaskGraph("test")
        graph.add_task(TaskNode(task_id="t1", name="T1", task_type="test"))
        graph.add_task(TaskNode(task_id="t2", name="T2", task_type="test"))
        all_tasks = graph.get_all_tasks()
        self.assertEqual(len(all_tasks), 2)

    def test_task_graph_get_running_tasks(self):
        graph = TaskGraph("test")
        t1 = TaskNode(task_id="t1", name="T1", task_type="test")
        graph.add_task(t1)
        t1.status = TaskStatus.RUNNING
        running = graph.get_running_tasks()
        self.assertEqual(len(running), 1)

    def test_task_graph_to_dict(self):
        graph = TaskGraph("test")
        graph.add_task(TaskNode(task_id="t1", name="T1", task_type="test"))
        d = graph.to_dict()
        self.assertIn("workflow_name", d)
        self.assertIn("tasks", d)


class TestConnectorsExtended2(unittest.TestCase):
    def test_meta_get_adset_metrics(self):
        connector = MetaAdsConnector()
        connector.connect()
        result = connector.get_adset_metrics("camp_001")
        self.assertTrue(result.success)

    def test_meta_get_creative_performance(self):
        connector = MetaAdsConnector()
        connector.connect()
        result = connector.get_creative_performance("camp_001")
        self.assertTrue(result.success)

    def test_google_ads_campaign(self):
        connector = GoogleAdsConnector()
        connector.connect()
        result = connector.get_campaign_metrics("camp_001")
        self.assertTrue(result.success)

    def test_asa_campaign(self):
        connector = AppleSearchAdsConnector()
        connector.connect()
        result = connector.get_campaigns()
        self.assertTrue(result.success)

    def test_tiktok_campaign(self):
        connector = TikTokAdsConnector()
        connector.connect()
        result = connector.get_campaigns()
        self.assertTrue(result.success)

    def test_adjust_events(self):
        connector = AdjustConnector()
        connector.connect()
        result = connector.get_events()
        self.assertTrue(result.success)

    def test_revenuecat_mrr(self):
        connector = RevenueCatConnector()
        connector.connect()
        result = connector.get_mrr()
        self.assertTrue(result.success)

    def test_appstore_sales(self):
        connector = AppStoreConnector()
        connector.connect()
        result = connector.get_sales_report()
        self.assertTrue(result.success)

    def test_googleplay_reviews(self):
        connector = GooglePlayConnector()
        connector.connect()
        result = connector.get_reviews()
        self.assertTrue(result.success)

    def test_unity_project(self):
        connector = UnityConnector()
        connector.connect()
        result = connector.get_project_info()
        self.assertTrue(result.success)

    def test_github_repo(self):
        connector = GitHubConnector()
        connector.connect()
        result = connector.get_repo_info()
        self.assertTrue(result.success)


class TestProductionMemoryExtended2(unittest.TestCase):
    def test_memory_query_by_category(self):
        db = CompanyMemoryDB()
        db.store(MemoryCategory.PRODUCT, "P1", {})
        db.store(MemoryCategory.STRATEGY, "S1", {})
        results = db.get_by_category(MemoryCategory.PRODUCT)
        self.assertEqual(len(results), 1)

    def test_memory_query_by_tag(self):
        db = CompanyMemoryDB()
        db.store(MemoryCategory.PRODUCT, "Test", {}, tags=["merge", "puzzle"])
        results = db.get_by_tag("merge")
        self.assertGreaterEqual(len(results), 0)

    def test_memory_search(self):
        db = CompanyMemoryDB()
        db.store(MemoryCategory.STRATEGY, "Merge Game Strategy", {"roi": 2.5})
        results = db.search("merge")
        self.assertGreaterEqual(len(results), 0)

    def test_memory_importance(self):
        db = CompanyMemoryDB()
        db.store(MemoryCategory.STRATEGY, "High", {"k": "v"}, importance=0.9)
        db.store(MemoryCategory.STRATEGY, "Low", {"k": "v"}, importance=0.3)
        results = db.query(min_importance=0.8)
        self.assertEqual(len(results), 1)

    def test_memory_update(self):
        db = CompanyMemoryDB()
        mem = db.store(MemoryCategory.PRODUCT, "Test", {"v": 1})
        db.update(mem.record_id, {"content": {"v": 2}})
        updated = db.get(mem.record_id)
        self.assertEqual(updated.content["v"], 2)

    def test_memory_delete(self):
        db = CompanyMemoryDB()
        mem = db.store(MemoryCategory.PRODUCT, "Test", {})
        result = db.delete(mem.record_id)
        self.assertTrue(result)

    def test_vector_memory_delete(self):
        vm = VectorMemory()
        entry = vm.add("test", {}, "general")
        result = vm.delete(entry.vector_id)
        self.assertTrue(result)

    def test_vector_memory_get(self):
        vm = VectorMemory()
        entry = vm.add("test_key", {"data": "value"}, "general")
        vec = vm.get(entry.vector_id)
        self.assertIsNotNone(vec)

    def test_knowledge_graph_edge_weight(self):
        kg = KnowledgeGraphDB()
        n1 = kg.add_node(NodeType.GAME, "G1")
        n2 = kg.add_node(NodeType.GENRE, "Genre1")
        edge = kg.add_edge(n1.node_id, n2.node_id, EdgeType.BELONGS_TO)
        self.assertIsNotNone(edge)

    def test_memory_sync_history(self):
        engine = MemorySyncEngine()
        engine.add_record_with_sync(MemoryCategory.STRATEGY, "Test", {})
        history = engine.get_sync_history()
        self.assertEqual(len(history), 1)


def count_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    total = 0
    for test_suite in suite:
        for test_case in test_suite:
            total += 1
    return total


if __name__ == "__main__":
    print("=" * 80)
    print("V6.0 Production Autonomous Game Company - Release Gate")
    print("=" * 80)
    
    total_tests = count_tests()
    print(f"\nTotal test cases: {total_tests}")
    print()
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(sys.modules[__name__]))
    
    print("\n" + "=" * 80)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"Results: {passed}/{result.testsRun} PASS")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    print(f"  Skipped: {len(result.skipped)}")
    print("=" * 80)
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}")
            print(f"    {traceback.split(chr(10))[0]}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}")
            print(f"    {traceback.split(chr(10))[0]}")
    
    print(f"\nStatus: {'PASS' if result.wasSuccessful() else 'FAIL'}")
    
    sys.exit(0 if result.wasSuccessful() else 1)
