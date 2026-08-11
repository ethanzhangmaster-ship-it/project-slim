#!/usr/bin/env python3
"""V4.5.4 Production Hardening Patch Release Gate.

Tests 8 modules for production readiness:
1. State Machine - Generation state transitions
2. Queue System - Priority and retry queues
3. Retry Logic - Dead letter queue handling
4. Cost Controller - Budget and cost estimation
5. Asset Lineage - Video-to-Blueprint tracking
6. QA Agent - Visual and Marketing quality
7. Recovery - Failure detection and auto recovery
8. Load Test - Production stress and resilience

Target: 8/8 PASS
"""

import sys
import os
from pathlib import Path
import json
import sqlite3
from datetime import datetime
import random

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Test counter
PASS_COUNT = 0
FAIL_COUNT = 0
TEST_RESULTS = []


def test(name: str, passed: bool, details: str = "") -> None:
    """Record test result."""
    global PASS_COUNT, FAIL_COUNT, TEST_RESULTS
    
    status = "PASS" if passed else "FAIL"
    if passed:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1
    
    result = {
        "test": name,
        "status": status,
        "details": details
    }
    TEST_RESULTS.append(result)
    
    print(f"[{status}] {name}")
    if details:
        print(f"    {details}")


def test_state_machine() -> None:
    """Test 1: Generation State Machine."""
    print("\n=== Test 1: State Machine ===")
    
    from market_ops.video_generation.production.state_machine import (
        GenerationState,
        StateTransition,
        StateStore,
        TransitionRecord
    )
    
    # Test state enumeration
    states = list(GenerationState)
    expected_states = ["created", "queued", "processing", "success", "failed", "retrying", "cancelled"]
    state_values = [s.value for s in states]
    
    test(
        "State Enumeration",
        set(state_values) == set(expected_states),
        f"States: {state_values}"
    )
    
    # Test state transition
    valid = StateTransition.can_transition(GenerationState.CREATED, GenerationState.QUEUED)
    test(
        "Valid Transition CREATED→QUEUED",
        valid,
        f"Allowed: {valid}"
    )
    
    # Test invalid transition
    invalid = StateTransition.can_transition(GenerationState.SUCCESS, GenerationState.PROCESSING)
    test(
        "Invalid Transition SUCCESS→PROCESSING",
        not invalid,
        f"Blocked: {not invalid}"
    )
    
    # Test transition execution
    record = StateTransition.transition("gen_001", GenerationState.CREATED, GenerationState.QUEUED, "Initial queue")
    test(
        "Transition Execution",
        record.generation_id == "gen_001",
        f"Recorded: {record.from_state} → {record.to_state}"
    )
    
    # Test state store
    store = StateStore()
    store.record_transition(record)
    
    history = store.get_transition_history("gen_001")
    test(
        "State Store Persistence",
        len(history) >= 1,
        f"Records: {len(history)}"
    )


def test_queue_system() -> None:
    """Test 2: Queue System."""
    print("\n=== Test 2: Queue System ===")
    
    from market_ops.video_generation.production.queue import (
        Job,
        JobQueue,
        PriorityQueue,
        RetryQueue,
        DeadLetterQueue
    )
    
    # Test job creation
    job = Job(
        job_id="job_001",
        priority="P0",
        platform="kling"
    )
    test(
        "Job Creation",
        job.job_id == "job_001",
        f"Job: {job.job_id}, Priority: {job.priority}"
    )
    
    # Test priority queue
    pq = PriorityQueue()
    pq.enqueue(Job(job_id="p1_job", priority="P1", platform="kling"))
    pq.enqueue(Job(job_id="p0_job", priority="P0", platform="veo"))
    pq.enqueue(Job(job_id="p2_job", priority="P2", platform="runway"))
    
    # P0 should be first
    first = pq.dequeue()
    test(
        "Priority Queue Ordering",
        first.priority == "P0",
        f"First: {first.job_id} (Priority {first.priority})"
    )
    
    # Test retry queue
    rq = RetryQueue()
    rq.add(Job(job_id="retry_001", priority="P1", platform="kling", retry_count=1), delay=5.0)
    
    pending = rq.size()
    test(
        "Retry Queue",
        pending >= 1,
        f"Pending retries: {pending}"
    )
    
    # Test dead letter queue
    dlq = DeadLetterQueue()
    dlq.add(Job(job_id="failed_001", priority="P1", platform="kling", retry_count=3), reason="max_retries")
    
    dead_jobs = dlq.size()
    test(
        "Dead Letter Queue",
        dead_jobs == 1,
        f"Dead jobs: {dead_jobs}"
    )


