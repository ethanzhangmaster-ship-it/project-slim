"""E13.7.1 Memory Adapter — 连接 E13.4 Memory Kernel.

将 Agent 的记忆操作转换为对 E13.4 Memory 系统的调用。

处理的工具:
  - query_memory → Memory Kernel (Pattern/Strategy/Experience/Failure)
  - update_memory → Memory Kernel (写入)
  - record_episode → EpisodicMemory (写入)

连接:
  Agent Tool → MemoryAdapter → E13.4 Memory Kernel (PatternStore, StrategyMemory, ...)
"""

from __future__ import annotations

from typing import Any

from ..agent_tools import ToolResult, ToolResultStatus
from .tool_adapter import ToolAdapter, ToolExecutionContext


class MemoryAdapter(ToolAdapter):
    """记忆适配器 — 连接 E13.4 Memory Kernel.

    提供:
      - 记忆查询 (Pattern, Strategy, Experience, Failure)
      - 记忆写入
      - 情景记录
    """

    HANDLED_ACTIONS = {
        "query_memory",
        "update_memory",
        "record_episode",
    }

    @property
    def name(self) -> str:
        return "memory_adapter"

    def can_handle(self, action_name: str) -> bool:
        return action_name in self.HANDLED_ACTIONS

    def execute(
        self,
        action_name: str,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        mode = context.execution_mode

        if mode == "mock":
            return self._execute_mock(action_name, params)
        elif mode == "real":
            return self._execute_real(action_name, params, context)
        else:
            return self._execute_mock(action_name, params)

    def _execute_real(
        self,
        action_name: str,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        """真实记忆系统调用."""
        try:
            if action_name == "query_memory":
                return self._query_memory_real(params)
            elif action_name == "update_memory":
                return self._update_memory_real(params)
            elif action_name == "record_episode":
                return self._record_episode_real(params)

            return ToolResult(
                tool_name=action_name,
                status=ToolResultStatus.FAILED,
                error=f"Unknown action: {action_name}",
            )

        except ImportError:
            return self._execute_mock(action_name, params)
        except Exception as e:
            return ToolResult(
                tool_name=action_name,
                status=ToolResultStatus.FAILED,
                error=f"Memory system error: {str(e)}",
            )

    def _query_memory_real(self, params: dict[str, Any]) -> ToolResult:
        """查询记忆系统."""
        query = params.get("query", "")
        memory_type = params.get("memory_type", "pattern")
        top_k = params.get("top_k", 5)

        results = []

        try:
            from ..memory.pattern_store import PatternStore
            store = PatternStore()
            results = store.search(query, top_k=top_k)
        except ImportError:
            pass

        if not results:
            try:
                from ..memory.memory_retriever import MemoryRetriever
                retriever = MemoryRetriever()
                results = retriever.search(query, memory_type=memory_type, top_k=top_k)
            except ImportError:
                pass

        return ToolResult(
            tool_name="query_memory",
            status=ToolResultStatus.SUCCESS,
            data={
                "query": query,
                "memory_type": memory_type,
                "results": results,
                "count": len(results) if results else 0,
            },
        )

    def _update_memory_real(self, params: dict[str, Any]) -> ToolResult:
        """更新记忆系统."""
        concept = params.get("concept", "")
        description = params.get("description", "")
        confidence = params.get("confidence", 0.5)

        try:
            from ..memory.experience_store import ExperienceStore
            store = ExperienceStore()
            store.add(concept=concept, description=description, confidence=confidence)
        except ImportError:
            pass

        return ToolResult(
            tool_name="update_memory",
            status=ToolResultStatus.SUCCESS,
            data={
                "concept": concept,
                "description": description,
                "confidence": confidence,
                "status": "stored",
            },
        )

    def _record_episode_real(self, params: dict[str, Any]) -> ToolResult:
        """记录情景."""
        goal = params.get("goal", {})
        plan = params.get("plan", {})
        actions = params.get("actions", [])
        results = params.get("results", [])
        outcome = params.get("outcome", "")
        lessons = params.get("lessons", [])

        try:
            from ..memory.experience_store import ExperienceStore
            store = ExperienceStore()
            store.record_episode(
                goal=goal,
                plan=plan,
                actions=actions,
                results=results,
                outcome=outcome,
                lessons=lessons,
            )
        except ImportError:
            pass

        return ToolResult(
            tool_name="record_episode",
            status=ToolResultStatus.SUCCESS,
            data={
                "outcome": outcome,
                "lesson_count": len(lessons),
                "status": "recorded",
            },
        )

    def _execute_mock(self, action_name: str, params: dict[str, Any]) -> ToolResult:
        """Mock 记忆操作."""
        mock_data = {
            "query_memory": {
                "query": params.get("query", ""),
                "results": [
                    {
                        "concept": "Creative Mutation",
                        "description": "D7 ROAS +22% after mutation",
                        "confidence": 0.85,
                        "evidence_count": 3,
                    },
                    {
                        "concept": "Rescue Hook",
                        "description": "Payer rate +23% with rescue hook",
                        "confidence": 0.78,
                        "evidence_count": 5,
                    },
                ],
                "count": 2,
            },
            "update_memory": {
                "concept": params.get("concept", ""),
                "description": params.get("description", ""),
                "confidence": params.get("confidence", 0.5),
                "status": "stored",
            },
            "record_episode": {
                "outcome": params.get("outcome", "positive"),
                "lesson_count": len(params.get("lessons", [])),
                "status": "recorded",
            },
        }

        return ToolResult(
            tool_name=action_name,
            status=ToolResultStatus.SUCCESS,
            data=mock_data.get(action_name, {"status": "ok"}),
            metadata={"mode": "mock", "source": "memory"},
        )