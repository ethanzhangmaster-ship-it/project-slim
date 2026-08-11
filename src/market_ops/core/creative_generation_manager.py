"""Phase 2.1: Creative Generation Manager — unified entry point for batch generation.

Orchestrates the full production pipeline:
  1. Load Winner DNA → CreativeGenerationSpecs
  2. Phase 1.6.1 V2 Ad Readiness Scoring
  3. Build Lovart Prompts
  4. Submit to Lovart Queue
  5. Worker Pool executes generation
  6. AI Quality Gate scores results
  7. Output report with top creatives

Usage:
    manager = CreativeGenerationManager()
    result = manager.generate_batch(specs, variations_per_spec=5)
    print(result.report())
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..creative_blueprint_validator import CreativeGenerationSpec
from ..creative_prompt_builder import CreativePromptBuilder, LovartPrompt
from ..creative_generation_feasibility import GenerationReadinessScorerV2, FeasibilityReportV2
from ..ai_creative_quality_gate import AICreativeQualityGate, BatchQualityReport
from ..image_validator import ImageValidator
from ..observability.event_bus import EventBus
from ..observability.observability_store import ObservabilityStore
from ..observability.observers import WorkerObserver, LatencyObserver
from ..observability.registry import ObserverRegistry
from .generation_store import GenerationStore
from .lovart_queue import LovartQueue
from ..lovart_adapter import LovartAPIAdapter
from .lovart_worker import WorkerPool


@dataclass
class BatchResult:
    """Result of a batch generation run."""
    batch_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    total_specs: int = 0
    ready_specs: int = 0
    prompts_built: int = 0
    tasks_submitted: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    quality_pass: int = 0
    quality_review: int = 0
    quality_fail: int = 0
    avg_quality: float = 0.0
    total_cost: float = 0.0
    total_time: float = 0.0
    v2_report: Any = None
    quality_report: Any = None
    top_creatives: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def report(self) -> str:
        lines = []
        lines.append("=" * 65)
        lines.append("  PHASE 2.1: Creative Generation Report")
        lines.append("  Merge Witches — Lovart Production Adapter")
        lines.append("=" * 65)
        lines.append("")
        lines.append(f"  Batch ID:       {self.batch_id}")
        lines.append(f"  Duration:       {self.total_time:.1f}s")
        lines.append("")
        lines.append(f"  Specs:          {self.total_specs}")
        lines.append(f"  Ready (V2):     {self.ready_specs}")
        lines.append(f"  Prompts:        {self.prompts_built}")
        lines.append(f"  Tasks:          {self.tasks_submitted}")
        lines.append("")
        lines.append(f"  Succeeded:      {self.tasks_succeeded}")
        lines.append(f"  Failed:         {self.tasks_failed}")
        lines.append(f"  Success Rate:   {self.tasks_succeeded / max(self.tasks_submitted, 1) * 100:.0f}%")
        lines.append(f"  Total Cost:     ${self.total_cost:.2f}")
        lines.append("")
        lines.append(f"  Quality PASS:   {self.quality_pass}")
        lines.append(f"  Quality REVIEW: {self.quality_review}")
        lines.append(f"  Quality FAIL:   {self.quality_fail}")
        lines.append(f"  Avg Quality:    {self.avg_quality:.0f}/100")
        lines.append("")
        if self.top_creatives:
            lines.append("  Top Creatives:")
            for i, tc in enumerate(self.top_creatives[:5], 1):
                lines.append(f"    #{i} {tc.get('creative_id', '?')}: "
                             f"score={tc.get('quality_score', 0)}, "
                             f"path={tc.get('image_path', 'N/A')[:60]}")
        if self.errors:
            lines.append("")
            lines.append(f"  Errors ({len(self.errors)}):")
            for e in self.errors[:5]:
                lines.append(f"    - {e}")
        lines.append("")
        lines.append("=" * 65)
        return "\n".join(lines)


class CreativeGenerationManager:
    """Unified manager for the entire creative generation pipeline."""

    # Default paths
    DEFAULT_OUTPUT = Path("output/creative_analysis/generated_creatives")
    DEFAULT_DB = Path("output/creative_analysis/generations.db")
    DEFAULT_OBS_DB = Path("output/creative_analysis/observability.db")
    DEFAULT_SPECS = Path("output/creative_analysis/generation_specs.json")
    DEFAULT_RULES = Path("output/creative_analysis/creative_rules.json")

    def __init__(
        self,
        output_dir: Path | None = None,
        db_path: Path | None = None,
        specs_path: Path | None = None,
        rules_path: Path | None = None,
        num_workers: int = 3,
        timeout: int = 60,
        max_retries: int = 3,
        lovart_access_key: str | None = None,
        lovart_secret_key: str | None = None,
    ) -> None:
        self._output_dir = output_dir or self.DEFAULT_OUTPUT
        self._db_path = db_path or self.DEFAULT_DB
        self._specs_path = specs_path or self.DEFAULT_SPECS
        self._rules_path = rules_path or self.DEFAULT_RULES
        self._num_workers = num_workers
        self._timeout = timeout
        self._max_retries = max_retries

        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Infrastructure
        self._store = GenerationStore(db_path=self._db_path)
        self._queue = LovartQueue(store=self._store)
        self._adapter = LovartAPIAdapter(
            access_key=lovart_access_key,
            secret_key=lovart_secret_key,
            timeout=timeout,
        )
        self._validator = ImageValidator()
        self._prompt_builder = CreativePromptBuilder()
        self._quality_gate = AICreativeQualityGate()

        # Phase 2.2A Final: Observability layer (Event Bus + ObserverRegistry)
        self._obs_store = ObservabilityStore(db_path=self._output_dir.parent / "observability.db")
        self._event_bus = EventBus()

        # Declarative registry — add new observers here, nothing else changes
        self._registry = ObserverRegistry(self._event_bus)
        self._registry.register(
            WorkerObserver(store=self._obs_store),
            priority=100,
        ).register(
            LatencyObserver(core_store=self._store, obs_store=self._obs_store),
            priority=80,
        )
        self._registry.bootstrap()

        # Workers (created on demand)
        self._pool: WorkerPool | None = None

    @property
    def adapter_available(self) -> bool:
        return self._adapter.available

    # ── Main API ──

    def generate_batch(
        self,
        specs: list[CreativeGenerationSpec] | None = None,
        rules: list[dict[str, Any]] | None = None,
        variations_per_spec: int = 5,
        wait: bool = True,
        max_wait: float = 600,
    ) -> BatchResult:
        """Execute the full generation pipeline."""
        batch_id = f"gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        started_at = datetime.now(timezone.utc).isoformat()
        t0 = time.time()
        errors: list[str] = []

        if specs is None:
            specs, load_err = self._load_specs()
            errors.extend(load_err)

        if rules is None:
            rules, load_err = self._load_rules()
            errors.extend(load_err)

        if not specs:
            errors.append("No specs available")
            return BatchResult(
                batch_id=batch_id, errors=errors,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
            )

        scorer = GenerationReadinessScorerV2(rules=rules or [])
        v2_results = scorer.score_all(specs)
        v2_report = FeasibilityReportV2(
            total_specs=len(specs),
            passed_gate=sum(1 for r in v2_results if r.phase_2_gate),
            average_score=sum(r.total for r in v2_results) / len(v2_results),
            results=v2_results,
            phase_2_ready=all(r.phase_2_gate for r in v2_results),
        )

        gate_specs = [s for s, r in zip(specs, v2_results) if r.phase_2_gate]
        if not gate_specs:
            errors.append("No specs pass Phase 2 gate")
            return BatchResult(
                batch_id=batch_id, errors=errors,
                total_specs=len(specs), ready_specs=0,
                v2_report=v2_report,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
            )

        all_prompts = self._prompt_builder.build_variations_batch(
            gate_specs, variations_per_spec
        )

        tasks = []
        for p in all_prompts:
            tasks.append({
                "creative_id": p.prompt_id,
                "prompt": p.prompt_text,
                "negative_prompt": p.negative_prompt,
                "priority": "normal",
                "format": "1080x1080",
                "dna_source": p.source_blueprint,
            })

        task_ids = self._queue.submit_batch(tasks)

        self._pool = WorkerPool(
            queue=self._queue,
            adapter=self._adapter,
            store=self._store,
            output_dir=self._output_dir / batch_id,
            num_workers=self._num_workers,
            timeout=self._timeout,
            event_bus=self._event_bus,
        )
        self._pool.start()

        self._store.start_recovery_thread(interval=30, daemon=True)

        if wait:
            self._pool.wait_idle(poll_interval=2.0, max_wait=max_wait)
            self._pool.stop()

        stats = self._store.get_stats()
        succeeded = self._store.list_all(limit=200)
        succeeded = [t for t in succeeded if t["status"] == "SUCCESS"]

        from ..lovart_generator_adapter import GeneratedCreative
        mock_creatives = []
        for t in succeeded:
            prompt = LovartPrompt(
                prompt_id=t["creative_id"],
                prompt_text=t["prompt"],
                source_blueprint=t.get("dna_source", ""),
            )
            gc = GeneratedCreative(
                creative_id=t["creative_id"],
                prompt=prompt,
                image_path=t.get("image_path", ""),
                source_blueprint=t.get("dna_source", ""),
            )
            mock_creatives.append(gc)

        quality_results = self._quality_gate.evaluate_batch(mock_creatives, gate_specs)
        avg_quality = sum(r.total for r in quality_results) / max(len(quality_results), 1)

        for qr, t in zip(quality_results, succeeded):
            if qr.creative_id == t["creative_id"]:
                self._store.update_status(t["id"], t["status"], quality_score=qr.total)

        quality_report = BatchQualityReport(
            batch_id=batch_id,
            total=len(quality_results),
            passed=sum(1 for r in quality_results if r.status == "PASS"),
            review=sum(1 for r in quality_results if r.status == "REVIEW"),
            failed=sum(1 for r in quality_results if r.status == "FAIL"),
            average_score=avg_quality,
            results=quality_results,
        )

        sorted_results = sorted(quality_results, key=lambda r: r.total, reverse=True)
        top_creatives = []
        for r in sorted_results[:5]:
            matching = [t for t in succeeded if t["creative_id"] == r.creative_id]
            top_creatives.append({
                "creative_id": r.creative_id,
                "quality_score": r.total,
                "image_path": matching[0].get("image_path", "") if matching else "",
                "status": r.status,
            })

        total_time = time.time() - t0
        stats = self._store.get_stats()

        return BatchResult(
            batch_id=batch_id,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            total_specs=len(specs),
            ready_specs=len(gate_specs),
            prompts_built=len(all_prompts),
            tasks_submitted=len(task_ids),
            tasks_succeeded=stats["success_count"],
            tasks_failed=stats["failed_count"],
            quality_pass=quality_report.passed,
            quality_review=quality_report.review,
            quality_fail=quality_report.failed,
            avg_quality=avg_quality,
            total_cost=stats["total_cost"],
            total_time=total_time,
            v2_report=v2_report,
            quality_report=quality_report,
            top_creatives=top_creatives,
            errors=errors,
        )

    def get_stats(self) -> dict[str, Any]:
        return self._store.get_stats()

    def get_queue_status(self) -> dict[str, Any]:
        return self._queue.stats()

    def _load_specs(self) -> tuple[list[CreativeGenerationSpec], list[str]]:
        errors: list[str] = []
        try:
            with open(self._specs_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            specs = [CreativeGenerationSpec.from_dict(s) for s in data.get("specs", [])]
            return specs, errors
        except Exception as e:
            errors.append(f"Failed to load specs: {e}")
            return [], errors

    def _load_rules(self) -> tuple[list[dict[str, Any]], list[str]]:
        errors: list[str] = []
        try:
            with open(self._rules_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("rules", []), errors
        except Exception as e:
            errors.append(f"Failed to load rules: {e}")
            return [], errors