def test_retry_logic() -> None:
    """Test 3: Retry Logic."""
    print("\n=== Test 3: Retry Logic ===")
    
    from market_ops.video_generation.production.queue import (
        Job,
        RetryQueue,
        DeadLetterQueue
    )
    
    rq = RetryQueue()
    dlq = DeadLetterQueue()
    
    # Test retry cycle
    job = Job(job_id="retry_test", priority="P1", platform="kling", max_retries=3)
    
    # Simulate retries
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        rq.add(job)
        retry_count += 1
    
    # After 3 retries, should go to DLQ
    if job.retry_count >= max_retries:
        dlq.add(job, reason="max_retries_exceeded")
    
    test(
        "Retry Exhaustion",
        job.retry_count >= max_retries,
        f"Retries: {job.retry_count}/{max_retries}"
    )
    
    test(
        "Dead Letter Queue Entry",
        dlq.size() >= 1,
        f"DLQ size: {dlq.size()}"
    )


def test_cost_controller() -> None:
    """Test 4: Cost Controller."""
    print("\n=== Test 4: Cost Controller ===")
    
    from market_ops.video_generation.production.cost import (
        CostController,
        CostEstimate,
        CostPredictor,
        BudgetPolicyManager
    )
    
    # Test cost estimation
    controller = CostController()
    
    blueprint = {
        "scene": "witch treasure",
        "duration": 15,
        "resolution": "1080p"
    }
    
    estimate = controller.estimate(blueprint, platform="kling", creative_score=75)
    
    test(
        "Cost Estimation",
        estimate.estimated_cost > 0,
        f"Cost: ${estimate.estimated_cost:.2f}"
    )
    
    test(
        "Platform Recommendation",
        estimate.recommended_platform in ["kling", "veo", "runway", "comfyui"],
        f"Recommended: {estimate.recommended_platform}"
    )
    
    # Test budget policy manager
    policy_mgr = BudgetPolicyManager()
    
    can_afford = policy_mgr.can_afford(estimate.estimated_cost)
    test(
        "Budget Check",
        can_afford,
        f"Daily budget: ${policy_mgr.policy.daily_budget}, Cost: ${estimate.estimated_cost:.2f}"
    )
    
    # Test cost predictor
    predictor = CostPredictor()
    prediction = predictor.predict("gen_001", "kling", 10, "720p")
    
    test(
        "Cost Prediction",
        prediction > 0,
        f"Predicted: ${prediction:.2f}"
    )


def test_asset_lineage() -> None:
    """Test 5: Asset Lineage."""
    print("\n=== Test 5: Asset Lineage ===")
    
    from market_ops.video_generation.production.lineage import (
        AssetNode,
        AssetGraph,
        LineageStore
    )
    
    # Test asset node
    node = AssetNode(
        asset_id="video_001",
        parent_id="blueprint_12",
        asset_type="video",
        prompt_dna="witch treasure opening",
        platform="kling",
        seed=88392
    )
    
    test(
        "Asset Node Creation",
        node.asset_id == "video_001",
        f"Asset: {node.asset_id}, Parent: {node.parent_id}"
    )
    
    # Test asset graph
    graph = AssetGraph()
    graph.add_node(node)
    
    # Add child node
    child = AssetNode(
        asset_id="video_002",
        parent_id="video_001",
        asset_type="video",
        platform="veo"
    )
    graph.add_node(child)
    
    lineage = graph.get_lineage("video_002")
    test(
        "Lineage Trace",
        len(lineage) >= 1,
        f"Ancestors: {len(lineage)}"
    )
    
    # Test lineage store
    store = LineageStore()
    store.save(node)
    
    retrieved = store.load("video_001")
    test(
        "Lineage Store Persistence",
        retrieved is not None and retrieved.asset_id == "video_001",
        f"Retrieved: {retrieved.asset_id if retrieved else 'None'}"
    )


