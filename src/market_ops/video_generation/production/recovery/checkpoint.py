"""Checkpoint System for Generation Tasks.

Saves task progress for recovery after failures.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional
import json
from datetime import datetime, timedelta
from pathlib import Path


class CheckpointStatus(str, Enum):
    """Checkpoint status."""
    ACTIVE = "active"  # Task in progress
    PAUSED = "paused"  # Task paused, checkpoint saved
    RESUMED = "resumed"  # Task resumed from checkpoint
    COMPLETED = "completed"  # Task completed, checkpoint archived
    FAILED = "failed"  # Task failed, checkpoint for recovery


@dataclass
class Checkpoint:
    """Checkpoint for a generation task."""
    checkpoint_id: str = ""
    generation_id: str = ""
    task_type: str = "video_generation"
    status: CheckpointStatus = CheckpointStatus.ACTIVE
    platform: str = ""
    worker_id: str = ""
    
    # Task progress
    progress_percent: float = 0.0
    current_step: str = ""
    total_steps: int = 5
    
    # Task data
    blueprint_id: str = ""
    prompt_data: Dict[str, Any] = field(default_factory=dict)
    generation_params: Dict[str, Any] = field(default_factory=dict)
    
    # Result data (if available)
    video_url: str = ""
    video_path: str = ""
    
    # Metadata
    created_at: str = ""
    updated_at: str = ""
    expires_at: str = ""  # Checkpoint expiration time
    
    # Recovery info
    retry_count: int = 0
    last_error: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "generation_id": self.generation_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "platform": self.platform,
            "worker_id": self.worker_id,
            "progress_percent": self.progress_percent,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "blueprint_id": self.blueprint_id,
            "prompt_data": self.prompt_data,
            "generation_params": self.generation_params,
            "video_url": self.video_url,
            "video_path": self.video_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "retry_count": self.retry_count,
            "last_error": self.last_error
        }
    
    def is_valid(self) -> bool:
        """Check if checkpoint is still valid."""
        if self.expires_at:
            expiry = datetime.fromisoformat(self.expires_at)
            return datetime.now() < expiry
        return True


class CheckpointManager:
    """Checkpoint manager for generation tasks.
    
    Features:
    - Save task progress at key points
    - Resume from checkpoint after failures
    - Checkpoint expiration and cleanup
    - Checkpoint recovery for different scenarios
    """
    
    # Standard checkpoint steps for video generation
    GENERATION_STEPS = [
        "blueprint_parsed",
        "prompt_generated",
        "api_call_started",
        "video_generating",
        "video_downloading",
        "qa_checking",
        "completed"
    ]
    
    def __init__(
        self,
        storage_dir: Optional[str] = None,
        checkpoint_ttl_hours: int = 24
    ):
        self.storage_dir = storage_dir or "data/checkpoints"
        self.checkpoint_ttl_hours = checkpoint_ttl_hours
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._checkpoint_id_counter = 0
    
    def create_checkpoint(
        self,
        generation_id: str,
        task_type: str = "video_generation",
        platform: str = "",
        worker_id: str = "",
        blueprint_id: str = "",
        prompt_data: Optional[Dict[str, Any]] = None,
        generation_params: Optional[Dict[str, Any]] = None
    ) -> Checkpoint:
        """Create a new checkpoint.
        
        Args:
            generation_id: ID of the generation task
            task_type: Type of task
            platform: Platform being used
            worker_id: Worker processing the task
            blueprint_id: Blueprint ID
            prompt_data: Prompt data
            generation_params: Generation parameters
            
        Returns:
            New Checkpoint
        """
        self._checkpoint_id_counter += 1
        checkpoint_id = f"ckpt_{self._checkpoint_id_counter:04d}"
        
        now = datetime.now()
        expires_at = datetime.now() + timedelta(hours=self.checkpoint_ttl_hours)
        
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            generation_id=generation_id,
            task_type=task_type,
            status=CheckpointStatus.ACTIVE,
            platform=platform,
            worker_id=worker_id,
            blueprint_id=blueprint_id,
            prompt_data=prompt_data or {},
            generation_params=generation_params or {},
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            expires_at=expires_at.isoformat()
        )
        
        self._checkpoints[checkpoint_id] = checkpoint
        self._save_checkpoint(checkpoint)
        
        return checkpoint
    
    def update_checkpoint(
        self,
        checkpoint_id: str,
        current_step: str = "",
        progress_percent: Optional[float] = None,
        video_url: str = "",
        video_path: str = "",
        status: Optional[CheckpointStatus] = None
    ) -> Optional[Checkpoint]:
        """Update checkpoint progress.
        
        Args:
            checkpoint_id: ID of checkpoint to update
            current_step: Current processing step
            progress_percent: Progress percentage (optional, auto-calculated)
            video_url: Video URL if generated
            video_path: Local video path if downloaded
            status: New status
            
        Returns:
            Updated Checkpoint
        """
        checkpoint = self._checkpoints.get(checkpoint_id)
        if not checkpoint:
            return None
        
        # Update current step
        if current_step:
            checkpoint.current_step = current_step
            
            # Auto-calculate progress if not provided
            if progress_percent is None:
                step_index = self.GENERATION_STEPS.index(current_step) if current_step in self.GENERATION_STEPS else 0
                checkpoint.progress_percent = (step_index / len(self.GENERATION_STEPS)) * 100
            else:
                checkpoint.progress_percent = progress_percent
        
        # Update video data
        if video_url:
            checkpoint.video_url = video_url
        if video_path:
            checkpoint.video_path = video_path
        
        # Update status
        if status:
            checkpoint.status = status
        
        checkpoint.updated_at = datetime.now().isoformat()
        self._save_checkpoint(checkpoint)
        
        return checkpoint
    
    def pause_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Pause a checkpoint."""
        return self.update_checkpoint(checkpoint_id, status=CheckpointStatus.PAUSED)
    
    def resume_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Resume a paused checkpoint."""
        checkpoint = self._checkpoints.get(checkpoint_id)
        if checkpoint and checkpoint.status == CheckpointStatus.PAUSED:
            checkpoint.status = CheckpointStatus.RESUMED
            checkpoint.retry_count += 1
            checkpoint.updated_at = datetime.now().isoformat()
            self._save_checkpoint(checkpoint)
            return checkpoint
        return None
    
    def complete_checkpoint(
        self,
        checkpoint_id: str,
        video_path: str = ""
    ) -> Optional[Checkpoint]:
        """Mark checkpoint as completed."""
        checkpoint = self._checkpoints.get(checkpoint_id)
        if checkpoint:
            checkpoint.status = CheckpointStatus.COMPLETED
            checkpoint.progress_percent = 100.0
            checkpoint.current_step = "completed"
            if video_path:
                checkpoint.video_path = video_path
            checkpoint.updated_at = datetime.now().isoformat()
            self._save_checkpoint(checkpoint)
            return checkpoint
        return None
    
    def fail_checkpoint(
        self,
        checkpoint_id: str,
        error_message: str = ""
    ) -> Optional[Checkpoint]:
        """Mark checkpoint as failed."""
        checkpoint = self._checkpoints.get(checkpoint_id)
        if checkpoint:
            checkpoint.status = CheckpointStatus.FAILED
            checkpoint.last_error = error_message
            checkpoint.updated_at = datetime.now().isoformat()
            self._save_checkpoint(checkpoint)
            return checkpoint
        return None
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get checkpoint by ID."""
        return self._checkpoints.get(checkpoint_id)
    
    def get_checkpoint_by_generation(self, generation_id: str) -> Optional[Checkpoint]:
        """Get checkpoint by generation ID."""
        for checkpoint in self._checkpoints.values():
            if checkpoint.generation_id == generation_id:
                return checkpoint
        return None
    
    def get_active_checkpoints(self) -> List[Checkpoint]:
        """Get all active checkpoints."""
        return [c for c in self._checkpoints.values() if c.status == CheckpointStatus.ACTIVE]
    
    def get_paused_checkpoints(self) -> List[Checkpoint]:
        """Get all paused checkpoints."""
        return [c for c in self._checkpoints.values() if c.status == CheckpointStatus.PAUSED]
    
    def get_failed_checkpoints(self) -> List[Checkpoint]:
        """Get all failed checkpoints."""
        return [c for c in self._checkpoints.values() if c.status == CheckpointStatus.FAILED]
    
    def cleanup_expired(self) -> List[str]:
        """Remove expired checkpoints.
        
        Returns:
            List of removed checkpoint IDs
        """
        removed = []
        for checkpoint_id, checkpoint in list(self._checkpoints.items()):
            if not checkpoint.is_valid():
                removed.append(checkpoint_id)
                del self._checkpoints[checkpoint_id]
        
        return removed
    
    def get_recovery_data(self, checkpoint_id: str) -> Dict[str, Any]:
        """Get data needed to resume from checkpoint.
        
        Returns:
            Recovery data including platform, params, progress
        """
        checkpoint = self._checkpoints.get(checkpoint_id)
        if not checkpoint:
            return {}
        
        # Determine next step based on current progress
        current_step_index = self.GENERATION_STEPS.index(checkpoint.current_step) if checkpoint.current_step in self.GENERATION_STEPS else 0
        next_step = self.GENERATION_STEPS[current_step_index + 1] if current_step_index + 1 < len(self.GENERATION_STEPS) else "completed"
        
        return {
            "checkpoint_id": checkpoint_id,
            "generation_id": checkpoint.generation_id,
            "platform": checkpoint.platform,
            "worker_id": checkpoint.worker_id,
            "blueprint_id": checkpoint.blueprint_id,
            "prompt_data": checkpoint.prompt_data,
            "generation_params": checkpoint.generation_params,
            "current_step": checkpoint.current_step,
            "next_step": next_step,
            "progress_percent": checkpoint.progress_percent,
            "retry_count": checkpoint.retry_count,
            "video_url": checkpoint.video_url  # Resume download if already generated
        }
    
    def _save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint to storage."""
        # In production, save to disk or database
        # For demo, just keep in memory
        pass
    
    def get_status_description(self, status: CheckpointStatus) -> str:
        """Get description of checkpoint status."""
        descriptions = {
            CheckpointStatus.ACTIVE: "Task is in progress",
            CheckpointStatus.PAUSED: "Task paused, checkpoint saved",
            CheckpointStatus.RESUMED: "Task resumed from checkpoint",
            CheckpointStatus.COMPLETED: "Task completed successfully",
            CheckpointStatus.FAILED: "Task failed, ready for recovery"
        }
        return descriptions.get(status, "Unknown status")


def demo_checkpoint_manager():
    """Demo checkpoint manager functionality."""
    manager = CheckpointManager()
    
    # Create checkpoint
    checkpoint1 = manager.create_checkpoint(
        generation_id="gen_001",
        platform="kling",
        worker_id="worker_01",
        blueprint_id="bp_001",
        prompt_data={"scene": "witch treasure"}
    )
    
    print("=== Created Checkpoint ===")
    print(f"ID: {checkpoint1.checkpoint_id}")
    print(f"Generation: {checkpoint1.generation_id}")
    print(f"Platform: {checkpoint1.platform}")
    print(f"Status: {checkpoint1.status.value}")
    
    # Update progress
    checkpoint1 = manager.update_checkpoint(checkpoint1.checkpoint_id, "api_call_started")
    print(f"\n=== Updated Progress ===")
    print(f"Current Step: {checkpoint1.current_step}")
    print(f"Progress: {checkpoint1.progress_percent:.1f}%")
    
    # Simulate failure
    checkpoint1 = manager.fail_checkpoint(checkpoint1.checkpoint_id, "API timeout")
    print(f"\n=== Failed Checkpoint ===")
    print(f"Status: {checkpoint1.status.value}")
    print(f"Error: {checkpoint1.last_error}")
    
    # Get recovery data
    recovery_data = manager.get_recovery_data(checkpoint1.checkpoint_id)
    print(f"\n=== Recovery Data ===")
    print(f"Next Step: {recovery_data['next_step']}")
    print(f"Retry Count: {recovery_data['retry_count']}")
    
    # Resume checkpoint
    checkpoint1 = manager.resume_checkpoint(checkpoint1.checkpoint_id)
    print(f"\n=== Resumed Checkpoint ===")
    print(f"Status: {checkpoint1.status.value}")
    print(f"Retry Count: {checkpoint1.retry_count}")


if __name__ == "__main__":
    demo_checkpoint_manager()