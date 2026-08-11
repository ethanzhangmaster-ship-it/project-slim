"""
E13.3.1 — Monetization Reality Engine
======================================

Upgrades the E13.2.8 offline analysis into a *continuous* fact-generation
layer. Four cooperating modules:

  * event_stream.py   — GameEventStream: incremental event consumer
                        (in-memory buffer + optional JSONL append log)
  * segment_engine.py — SegmentEngine: aggregates events across the full
                        dimension set incl. traffic_source / user_cohort
  * metric_store.py   — MetricStore: holds computed facts (memory + JSON file)
  * fact_builder.py   — FactBuilder: emits standard MonetizationFact
                        (daily grain + fine segment grain)

reality_engine.py ties them together and exposes a `detect()` seam that
reuses the E13.2.8 Opportunity Detector — the input data for E13.3.2.

No backend / database. Local file + memory only (Lean).
"""
