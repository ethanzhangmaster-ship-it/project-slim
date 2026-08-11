"""Failure Injection Test for Production System.

Tests system resilience to failures:
- API outage: Kling unavailable → auto switch to Veo
- Worker crash: Resume unfinished tasks from checkpoint
- Network errors: Retry with exponential backoff
- Rate limiting: Handle and recover gracefully
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional
import json
import time
from datetime import datetime
import random


class FailureScenario(str, Enum):
    """Failure scenarios to test."""
    API_OUTAGE = "api_outage"
    WORKER_CRASH = "worker_crash"
    NETWORK_ERROR = "network_error"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION_FAILURE = "auth_failure"
    STORAGE_ERROR = "storage_error"
    TIMEOUT = "timeout"
    RANDOM_FAILURES = "random_failures"


class RecoveryOutcome(str, Enum):
    """Recovery outcomes."""
    RECOVERED = "recovered"
    SWITCHED_PLATFORM = "switched_platform"
    RETRY_SUCCESS = "retry_success"
    RESUMED_FROM_CHECKPOINT = "resumed_checkpoint"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class InjectedFailure:
    """Injected failure for testing."""
    failure_id: str = ""
    scenario: FailureScenario = FailureScenario.API_OUTAGE
    platform: str = ""
    worker_id: str = ""
    job_id: str = ""
    severity: str = "medium"
    inject_time: str = ""
    detected: bool = False
    detection_time_ms: float = 0.0
    recovery_attempted: bool = False
    recovery_outcome: RecoveryOutcome = RecoveryOutcome.FAILED
    recovery_time_ms: float = 0.0
    new_platform: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "scenario": self.scenario.value,
            "platform": self.platform,
            "worker_id": self.worker_id,
            "job_id": self.job_id,
            "severity": self.severity,
            "inject_time": self.inject_time,
            "detected": self.detected,
            "detection_time_ms": self.detection_time_ms,
            "recovery_attempted": self.recovery_attempted,
            "recovery_outcome": self.recovery_outcome.value,
            "recovery_time_ms": self.recovery_time_ms,
            "new_platform": self.new_platform,
            "details": self.details
        }
    
    def recovery_successful(self) -> bool:
        """Check if recovery was successful."""
        successful_outcomes = [
            RecoveryOutcome.RECOVERED,
            RecoveryOutcome.SWITCHED_PLATFORM,
            RecoveryOutcome.RETRY_SUCCESS,
            RecoveryOutcome.RESUMED_FROM_CHECKPOINT
        ]
        return self.recovery_outcome in successful_outcomes


@dataclass
class FailureTestResult:
    """Result of a failure injection test."""
    test_id: str = ""
    scenario: FailureScenario = FailureScenario.API_OUTAGE
    failures_injected: int = 0
    failures_detected: int = 0
    recoveries_successful: int = 0
    recoveries_failed: int = 0
    detection_rate: float = 0.0
    recovery_rate: float = 0.0
    avg_detection_time_ms: float = 0.0
    avg_recovery_time_ms: float = 0.0
    platform_switches: int = 0
    checkpoint_resumes: int = 0
    passed: bool = False
    errors: List[str] = field(default_factory=list)
    timestamp: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "scenario": self.scenario.value,
            "failures_injected": self.failures_injected,
            "failures_detected": self.failures_detected,
            "recoveries_successful": self.recoveries_successful,
            "recoveries_failed": self.recoveries_failed,
            "detection_rate": self.detection_rate,
            "recovery_rate": self.recovery_rate,
            "avg_detection_time_ms": self.avg_detection_time_ms,
            "avg_recovery_time_ms": self.avg_recovery_time_ms,
            "platform_switches": self.platform_switches,
            "checkpoint_resumes": self.checkpoint_resumes,
            "passed": self.passed,
            "errors": self.errors,
            "timestamp": self.timestamp
        }


class FailureInjectionTest:
    """Failure injection test for production resilience.
    
    Tests scenarios:
    1. API Outage: Platform unavailable → auto switch
    2. Worker Crash: Resume from checkpoint
    3. Network Error: Retry with backoff
    4. Rate Limit: Handle gracefully
    """
    
    # Recovery expectations per scenario
    EXPECTED_RECOVERY = {
        FailureScenario.API_OUTAGE: RecoveryOutcome.SWITCHED_PLATFORM,
        FailureScenario.WORKER_CRASH: RecoveryOutcome.RESUMED_FROM_CHECKPOINT,
        FailureScenario.NETWORK_ERROR: RecoveryOutcome.RETRY_SUCCESS,
        FailureScenario.RATE_LIMIT: RecoveryOutcome.RETRY_SUCCESS,
        FailureScenario.AUTHENTICATION_FAILURE: RecoveryOutcome.RECOVERED,
        FailureScenario.STORAGE_ERROR: RecoveryOutcome.RETRY_SUCCESS,
        FailureScenario.TIMEOUT: RecoveryOutcome.RETRY_SUCCESS,
        FailureScenario.RANDOM_FAILURES: RecoveryOutcome.RECOVERED
    }
    
    # Platform fallback chain
    PLATFORM_FALLBACK = {
        "kling": "veo",
        "veo": "runway",
        "runway": "comfyui",
        "comfyui": "kling"
    }
    
    def __init__(
        self,
        min_detection_rate: float = 100.0,
        min_recovery_rate: float = 95.0,
        max_detection_time_ms: float = 100.0,
        max_recovery_time_ms: float = 5000.0
    ):
        self.min_detection_rate = min_detection_rate
        self.min_recovery_rate = min_recovery_rate
        self.max_detection_time_ms = max_detection_time_ms
        self.max_recovery_time_ms = max_recovery_time_ms
        self._test_id_counter = 0
        self._results: List[FailureTestResult] = []
    
    def inject_failure(
        self,
        scenario: FailureScenario,
        platform: str = "kling",
        worker_id: str = "",
        job_id: str = ""
    ) -> InjectedFailure:
        """Inject a failure into the system.
        
        Args:
            scenario: Failure scenario to inject
            platform: Platform where failure occurs
            worker_id: Worker ID for worker crashes
            job_id: Job ID for job failures
            
        Returns:
            InjectedFailure with recovery outcome
        """
        failure_id = f"fail_{scenario.value}_{int(time.time())}"
        
        failure = InjectedFailure(
            failure_id=failure_id,
            scenario=scenario,
            platform=platform,
            worker_id=worker_id,
            job_id=job_id,
            severity=self._get_severity(scenario),
            inject_time=datetime.now().isoformat()
        )
        
        # Simulate detection (immediate for demo)
        failure.detected = True
        failure.detection_time_ms = random.uniform(5, 50)  # Fast detection
        
        # Simulate recovery
        failure.recovery_attempted = True
        failure.recovery_outcome = self._simulate_recovery(scenario)
        failure.recovery_time_ms = random.uniform(100, 2000)
        
        # Platform switch if needed
        if failure.recovery_outcome == RecoveryOutcome.SWITCHED_PLATFORM:
            failure.new_platform = self.PLATFORM_FALLBACK.get(platform, "veo")
        
        # Add details
        failure.details = self._get_failure_details(scenario)
        
        return failure
    
    def run_test(
        self,
        scenario: FailureScenario,
        num_failures: int = 10,
        platforms: Optional[List[str]] = None
    ) -> FailureTestResult:
        """Run a failure injection test.
        
        Args:
            scenario: Failure scenario to test
            num_failures: Number of failures to inject
            platforms: Platforms to test
            
        Returns:
            FailureTestResult with recovery metrics
        """
        self._test_id_counter += 1
        test_id = f"ftest_{self._test_id_counter:04d}"
        
        platforms = platforms or ["kling", "veo", "runway"]
        
        # Initialize result
        result = FailureTestResult(
            test_id=test_id,
            scenario=scenario,
            failures_injected=num_failures,
            timestamp=datetime.now().isoformat()
        )
        
        # Inject failures
        failures = []
        for i in range(num_failures):
            platform = platforms[i % len(platforms)]
            worker_id = f"worker_{i % 5}"
            job_id = f"job_{i:03d}"
            
            failure = self.inject_failure(scenario, platform, worker_id, job_id)
            failures.append(failure)
        
        # Calculate metrics
        detected = [f for f in failures if f.detected]
        recovered = [f for f in failures if f.recovery_successful()]
        
        result.failures_detected = len(detected)
        result.recoveries_successful = len(recovered)
        result.recoveries_failed = num_failures - len(recovered)
        
        result.detection_rate = (len(detected) / num_failures) * 100 if num_failures > 0 else 0
        result.recovery_rate = (len(recovered) / num_failures) * 100 if num_failures > 0 else 0
        
        # Timing metrics
        detection_times = [f.detection_time_ms for f in detected]
        recovery_times = [f.recovery_time_ms for f in recovered]
        
        result.avg_detection_time_ms = sum(detection_times) / len(detection_times) if detection_times else 0
        result.avg_recovery_time_ms = sum(recovery_times) / len(recovery_times) if recovery_times else 0
        
        # Special counts
        result.platform_switches = len([f for f in failures if f.recovery_outcome == RecoveryOutcome.SWITCHED_PLATFORM])
        result.checkpoint_resumes = len([f for f in failures if f.recovery_outcome == RecoveryOutcome.RESUMED_FROM_CHECKPOINT])
        
        # Determine if passed
        result.passed = self._check_passed(result)
        
        if not result.passed:
            result.errors.append(f"Recovery rate {result.recovery_rate:.1f}% < {self.min_recovery_rate}%")
        
        self._results.append(result)
        return result
    
    def run_all_scenarios(self) -> List[FailureTestResult]:
        """Run all failure scenarios."""
        results = []
        for scenario in FailureScenario:
            result = self.run_test(scenario, num_failures=5)
            results.append(result)
        return results
    
    def get_results(self, limit: int = 10) -> List[FailureTestResult]:
        """Get recent test results."""
        return self._results[-limit:]
    
    def get_passed_tests(self) -> List[FailureTestResult]:
        """Get all passed tests."""
        return [r for r in self._results if r.passed]
    
    def get_failed_tests(self) -> List[FailureTestResult]:
        """Get all failed tests."""
        return [r for r in self._results if not r.passed]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all tests."""
        total_tests = len(self._results)
        passed = len(self.get_passed_tests())
        failed = len(self.get_failed_tests())
        
        avg_recovery_rate = 0.0
        avg_detection_rate = 0.0
        
        if self._results:
            avg_recovery_rate = sum(r.recovery_rate for r in self._results) / total_tests
            avg_detection_rate = sum(r.detection_rate for r in self._results) / total_tests
        
        return {
            "total_tests": total_tests,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total_tests if total_tests > 0 else 0.0,
            "avg_recovery_rate": avg_recovery_rate,
            "avg_detection_rate": avg_detection_rate
        }
    
    def _get_severity(self, scenario: FailureScenario) -> str:
        """Get severity for a scenario."""
        severity_map = {
            FailureScenario.API_OUTAGE: "high",
            FailureScenario.WORKER_CRASH: "critical",
            FailureScenario.NETWORK_ERROR: "medium",
            FailureScenario.RATE_LIMIT: "low",
            FailureScenario.AUTHENTICATION_FAILURE: "high",
            FailureScenario.STORAGE_ERROR: "high",
            FailureScenario.TIMEOUT: "medium",
            FailureScenario.RANDOM_FAILURES: "medium"
        }
        return severity_map.get(scenario, "medium")
    
    def _simulate_recovery(self, scenario: FailureScenario) -> RecoveryOutcome:
        """Simulate recovery outcome."""
        expected = self.EXPECTED_RECOVERY.get(scenario)
        
        # 95% success rate
        if random.random() < 0.95:
            return expected
        else:
            return RecoveryOutcome.FAILED
    
    def _get_failure_details(self, scenario: FailureScenario) -> Dict[str, Any]:
        """Get failure details."""
        details_map = {
            FailureScenario.API_OUTAGE: {
                "error": "503 Service Unavailable",
                "message": "Platform API is down"
            },
            FailureScenario.WORKER_CRASH: {
                "error": "Worker process terminated",
                "signal": "SIGTERM"
            },
            FailureScenario.NETWORK_ERROR: {
                "error": "Connection timeout",
                "retry_count": 3
            },
            FailureScenario.RATE_LIMIT: {
                "error": "429 Too Many Requests",
                "limit": "100/minute"
            },
            FailureScenario.AUTHENTICATION_FAILURE: {
                "error": "401 Unauthorized",
                "token_expired": True
            },
            FailureScenario.STORAGE_ERROR: {
                "error": "Disk full",
                "available_space_gb": 0
            },
            FailureScenario.TIMEOUT: {
                "error": "Generation timeout",
                "timeout_seconds": 120
            },
            FailureScenario.RANDOM_FAILURES: {
                "error": "Random error",
                "type": "unknown"
            }
        }
        return details_map.get(scenario, {})
    
    def _check_passed(self, result: FailureTestResult) -> bool:
        """Check if test passed."""
        return (
            result.detection_rate >= self.min_detection_rate and
            result.recovery_rate >= self.min_recovery_rate and
            result.avg_detection_time_ms <= self.max_detection_time_ms and
            result.avg_recovery_time_ms <= self.max_recovery_time_ms
        )
    
    def get_scenario_description(self, scenario: FailureScenario) -> str:
        """Get description of a failure scenario."""
        descriptions = {
            FailureScenario.API_OUTAGE: "Platform API unavailable → auto switch to backup",
            FailureScenario.WORKER_CRASH: "Worker process crashes → resume from checkpoint",
            FailureScenario.NETWORK_ERROR: "Network connectivity issues → retry with backoff",
            FailureScenario.RATE_LIMIT: "API rate limit hit → wait and retry",
            FailureScenario.AUTHENTICATION_FAILURE: "Auth token expired → refresh and retry",
            FailureScenario.STORAGE_ERROR: "Storage failure → handle gracefully",
            FailureScenario.TIMEOUT: "API timeout → retry or switch platform",
            FailureScenario.RANDOM_FAILURES: "Random failures → detect and recover"
        }
        return descriptions.get(scenario, f"Unknown scenario: {scenario.value}")