def test_qa_agent() -> None:
    """Test 6: QA Agent."""
    print("\n=== Test 6: QA Agent ===")
    
    from market_ops.video_generation.production.qa_agent import (
        QAScorer,
        QAScore,
        QAGrade,
        VisualChecker,
        MarketingChecker
    )
    
    # Test visual checker
    visual = VisualChecker()
    result = visual.check("sample_video.mp4", "test_001")
    
    test(
        "Visual QA Check",
        len(result.scores) == 5,
        f"Checked: blur, artifact, flicker, frame_error, bad_generation"
    )
    
    test(
        "Visual Issue Detection",
        result.passed or len(result.issues) > 0,
        f"Issues: {len(result.issues)}"
    )
    
    # Test marketing checker
    marketing = MarketingChecker()
    blueprint = {
        "hook_elements": ["question", "movement"],
        "product_focus": True,
        "cta_type": "button"
    }
    
    mkt_result = marketing.check("sample_video.mp4", "test_001", blueprint)
    
    test(
        "Marketing QA Check",
        len(mkt_result.dimension_scores) == 4,
        f"Dimensions: hook, product_visibility, cta, emotion"
    )
    
    # Test QA scorer
    scorer = QAScorer()
    qa_score = scorer.score("sample_video.mp4", "test_001", blueprint)
    
    test(
        "QA Score Calculation",
        qa_score.final_score > 0,
        f"Visual: {qa_score.visual_score:.1f}, Hook: {qa_score.hook_score:.1f}, Conversion: {qa_score.conversion_score:.1f}"
    )
    
    test(
        "QA Grade Assignment",
        qa_score.grade in [QAGrade.EXCELLENT, QAGrade.GOOD, QAGrade.ACCEPTABLE, QAGrade.BELOW_STANDARD, QAGrade.POOR],
        f"Grade: {qa_score.grade.value}"
    )


def test_recovery() -> None:
    """Test 7: Recovery System."""
    print("\n=== Test 7: Recovery System ===")
    
    from market_ops.video_generation.production.recovery import (
        FailureDetector,
        AutoRecovery,
        CheckpointManager,
        FailureType,
        FailureSeverity
    )
    
    # Test failure detector
    detector = FailureDetector()
    
    timeout_error = TimeoutError("API timeout after 120s")
    failure = detector.detect(timeout_error, "gen_001", "kling")
    
    test(
        "Failure Detection",
        failure.failure_type == FailureType.API_TIMEOUT,
        f"Type: {failure.failure_type.value}"
    )
    
    test(
        "Failure Classification",
        failure.severity in [FailureSeverity.LOW, FailureSeverity.MEDIUM, FailureSeverity.HIGH, FailureSeverity.CRITICAL],
        f"Severity: {failure.severity.value}"
    )
    
    # Test auto recovery
    recovery = AutoRecovery()
    result = recovery.auto_recover(timeout_error, "gen_001", "kling")
    
    test(
        "Auto Recovery Execution",
        result.success or result.attempt_number > 0,
        f"Attempt: {result.attempt_number}, Success: {result.success}"
    )
    
    # Test checkpoint manager
    checkpoint_mgr = CheckpointManager()
    checkpoint = checkpoint_mgr.create_checkpoint(
        generation_id="gen_001",
        platform="kling",
        worker_id="worker_01",
        blueprint_id="bp_001"
    )
    
    test(
        "Checkpoint Creation",
        checkpoint.checkpoint_id.startswith("ckpt_"),
        f"Checkpoint: {checkpoint.checkpoint_id}"
    )
    
    checkpoint_mgr.update_checkpoint(checkpoint.checkpoint_id, "api_call_started")
    checkpoint_mgr.fail_checkpoint(checkpoint.checkpoint_id, "API timeout")
    
    recovery_data = checkpoint_mgr.get_recovery_data(checkpoint.checkpoint_id)
    test(
        "Checkpoint Recovery Data",
        "next_step" in recovery_data,
        f"Next step: {recovery_data.get('next_step', 'N/A')}"
    )


