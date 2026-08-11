"""E12.6.2 — Resource Controller。

资源控制器模块，负责系统资源的智能分配。

模块:
  - models:               ResourceType, ResourceRequest, ResourceAllocation, ProductResourceState
  - resource_policy:      4 条资源策略规则
  - priority_allocator:   Softmax 优先级分配器
  - budget_optimizer:     动态预算优化器
  - resource_controller:  核心控制器
"""

from .models import (
    BudgetAdjustment,
    ProductResourceState,
    ResourceAllocation,
    ResourceRequest,
    ResourceType,
    calculate_priority_score,
    get_resource_label,
    softmax_allocate,
)
from .resource_policy import (
    DEFAULT_RESOURCE_POLICIES,
    ExplorationPolicy,
    FatigueRecoveryPolicy,
    LowPotentialPolicy,
    ResourcePolicy,
    WinnerScalingPolicy,
)
from .priority_allocator import PriorityAllocator
from .budget_optimizer import BudgetOptimizer
from .resource_controller import ResourceController

__all__ = [
    # Models
    "ResourceType",
    "ResourceRequest",
    "ResourceAllocation",
    "ProductResourceState",
    "BudgetAdjustment",
    "calculate_priority_score",
    "get_resource_label",
    "softmax_allocate",
    # Policies
    "ResourcePolicy",
    "WinnerScalingPolicy",
    "FatigueRecoveryPolicy",
    "LowPotentialPolicy",
    "ExplorationPolicy",
    "DEFAULT_RESOURCE_POLICIES",
    # Allocator
    "PriorityAllocator",
    # Optimizer
    "BudgetOptimizer",
    # Controller
    "ResourceController",
]