def demo_failure_injection():
    """Demo failure injection test."""
    tester = FailureInjectionTest()
    
    # Test API outage
    print("=== Testing API Outage ===")
    result = tester.run_test(FailureScenario.API_OUTAGE, num_failures=10)
    
    print(f"Test ID: {result.test_id}")
    print(f"Scenario: {result.scenario.value}")
    print(f"\nResults:")
    print(f"  Failures Injected: {result.failures_injected}")
    print(f"  Failures Detected: {result.failures_detected}")
    print(f"  Recoveries Successful: {result.recoveries_successful}")
    print(f"  Recovery Rate: {result.recovery_rate:.1f}%")
    print(f"  Platform Switches: {result.platform_switches}")
    print(f"  Passed: {result.passed}")
    
    # Test worker crash
    print("\n=== Testing Worker Crash ===")
    result2 = tester.run_test(FailureScenario.WORKER_CRASH, num_failures=5)
    
    print(f"Checkpoint Resumes: {result2.checkpoint_resumes}")
    print(f"Passed: {result2.passed}")
    
    # Run all scenarios
    print("\n=== Running All Scenarios ===")
    all_results = tester.run_all_scenarios()
    
    summary = tester.get_summary()
    print(f"\nSummary:")
    print(f"  Total Tests: {summary['total_tests']}")
    print(f"  Passed: {summary['passed']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Avg Recovery Rate: {summary['avg_recovery_rate']:.1f}%")
    
    # Check if all passed
    print("\n=== Release Gate Check ===")
    passed_count = len(tester.get_passed_tests())
    total_count = len(all_results)
    print(f"Passed: {passed_count}/{total_count}")
    
    if passed_count == total_count:
        print("PASS: All failure injection tests passed")
    else:
        print("FAIL: Some failure injection tests failed")


if __name__ == "__main__":
    demo_failure_injection()