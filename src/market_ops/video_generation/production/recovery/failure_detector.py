"""Failure Detector for Generation Tasks.

Detects and categorizes failures during video generation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional
import json
from datetime import datetime


class FailureType(str, Enum):
    """Types of generation failures."""
    API_TIMEOUT = "api_timeout"
    API_ERROR = "api_error"
    PLATFORM_UNAVAILABLE = "platform_unavailable"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION_ERROR = "auth_error"
    NETWORK_ERROR = "network_error"
    GENERATION_FAILED = "generation_failed"
    DOWNLOAD_FAILED = "download_failed"
    STORAGE_ERROR = "storage_error"
    WORKER_CRASH = "worker_crash"
    UNKNOWN = "unknown"


class FailureSeverity(str, Enum):
    """Failure severity levels."""
    LOW = "low"  # Can retry immediately
    MEDIUM = "medium"  # Retry with delay
    HIGH = "high"  # Switch platform or abort
    CRITICAL = "critical"  # System-wide issue


@dataclass
class FailureRecord:
    """Record of a detected failure."""
    failure_id: str = ""
    generation_id: str = ""
    failure_type: FailureType = FailureType.UNKNOWN
    severity: FailureSeverity = FailureSeverity.MEDIUM
    platform: str = ""
    timestamp: str = ""
    message: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "generation_id": self.generation_id,
            "failure_type": self.failure_type.value,
            "severity": self.severity.value,
            "platform": self.platform,
            "timestamp": self.timestamp,
            "message": self.message,
            "context": self.context,
            "recoverable": self.recoverable
        }


@dataclass
class FailurePattern:
    """Pattern of recurring failures."""
    pattern_id: str = ""
    failure_type: FailureType = FailureType.UNKNOWN
    count: int = 0
    platforms: List[str] = field(default_factory=list)
    first_occurrence: str = ""
    last_occurrence: str = ""
    avg_interval_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "failure_type": self.failure_type.value,
            "count": self.count,
            "platforms": self.platforms,
            "first_occurrence": self.first_occurrence,
            "last_occurrence": self.last_occurrence,
            "avg_interval_seconds": self.avg_interval_seconds
        }


class FailureDetector:
    """Detects and categorizes generation failures.
    
    Features:
    - Real-time failure detection
    - Failure type classification
    - Severity assessment
    - Pattern recognition for recurring issues
    - Recovery recommendations
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or "data/failures.json"
        self._failure_history: List[FailureRecord] = []
        self._patterns: Dict[FailureType, FailurePattern] = {}
        self._failure_id_counter = 0
    
    def detect(
        self,
        error: Exception,
        generation_id: str = "",
        platform: str = "",
        context: Optional[Dict[str, Any]] = None
    ) -> FailureRecord:
        """Detect and classify a failure.
        
        Args:
            error: Exception that occurred
            generation_id: ID of the generation task
            platform: Platform where failure occurred
            context: Additional context about the failure
            
        Returns:
            FailureRecord with classification and recovery recommendation
        """
        # Generate failure ID
        self._failure_id_counter += 1
        failure_id = f"fail_{self._failure_id_counter:04d}"
        
        # Classify failure type
        failure_type = self._classify_failure(error)
        
        # Determine severity
        severity = self._determine_severity(failure_type, error)
        
        # Determine if recoverable
        recoverable = self._is_recoverable(failure_type, severity)
        
        # Create record
        record = FailureRecord(
            failure_id=failure_id,
            generation_id=generation_id,
            failure_type=failure_type,
            severity=severity,
            platform=platform,
            timestamp=datetime.now().isoformat(),
            message=str(error),
            context=context or {},
            recoverable=recoverable
        )
        
        # Add to history
        self._failure_history.append(record)
        
        # Update patterns
        self._update_patterns(record)
        
        return record
    
    def detect_timeout(
        self,
        generation_id: str,
        platform: str,
        timeout_seconds: float,
        expected_seconds: float = 60.0
    ) -> FailureRecord:
        """Detect a timeout failure.
        
        Args:
            generation_id: ID of the generation task
            platform: Platform where timeout occurred
            timeout_seconds: Actual timeout duration
            expected_seconds: Expected completion time
            
        Returns:
            FailureRecord for timeout
        """
        self._failure_id_counter += 1
        failure_id = f"fail_{self._failure_id_counter:04d}"
        
        severity = FailureSeverity.HIGH if timeout_seconds > expected_seconds * 2 else FailureSeverity.MEDIUM
        
        record = FailureRecord(
            failure_id=failure_id,
            generation_id=generation_id,
            failure_type=FailureType.API_TIMEOUT,
            severity=severity,
            platform=platform,
            timestamp=datetime.now().isoformat(),
            message=f"Timeout after {timeout_seconds}s (expected {expected_seconds}s)",
            context={
                "timeout_seconds": timeout_seconds,
                "expected_seconds": expected_seconds
            },
            recoverable=True
        )
        
        self._failure_history.append(record)
        self._update_patterns(record)
        
        return record
    
    def detect_platform_unavailable(self, platform: str) -> FailureRecord:
        """Detect platform unavailable failure.
        
        Args:
            platform: Platform that is unavailable
            
        Returns:
            FailureRecord for platform unavailable
        """
        self._failure_id_counter += 1
        failure_id = f"fail_{self._failure_id_counter:04d}"
        
        record = FailureRecord(
            failure_id=failure_id,
            generation_id="",
            failure_type=FailureType.PLATFORM_UNAVAILABLE,
            severity=FailureSeverity.HIGH,
            platform=platform,
            timestamp=datetime.now().isoformat(),
            message=f"Platform {platform} is unavailable",
            context={"platform": platform},
            recoverable=True
        )
        
        self._failure_history.append(record)
        self._update_patterns(record)
        
        return record
    
    def detect_worker_crash(self, worker_id: str) -> FailureRecord:
        """Detect worker crash failure.
        
        Args:
            worker_id: ID of crashed worker
            
        Returns:
            FailureRecord for worker crash
        """
        self._failure_id_counter += 1
        failure_id = f"fail_{self._failure_id_counter:04d}"
        
        record = FailureRecord(
            failure_id=failure_id,
            generation_id="",
            failure_type=FailureType.WORKER_CRASH,
            severity=FailureSeverity.CRITICAL,
            platform="",
            timestamp=datetime.now().isoformat(),
            message=f"Worker {worker_id} crashed",
            context={"worker_id": worker_id},
            recoverable=True
        )
        
        self._failure_history.append(record)
        self._update_patterns(record)
        
        return record
    
    def get_recent_failures(self, limit: int = 10) -> List[FailureRecord]:
        """Get recent failures."""
        return self._failure_history[-limit:]
    
    def get_failures_by_type(self, failure_type: FailureType) -> List[FailureRecord]:
        """Get failures by type."""
        return [f for f in self._failure_history if f.failure_type == failure_type]
    
    def get_failures_by_platform(self, platform: str) -> List[FailureRecord]:
        """Get failures by platform."""
        return [f for f in self._failure_history if f.platform == platform]
    
    def get_patterns(self) -> Dict[FailureType, FailurePattern]:
        """Get detected failure patterns."""
        return self._patterns
    
    def get_recovery_recommendation(self, record: FailureRecord) -> str:
        """Get recovery recommendation for a failure."""
        recommendations = {
            FailureType.API_TIMEOUT: "Retry with exponential backoff, or switch to backup platform",
            FailureType.API_ERROR: "Check API response, retry with adjusted parameters",
            FailureType.PLATFORM_UNAVAILABLE: "Switch to alternative platform (veo, kling, runway)",
            FailureType.RATE_LIMIT: "Wait for rate limit reset, then retry",
            FailureType.AUTHENTICATION_ERROR: "Refresh authentication token, retry",
            FailureType.NETWORK_ERROR: "Check network connectivity, retry",
            FailureType.GENERATION_FAILED: "Adjust prompt parameters, retry with different seed",
            FailureType.DOWNLOAD_FAILED: "Retry download, check storage availability",
            FailureType.STORAGE_ERROR: "Check storage capacity, retry",
            FailureType.WORKER_CRASH: "Restart worker, resume from checkpoint",
            FailureType.UNKNOWN: "Log for investigation, attempt retry"
        }
        return recommendations.get(record.failure_type, "No recommendation available")
    
    def get_severity_description(self, severity: FailureSeverity) -> str:
        """Get description of severity level."""
        descriptions = {
            FailureSeverity.LOW: "Minor issue, retry immediately",
            FailureSeverity.MEDIUM: "Moderate issue, retry with delay",
            FailureSeverity.HIGH: "Significant issue, consider switching platform",
            FailureSeverity.CRITICAL: "Critical issue, requires system-level intervention"
        }
        return descriptions.get(severity, "Unknown severity")
    
    def _classify_failure(self, error: Exception) -> FailureType:
        """Classify failure type from exception."""
        error_name = type(error).__name__
        error_message = str(error).lower()
        
        # Map exception types to failure types
        if "timeout" in error_message or "TimeoutError" in error_name:
            return FailureType.API_TIMEOUT
        elif "rate" in error_message or "limit" in error_message:
            return FailureType.RATE_LIMIT
        elif "auth" in error_message or "token" in error_message:
            return FailureType.AUTHENTICATION_ERROR
        elif "network" in error_message or "connection" in error_message:
            return FailureType.NETWORK_ERROR
        elif "unavailable" in error_message or "offline" in error_message:
            return FailureType.PLATFORM_UNAVAILABLE
        elif "download" in error_message:
            return FailureType.DOWNLOAD_FAILED
        elif "storage" in error_message or "disk" in error_message:
            return FailureType.STORAGE_ERROR
        elif "generation" in error_message:
            return FailureType.GENERATION_FAILED
        else:
            return FailureType.UNKNOWN
    
    def _determine_severity(
        self,
        failure_type: FailureType,
        error: Exception
    ) -> FailureSeverity:
        """Determine severity from failure type and error."""
        severity_map = {
            FailureType.API_TIMEOUT: FailureSeverity.MEDIUM,
            FailureType.API_ERROR: FailureSeverity.MEDIUM,
            FailureType.PLATFORM_UNAVAILABLE: FailureSeverity.HIGH,
            FailureType.RATE_LIMIT: FailureSeverity.LOW,
            FailureType.AUTHENTICATION_ERROR: FailureSeverity.HIGH,
            FailureType.NETWORK_ERROR: FailureSeverity.MEDIUM,
            FailureType.GENERATION_FAILED: FailureSeverity.MEDIUM,
            FailureType.DOWNLOAD_FAILED: FailureSeverity.LOW,
            FailureType.STORAGE_ERROR: FailureSeverity.HIGH,
            FailureType.WORKER_CRASH: FailureSeverity.CRITICAL,
            FailureType.UNKNOWN: FailureSeverity.MEDIUM
        }
        return severity_map.get(failure_type, FailureSeverity.MEDIUM)
    
    def _is_recoverable(
        self,
        failure_type: FailureType,
        severity: FailureSeverity
    ) -> bool:
        """Determine if failure is recoverable."""
        # All failures except critical are potentially recoverable
        if severity == FailureSeverity.CRITICAL:
            return False
        return True
    
    def _update_patterns(self, record: FailureRecord) -> None:
        """Update failure patterns."""
        pattern = self._patterns.get(record.failure_type)
        
        if pattern is None:
            pattern = FailurePattern(
                pattern_id=f"pattern_{record.failure_type.value}",
                failure_type=record.failure_type,
                count=1,
                platforms=[record.platform] if record.platform else [],
                first_occurrence=record.timestamp,
                last_occurrence=record.timestamp
            )
        else:
            pattern.count += 1
            pattern.last_occurrence = record.timestamp
            if record.platform and record.platform not in pattern.platforms:
                pattern.platforms.append(record.platform)
        
        self._patterns[record.failure_type] = pattern


