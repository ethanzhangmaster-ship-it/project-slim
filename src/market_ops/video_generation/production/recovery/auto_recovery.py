"""Auto Recovery System for Generation Tasks.

Automatically recovers from failures:
- Retry with exponential backoff
- Platform switching
- Task resumption from checkpoint
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional
import json
from datetime import datetime

from .failure_detector import (
    FailureDetector,
    FailureRecord,
    FailureType,
    FailureSeverity
)


class RecoveryAction(str, Enum):
    """Recovery actions."""
    RETRY_IMMEDIATE = "retry_immediate"
    RETRY_DELAYED = "retry_delayed"
    RETRY_EXPONENTIAL = "retry_exponential"
    SWITCH_PLATFORM = "switch_platform"
    RESUME_CHECKPOINT = "resume_checkpoint"
    RESTART_WORKER = "restart_worker"
    ABORT = "abort"
    MANUAL_REVIEW = "manual_review"


class RecoveryStatus(str, Enum):
    """Recovery status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class RecoveryPlan:
    """Recovery plan for a failure."""
    plan_id: str = ""
    failure_id: str = ""
    generation_id: str = ""
    action: RecoveryAction = RecoveryAction.RETRY_IMMEDIATE
    target_platform: str = ""
    delay_seconds: float = 0.0
    max_attempts: int = 3
    current_attempt: int = 0
    status: RecoveryStatus = RecoveryStatus.PENDING
    created_at: str = ""
    updated_at: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "failure_id": self.failure_id,
            "generation_id": self.generation_id,
            "action": self.action.value,
            "target_platform": self.target_platform,
            "delay_seconds": self.delay_seconds,
            "max_attempts": self.max_attempts,
            "current_attempt": self.current_attempt,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "context": self.context
        }


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""
    plan_id: str = ""
    attempt_number: int = 0
    success: bool = False
    new_generation_id: str = ""
    new_platform: str = ""
    message: str = ""
    timestamp: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "attempt_number": self.attempt_number,
            "success": self.success,
            "new_generation_id": self.new_generation_id,
            "new_platform": self.new_platform,
            "message": self.message,
            "timestamp": self.timestamp
        }