def test_load_test() -> None:
    """Test 8: Production Load Test."""
    print("\n=== Test 8: Load Test ===")
    
    from market_ops.video_generation.production.load_test import (
        RuntimeStressTest,
        FailureInjectionTest,
        FailureScenario
    )
    
    # Test runtime stress
    stress_tester = RuntimeStressTest()
    
    # Run standard scenario
    result = stress_tester.run_scenario("standard")
    
    test(
        "Runtime Stress Test",
        result.success_rate >= 90.0,
        f"Success rate: {result.success_rate:.1f}%"
    )
    
    test(
        "Throughput Test",
        result.jobs_per_second > 0,
        f"Jobs/sec: {result.jobs_per_second:.1f}"
    )
    
    # Test failure injection
    failure_tester = FailureInjectionTest()
    
    # Test API outage scenario
    api_result = failure_tester.run_test(FailureScenario.API_OUTAGE, num_failures=5)
    
    test(
        "Failure Injection - API Outage",
        api_result.recovery_rate >= 90.0,
        f"Recovery rate: {api_result.recovery_rate:.1f}%"
    )
    
    test(
        "Platform Switch Recovery",
        api_result.platform_switches > 0,
        f"Platform switches: {api_result.platform_switches}"
    )
    
    # Test worker crash scenario
    crash_result = failure_tester.run_test(FailureScenario.WORKER_CRASH, num_failures=5)
    
    test(
        "Failure Injection - Worker Crash",
        crash_result.recovery_rate >= 80.0,
        f"Recovery rate: {crash_result.recovery_rate:.1f}%"
    )


def print_summary() -> None:
    """Print final summary."""
    print("\n" + "=" * 50)
    print("V4.5.4 Production Hardening Patch Release Gate")
    print("=" * 50)
    
    print(f"\nResults: {PASS_COUNT}/{PASS_COUNT + FAIL_COUNT} PASS")
    
    if FAIL_COUNT == 0:
        print("\n✓ ALL TESTS PASSED - V4.5.4 RELEASE APPROVED")
        print("\nSystem ready for 7×24 production operation.")
    else:
        print(f"\n✗ {FAIL_COUNT} TESTS FAILED")
        print("\nFailed tests:")
        for result in TEST_RESULTS:
            if result["status"] == "FAIL":
                print(f"  - {result['test']}")
    
    # Save results
    output = {
        "version": "V4.5.4",
        "timestamp": datetime.now().isoformat(),
        "pass_count": PASS_COUNT,
        "fail_count": FAIL_COUNT,
        "passed": FAIL_COUNT == 0,
        "results": TEST_RESULTS
    }
    
    output_path = Path(__file__).parent.parent / "data" / "release_gate_v454_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to: {output_path}")


def main() -> None:
    """Run all tests."""
    print("=" * 50)
    print("V4.5.4 Production Hardening Patch Release Gate")
    print("=" * 50)
    print("\nTesting 8 modules for production readiness...")
    print("Target: 8/8 PASS\n")
    
    # Run all tests
    test_state_machine()
    test_queue_system()
    test_retry_logic()
    test_cost_controller()
    test_asset_lineage()
    test_qa_agent()
    test_recovery()
    test_load_test()
    
    # Print summary
    print_summary()
    
    # Exit code
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()