def demo_failure_detector():
    """Demo failure detector functionality."""
    detector = FailureDetector()
    
    # Simulate various failures
    timeout_error = TimeoutError("API call timed out after 120 seconds")
    record1 = detector.detect(timeout_error, "gen_001", "kling")
    
    rate_limit_error = Exception("Rate limit exceeded: 100 requests per minute")
    record2 = detector.detect(rate_limit_error, "gen_002", "veo")
    
    auth_error = Exception("Authentication token expired")
    record3 = detector.detect(auth_error, "gen_003", "runway")
    
    # Detect platform unavailable
    record4 = detector.detect_platform_unavailable("kling")
    
    # Detect worker crash
    record5 = detector.detect_worker_crash("worker_01")
    
    print("=== Failure Records ===")
    for record in detector.get_recent_failures(5):
        print(f"\n{record.failure_id}:")
        print(f"  Type: {record.failure_type.value}")
        print(f"  Severity: {record.severity.value}")
        print(f"  Platform: {record.platform}")
        print(f"  Recoverable: {record.recoverable}")
        print(f"  Recommendation: {detector.get_recovery_recommendation(record)}")
    
    print("\n=== Failure Patterns ===")
    for failure_type, pattern in detector.get_patterns().items():
        print(f"\n{failure_type.value}:")
        print(f"  Count: {pattern.count}")
        print(f"  Platforms: {pattern.platforms}")


if __name__ == "__main__":
    demo_failure_detector()