class AutoRecovery:
    """Automatic recovery system for generation tasks.
    
    Features:
    - Automatic failure detection and recovery
    - Retry with exponential backoff
    - Platform switching (kling → veo → runway → comfyui)
    - Checkpoint-based resumption
    - Worker restart for crashes
    """
    
    # Platform fallback chain
    PLATFORM_FALLBACK = {
        "kling": ["veo", "runway", "comfyui"],
        "veo": ["kling", "runway", "comfyui"],
        "runway": ["kling", "veo", "comfyui"],
        "comfyui": ["kling", "veo", "runway"],
        "pika": ["kling", "veo", "runway"],
        "luma": ["kling", "veo", "runway"],
        "hailuo": ["kling", "veo", "runway"]
    }
    
    def __init__(
        self,
        failure_detector: Optional[FailureDetector] = None,
        max_retry_attempts: int = 3,
        initial_delay: float = 5.0,
        max_delay: float = 60.0
    ):
        self.failure_detector = failure_detector or FailureDetector()
        self.max_retry_attempts = max_retry_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self._plans: Dict[str, RecoveryPlan] = {}
        self._plan_id_counter = 0
        self._results: List[RecoveryResult] = []
    
    def create_recovery_plan(self, failure: FailureRecord) -> RecoveryPlan:
        """Create a recovery plan for a failure.
        
        Args:
            failure: Detected failure
            
        Returns:
            RecoveryPlan with recommended action
        """
        self._plan_id_counter += 1
        plan_id = f"plan_{self._plan_id_counter:04d}"
        
        # Determine action based on failure type
        action = self._determine_action(failure)
        
        # Determine target platform if switching
        target_platform = ""
        if action == RecoveryAction.SWITCH_PLATFORM:
            target_platform = self._get_fallback_platform(failure.platform)
        
        # Determine delay
        delay = self._calculate_delay(action)
        
        plan = RecoveryPlan(
            plan_id=plan_id,
            failure_id=failure.failure_id,
            generation_id=failure.generation_id,
            action=action,
            target_platform=target_platform,
            delay_seconds=delay,
            max_attempts=self.max_retry_attempts,
            current_attempt=0,
            status=RecoveryStatus.PENDING,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            context=failure.context
        )
        
        self._plans[plan_id] = plan
        return plan
    
    def execute_recovery(self, plan_id: str) -> RecoveryResult:
        """Execute a recovery plan.
        
        Args:
            plan_id: ID of the recovery plan
            
        Returns:
            RecoveryResult with execution outcome
        """
        plan = self._plans.get(plan_id)
        if not plan:
            return RecoveryResult(
                plan_id=plan_id,
                success=False,
                message="Plan not found"
            )
        
        # Update plan status
        plan.status = RecoveryStatus.IN_PROGRESS
        plan.current_attempt += 1
        plan.updated_at = datetime.now().isoformat()
        
        # Simulate recovery execution
        result = self._execute_action(plan)
        
        # Update plan status based on result
        if result.success:
            plan.status = RecoveryStatus.SUCCESS
        elif plan.current_attempt >= plan.max_attempts:
            plan.status = RecoveryStatus.FAILED
        else:
            plan.status = RecoveryStatus.PENDING
        
        plan.updated_at = datetime.now().isoformat()
        self._results.append(result)
        
        return result
    
    def auto_recover(
        self,
        error: Exception,
        generation_id: str,
        platform: str,
        context: Optional[Dict[str, Any]] = None
    ) -> RecoveryResult:
        """Automatically detect failure and recover.
        
        Args:
            error: Exception that occurred
            generation_id: ID of the generation task
            platform: Platform where failure occurred
            context: Additional context
            
        Returns:
            RecoveryResult from automatic recovery
        """
        # Detect failure
        failure = self.failure_detector.detect(
            error,
            generation_id,
            platform,
            context
        )
        
        # Create recovery plan
        plan = self.create_recovery_plan(failure)
        
        # Execute recovery
        result = self.execute_recovery(plan.plan_id)
        
        return result
    
    def get_plan(self, plan_id: str) -> Optional[RecoveryPlan]:
        """Get recovery plan by ID."""
        return self._plans.get(plan_id)
    
    def get_pending_plans(self) -> List[RecoveryPlan]:
        """Get all pending recovery plans."""
        return [p for p in self._plans.values() if p.status == RecoveryStatus.PENDING]
    
    def get_results(self, limit: int = 10) -> List[RecoveryResult]:
        """Get recent recovery results."""
        return self._results[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get recovery statistics."""
        total_plans = len(self._plans)
        successful = len([p for p in self._plans.values() if p.status == RecoveryStatus.SUCCESS])
        failed = len([p for p in self._plans.values() if p.status == RecoveryStatus.FAILED])
        pending = len([p for p in self._plans.values() if p.status == RecoveryStatus.PENDING])
        
        return {
            "total_plans": total_plans,
            "successful": successful,
            "failed": failed,
            "pending": pending,
            "success_rate": successful / total_plans if total_plans > 0 else 0.0
        }
    
    def _determine_action(self, failure: FailureRecord) -> RecoveryAction:
        """Determine recovery action from failure."""
        action_map = {
            FailureType.API_TIMEOUT: RecoveryAction.RETRY_EXPONENTIAL,
            FailureType.API_ERROR: RecoveryAction.RETRY_DELAYED,
            FailureType.PLATFORM_UNAVAILABLE: RecoveryAction.SWITCH_PLATFORM,
            FailureType.RATE_LIMIT: RecoveryAction.RETRY_DELAYED,
            FailureType.AUTHENTICATION_ERROR: RecoveryAction.RETRY_IMMEDIATE,
            FailureType.NETWORK_ERROR: RecoveryAction.RETRY_DELAYED,
            FailureType.GENERATION_FAILED: RecoveryAction.SWITCH_PLATFORM,
            FailureType.DOWNLOAD_FAILED: RecoveryAction.RETRY_IMMEDIATE,
            FailureType.STORAGE_ERROR: RecoveryAction.RETRY_DELAYED,
            FailureType.WORKER_CRASH: RecoveryAction.RESTART_WORKER,
            FailureType.UNKNOWN: RecoveryAction.RETRY_DELAYED
        }
        
        # Check severity override
        if failure.severity == FailureSeverity.CRITICAL:
            return RecoveryAction.MANUAL_REVIEW
        elif failure.severity == FailureSeverity.HIGH and failure.failure_type != FailureType.PLATFORM_UNAVAILABLE:
            return RecoveryAction.SWITCH_PLATFORM
        
        return action_map.get(failure.failure_type, RecoveryAction.RETRY_DELAYED)
    
    def _get_fallback_platform(self, current_platform: str) -> str:
        """Get fallback platform."""
        fallbacks = self.PLATFORM_FALLBACK.get(current_platform, ["kling", "veo", "runway"])
        return fallbacks[0] if fallbacks else "kling"
    
    def _calculate_delay(self, action: RecoveryAction) -> float:
        """Calculate delay for retry."""
        delay_map = {
            RecoveryAction.RETRY_IMMEDIATE: 0.0,
            RecoveryAction.RETRY_DELAYED: self.initial_delay,
            RecoveryAction.RETRY_EXPONENTIAL: self.initial_delay,
            RecoveryAction.SWITCH_PLATFORM: 2.0,
            RecoveryAction.RESUME_CHECKPOINT: 5.0,
            RecoveryAction.RESTART_WORKER: 10.0
        }
        return delay_map.get(action, self.initial_delay)
    
    def _execute_action(self, plan: RecoveryPlan) -> RecoveryResult:
        """Execute recovery action (simulated).
        
        In production, this would:
        - Call the platform API
        - Switch to different platform
        - Resume from checkpoint
        - Restart worker
        """
        # Simulated execution
        success = plan.current_attempt <= plan.max_attempts // 2  # 50% success rate
        
        # Generate new generation ID for successful retries
        new_gen_id = ""
        if success:
            new_gen_id = f"{plan.generation_id}_retry_{plan.current_attempt}"
        
        result = RecoveryResult(
            plan_id=plan.plan_id,
            attempt_number=plan.current_attempt,
            success=success,
            new_generation_id=new_gen_id,
            new_platform=plan.target_platform if plan.action == RecoveryAction.SWITCH_PLATFORM else "",
            message=f"Recovery attempt {plan.current_attempt} via {plan.action.value}",
            timestamp=datetime.now().isoformat()
        )
        
        return result
    
    def get_action_description(self, action: RecoveryAction) -> str:
        """Get description of recovery action."""
        descriptions = {
            RecoveryAction.RETRY_IMMEDIATE: "Retry immediately without delay",
            RecoveryAction.RETRY_DELAYED: "Retry after a short delay",
            RecoveryAction.RETRY_EXPONENTIAL: "Retry with exponential backoff",
            RecoveryAction.SWITCH_PLATFORM: "Switch to alternative platform",
            RecoveryAction.RESUME_CHECKPOINT: "Resume from saved checkpoint",
            RecoveryAction.RESTART_WORKER: "Restart crashed worker",
            RecoveryAction.ABORT: "Abort task, no recovery",
            RecoveryAction.MANUAL_REVIEW: "Requires manual review and intervention"
        }
        return descriptions.get(action, "Unknown action")


def demo_auto_recovery():
    """Demo auto recovery functionality."""
    recovery = AutoRecovery()
    
    # Simulate failure and recovery
    timeout_error = TimeoutError("API timeout after 120s")
    result1 = recovery.auto_recover(timeout_error, "gen_001", "kling")
    
    print("=== Recovery 1: Timeout ===")
    print(f"Success: {result1.success}")
    print(f"Action: RecoveryAction.RETRY_EXPONENTIAL")
    print(f"New Generation: {result1.new_generation_id}")
    
    # Simulate platform unavailable
    failure2 = recovery.failure_detector.detect_platform_unavailable("kling")
    plan2 = recovery.create_recovery_plan(failure2)
    result2 = recovery.execute_recovery(plan2.plan_id)
    
    print("\n=== Recovery 2: Platform Unavailable ===")
    print(f"Success: {result2.success}")
    print(f"Target Platform: {plan2.target_platform}")
    print(f"New Platform: {result2.new_platform}")
    
    # Get stats
    stats = recovery.get_stats()
    print("\n=== Recovery Stats ===")
    print(f"Total Plans: {stats['total_plans']}")
    print(f"Success Rate: {stats['success_rate']:.1%}")


if __name__ == "__main__":
    demo_auto_recovery()