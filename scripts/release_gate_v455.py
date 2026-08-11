#!/usr/bin/env python3
"""V4.5.5 Production Observability Patch Release Gate.

Tests 8 modules for production visibility:
1. Dashboard - Runtime summary generation
2. Runtime Metrics - Generation and queue metrics
3. Creative Metrics - QA and winner tracking
4. Cost Report - Daily cost and platform analysis
5. Winner Report - Top creative DNA
6. DNA Extraction - Winner pattern analysis
7. Anomaly Detection - Cost/QA/CTR anomaly detection
8. Alert System - Alert creation and management

Target: 15/15 PASS
"""

import sys
import os
from pathlib import Path
import json
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

PASS_COUNT = 0
FAIL_COUNT = 0
TEST_RESULTS = []


def test(name: str, passed: bool, details: str = "") -> None:
    global PASS_COUNT, FAIL_COUNT, TEST_RESULTS
    status = "PASS" if passed else "FAIL"
    if passed:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1
    TEST_RESULTS.append({"test": name, "status": status, "details": details})
    print(f"[{status}] {name}")
    if details:
        print(f"    {details}")


def test_dashboard():
    print("\n=== Test 1: Dashboard ===")
    from market_ops.video_generation.observability import RuntimeDashboard
    
    dashboard = RuntimeDashboard()
    summary = dashboard.generate_demo()
    
    test("Dashboard Generation", summary.date == "2026-07-08", f"Date: {summary.date}")
    test("Generation Summary", summary.generation.total == 842, f"Total: {summary.generation.total}")
    test("Queue Summary", summary.queue.pending == 20, f"Pending: {summary.queue.pending}")
    test("Cost Summary", summary.cost.total == 320.5, f"Cost: ${summary.cost.total}")
    test("Platform Count", len(summary.platforms) == 3, f"Platforms: {len(summary.platforms)}")
    
    # Save & load
    path = dashboard.save_dashboard(summary)
    loaded = dashboard.load_dashboard("2026-07-08")
    test("Dashboard Persistence", loaded is not None and loaded.generation.total == 842, f"Path: {path}")
    
    # Markdown export
    md = dashboard.export_markdown(summary)
    test("Markdown Export", "# Daily Runtime Dashboard" in md, "Has header")


def test_runtime_metrics():
    print("\n=== Test 2: Runtime Metrics ===")
    from market_ops.video_generation.observability import RuntimeMetricsCollector
    
    collector = RuntimeMetricsCollector()
    
    # Record generations
    collector.record_generation(success=True, duration=45.0)
    collector.record_generation(success=True, duration=50.0)
    collector.record_generation(success=False, duration=30.0)
    
    collector.record_worker_stats(active=8, max_workers=10)
    collector.record_queue_latency(12.5)
    
    metrics = collector.finalize()
    
    test("Generation Count", metrics.generation_count == 3, f"Count: {metrics.generation_count}")
    test("Success Rate", metrics.success_rate == 2/3, f"Rate: {metrics.success_rate:.3f}")
    test("Worker Utilization", metrics.worker_utilization == 0.8, f"Util: {metrics.worker_utilization}")
    test("Queue Latency", metrics.queue_latency == 12.5, f"Latency: {metrics.queue_latency}")


def test_creative_metrics():
    print("\n=== Test 3: Creative Metrics ===")
    from market_ops.video_generation.observability import CreativeMetricsCollector, CreativeMetric
    
    collector = CreativeMetricsCollector()
    
    collector.record_creative(CreativeMetric(
        creative_id="v001", platform="kling", qa_score=88.0, visual_score=90.0,
        hook_score=82.0, conversion_score=75.0, passed_qa=True
    ))
    collector.record_creative(CreativeMetric(
        creative_id="v002", platform="veo", qa_score=55.0, visual_score=60.0,
        hook_score=50.0, conversion_score=45.0, passed_qa=False
    ))
    collector.record_winner("v001")
    
    daily = collector.get_daily_metrics()
    
    test("Creative Generated", daily.creative_generated == 2, f"Generated: {daily.creative_generated}")
    test("QA Pass Count", daily.creative_pass_qa == 1, f"Passed: {daily.creative_pass_qa}")
    test("Winner Count", daily.winner_count == 1, f"Winners: {daily.winner_count}")
    test("Top Creatives", len(collector.get_top_creatives("qa_score", 5)) == 2, f"Top: 2")


def test_performance_metrics():
    print("\n=== Test 4: Performance Metrics ===")
    from market_ops.video_generation.observability import PerformanceMetricsCollector, PerformanceMetric
    
    collector = PerformanceMetricsCollector()
    
    collector.record(PerformanceMetric(creative_id="v001", ctr=5.8, ipm=83, purchase_rate=4.1, roas_d7=1.8))
    collector.record(PerformanceMetric(creative_id="v001", ctr=4.2, ipm=65, purchase_rate=3.2, roas_d7=1.5))
    collector.record(PerformanceMetric(creative_id="v002", ctr=2.1, ipm=30, purchase_rate=1.2, roas_d7=0.8))
    
    perf = collector.get_creative_performance("v001")
    test("Creative Performance", perf is not None and perf.avg_ctr == 5.0, f"CTR: {perf.avg_ctr if perf else 0}")
    
    winners = collector.get_winners(limit=10)
    test("Winners Detection", len(winners) == 1, f"Winners: {len(winners)}")
    
    test("Winner CTR Threshold", winners[0].avg_ctr >= 3.0, f"CTR: {winners[0].avg_ctr}")


def test_cost_report():
    print("\n=== Test 5: Cost Report ===")
    from market_ops.video_generation.observability import DailyCostReporter, PlatformCostAnalyzer
    
    reporter = DailyCostReporter(daily_budget=500.0)
    report = reporter.generate_demo()
    
    test("Daily Cost Report", report.total_cost == 385.0, f"Cost: ${report.total_cost}")
    test("Avg Cost", report.avg_cost == 0.385, f"Avg: ${report.avg_cost}")
    test("Budget Remaining", report.budget_remaining == 115.0, f"Remaining: ${report.budget_remaining}")
    
    analyzer = PlatformCostAnalyzer()
    platform_data = [
        {"platform": "kling", "count": 500, "cost": 250.0, "success_rate": 0.97, "avg_time": 45.0},
        {"platform": "veo", "count": 200, "cost": 110.0, "success_rate": 0.95, "avg_time": 60.0},
        {"platform": "comfyui", "count": 300, "cost": 25.0, "success_rate": 0.98, "avg_time": 120.0},
    ]
    analysis = analyzer.analyze(platform_data)
    
    test("Platform Analysis", len(analysis.platforms) == 3, f"Platforms: {len(analysis.platforms)}")
    test("Recommendation", len(analysis.recommendation) > 0, f"Rec: {analysis.recommendation[:50]}...")
    test("Efficiency Ranking", analysis.platforms[0].platform == "comfyui", f"Best: {analysis.platforms[0].platform}")


def test_winner_report():
    print("\n=== Test 6: Winner Report ===")
    from market_ops.video_generation.observability import WinnerReporter
    
    reporter = WinnerReporter()
    winners = reporter.generate_demo()
    
    test("Winner Count", len(winners) == 3, f"Winners: {len(winners)}")
    test("Winner Ranking", winners[0].rank == 1, f"Rank 1: {winners[0].creative_id}")
    test("Winner CTR", winners[0].ctr >= 5.0, f"CTR: {winners[0].ctr}%")
    
    text = reporter.generate_text_report(2)
    test("Text Report", "TOP Creative DNA" in text, "Has header")


def test_dna_extraction():
    print("\n=== Test 7: DNA Extraction ===")
    from market_ops.video_generation.observability import DNAExtractor
    
    extractor = DNAExtractor()
    dna = extractor.generate_demo()
    
    test("DNA Patterns", len(dna.patterns) >= 2, f"Patterns: {len(dna.patterns)}")
    test("Top Camera", dna.top_elements.get("camera") == "close-up", f"Camera: {dna.top_elements.get('camera')}")
    test("Top Lighting", dna.top_elements.get("lighting") == "warm", f"Lighting: {dna.top_elements.get('lighting')}")
    test("Top Hook", dna.top_elements.get("hook") == "action", f"Hook: {dna.top_elements.get('hook')}")
    
    report = extractor.generate_report_text(dna)
    test("DNA Report Text", "Winner DNA Pattern" in report, "Has header")


def test_anomaly_detection():
    print("\n=== Test 8: Anomaly Detection ===")
    from market_ops.video_generation.observability import (
        AnomalyDetector, ThresholdManager, ThresholdPolicy,
        AlertManager, AlertSeverity, AlertType,
    )
    
    detector = AnomalyDetector()
    
    # Set baselines
    detector.threshold.set_baseline("avg_cost", 0.30)
    detector.threshold.set_baseline("qa_score", 85.0)
    detector.threshold.set_baseline("ctr", 4.0)
    
    # Test cost spike
    cost_alert = detector.detect_cost_spike(0.55)
    test("Cost Spike Detection", cost_alert, "Cost spike detected")
    
    # Test QA drop
    qa_alert = detector.detect_quality_drop(55.0)
    test("QA Drop Detection", qa_alert, "QA drop detected")
    
    # Test creative fatigue
    ctr_alert = detector.detect_creative_fatigue(1.5)
    test("Creative Fatigue Detection", ctr_alert, "Fatigue detected")
    
    # Test success rate drop
    sr_alert = detector.detect_success_rate_drop(0.85)
    test("Success Rate Drop Detection", sr_alert, "Success rate drop detected")
    
    # Test queue backlog
    qb_alert = detector.detect_queue_backlog(100, 5)
    test("Queue Backlog Detection", qb_alert, "Queue backlog detected")
    
    # Scan all
    detected = detector.scan_all({"avg_cost": 0.60, "qa_score": 50.0, "ctr": 1.0, "success_rate": 0.80})
    test("Scan All", len(detected) >= 2, f"Detected: {len(detected)} anomalies")
    
    # Alert summary
    summary = detector.get_alert_summary()
    test("Alert Summary", summary["total"] >= 4, f"Total alerts: {summary['total']}")
    test("Active Alerts", summary["active"] >= 4, f"Active: {summary['active']}")


def print_summary():
    print("\n" + "=" * 50)
    print("V4.5.5 Production Observability Patch Release Gate")
    print("=" * 50)
    print(f"\nResults: {PASS_COUNT}/{PASS_COUNT + FAIL_COUNT} PASS")
    
    if FAIL_COUNT == 0:
        print("\n✓ ALL TESTS PASSED - V4.5.5 RELEASE APPROVED")
        print("\nSystem now has full production visibility.")
    else:
        print(f"\n✗ {FAIL_COUNT} TESTS FAILED")
        for r in TEST_RESULTS:
            if r["status"] == "FAIL":
                print(f"  - {r['test']}")
    
    output = {
        "version": "V4.5.5",
        "timestamp": datetime.now().isoformat(),
        "pass_count": PASS_COUNT,
        "fail_count": FAIL_COUNT,
        "passed": FAIL_COUNT == 0,
        "results": TEST_RESULTS,
    }
    
    output_path = Path(__file__).parent.parent / "data" / "release_gate_v455_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: {output_path}")


def main():
    print("=" * 50)
    print("V4.5.5 Production Observability Patch Release Gate")
    print("=" * 50)
    print("\nTesting 8 modules for production visibility...")
    print("Target: 15/15 PASS\n")
    
    test_dashboard()
    test_runtime_metrics()
    test_creative_metrics()
    test_performance_metrics()
    test_cost_report()
    test_winner_report()
    test_dna_extraction()
    test_anomaly_detection()
    
    print_summary()
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
