#!/usr/bin/env python3
"""Production Generation V1 — Generation Layer Validation

Scope (STRICT):
- Winner Feature -> Creative Spec Builder -> Prompt Compiler -> Lovart -> PNG export
- Human-checkable outputs only

Forbidden in V1:
- Any scoring / OCR / CLIP similarity / reject / auto regeneration
- Any Facebook upload / campaign creation
- Any learning loop / dataset building / weight update

Outputs:
output/
  winner_features.json
  creative_specs.json
  compiled_prompts.json
  generation_report.json
  images/<run_id>/001.png ...
  creative_metadata/001.json ...
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_winner_features(directives_path: Path) -> dict[str, str]:
    """Step 1 — Winner Feature

    Requirement: no inference, only read existing winner targets.
    Source: output/pipeline_directives.json
    """
    payload = _read_json(directives_path)
    directives = payload.get("directives") or {}

    def _get(key: str) -> str:
        item = directives.get(key) or {}
        if isinstance(item, dict):
            return str(item.get("target") or "").strip()
        return ""

    # The example schema includes reward/mechanic/emotion/cta, but the current
    # pipeline_directives.json may not have them. We keep the keys with empty
    # strings (still "read-only", no inference).
    return {
        "game": _get("game"),
        "layout": _get("layout"),
        "color_tone": _get("color_tone"),
        "reward": _get("reward"),
        "mechanic": _get("mechanic"),
        "emotion": _get("emotion"),
        "cta": _get("cta"),
    }


# ── CAF (Character-as-Feature) helper — Step 5.5 parallel stream ──

def _run_caf_analysis(out_dir: Path, metadata_dir: Path, has_success: bool) -> None:
    """CAF analysis: extract signals from metadata → update character_schema.json.

    This runs in parallel to the main pipeline. Failure here does NOT
    invalidate the generation run.
    """
    if not has_success:
        print("[CAF] No successful generations, skipping CAF analysis.")
        return
    try:
        from market_ops.caf.caf_extractor import extract_signals
        from market_ops.caf.caf_updater import update_character

        for meta_file in sorted(metadata_dir.glob("*.json")):
            try:
                signals_payload = extract_signals(metadata_path=str(meta_file))
            except Exception:
                continue

            signals = signals_payload.get("signals") or {}
            if not any(abs(float(v)) > 0.001 for v in signals.values()):
                continue  # no meaningful signal (no metrics provided)

            try:
                updated = update_character(signals=signals)
            except Exception as exc:
                print(f"[CAF] update_character failed for {meta_file.name}: {exc}")
                continue

            print(
                f"[CAF] Updated character_schema.json → v{updated.get('version')} "
                f"deltas={updated.get('update_history', [{}])[-1].get('deltas', {})}"
            )
            break  # batch update: run once for the whole generation set

        caf_report_path = out_dir / "caf_report.json"
        caf_report_path.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        schema_path = Path(__file__).parent.parent / "src/market_ops/caf/character_schema.json"
        schema = _json.loads(schema_path.read_text(encoding="utf-8")) if schema_path.exists() else {}
        caf_report_path.write_text(
            _json.dumps({
                "completed": True,
                "character_id": schema.get("character_id", "witch_v1"),
                "version": schema.get("version", 1),
                "features": schema.get("features", {}),
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[CAF] caf_report.json written to {caf_report_path}")
    except Exception as exc:
        print(f"[CAF] Analysis skipped: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Production Generation V1 (Validation Only)")
    parser.add_argument("--project", default="P04 Witch")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _load_env()

    out_dir = ROOT / "output"
    directives_path = out_dir / "pipeline_directives.json"
    if not directives_path.exists():
        raise SystemExit("Missing output/pipeline_directives.json")

    winner_features = _extract_winner_features(directives_path)
    _write_json(out_dir / "winner_features.json", winner_features)

    # Step 2 — Creative Spec Builder
    from market_ops.prompt_compiler_v2.spec_builder import build_creative_specs, load_winner_features, write_creative_specs

    # Reuse the same directive reader; still no inference.
    wf_raw = load_winner_features(directives_path)
    specs = build_creative_specs(project=args.project, count=args.count, winner_features=wf_raw)
    _write_json(out_dir / "creative_specs.json", [{k: v for k, v in s.to_dict().items() if k not in {"negative", "model"}} for s in specs])

    # Step 3 — Prompt Compiler
    from market_ops.prompt_compiler_v2.compiler import compile_prompts, write_compiled_prompts

    compiled = compile_prompts(specs)
    write_compiled_prompts(out_dir / "compiled_prompts.json", compiled)

    if args.dry_run:
        _write_json(
            out_dir / "generation_report.json",
            {
                "run_id": "",
                "generated": args.count,
                "success": 0,
                "failed": 0,
                "average_generation_time": 0.0,
                "dry_run": True,
                "generated_at": _now_utc_iso(),
            },
        )
        print("[OK] Dry-run: wrote winner_features.json, creative_specs.json, compiled_prompts.json")
        return 0

    # Step 4 — Lovart Generation (no scoring / no reject / no regen)
    from market_ops.clients.lovart import LovartClient, download_image

    run_id = datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")
    images_dir = out_dir / "images" / run_id
    images_dir.mkdir(parents=True, exist_ok=True)

    metadata_dir = out_dir / "creative_metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    lovart = LovartClient(mode=os.getenv("LOVART_MODE", "fast"))
    # Round-robin between two Lovart accounts for rate-limit resilience
    ak2 = os.getenv("LOVART_ACCESS_KEY_2", "").strip()
    sk2 = os.getenv("LOVART_SECRET_KEY_2", "").strip()
    has_account2 = bool(ak2 and sk2)
    env_models = [m.strip() for m in os.getenv("LOVART_MODELS", "").split(",") if m.strip()]
    model = env_models[0] if env_models else None

    times: list[float] = []
    success = 0
    failed = 0
    rotation_idx = 0

    for spec, item in zip(specs, compiled):
        t0 = time.time()
        identity_meta = {"identity": "witch_v1"}
        # Round-robin account rotation: odd-index requests use account 2
        if has_account2 and (rotation_idx % 2 == 1):
            lovart = LovartClient(access_key=ak2, secret_key=sk2, mode=os.getenv("LOVART_MODE", "fast"))
        else:
            lovart = LovartClient(mode=os.getenv("LOVART_MODE", "fast"))
        rotation_idx += 1
        try:
            result = lovart.generate_image(prompt=item.lovart_prompt, model=model)
            gen_time = time.time() - t0
            times.append(gen_time)

            if result.status != "done" or not result.image_urls:
                failed += 1
                _write_json(
                    metadata_dir / f"{spec.creative_id}.json",
                    {
                        "creative_id": spec.creative_id,
                        "template": spec.template,
                        "creative_spec": spec.to_dict(),
                        "lovart_prompt": item.lovart_prompt,
                        "job_id": result.thread_id,
                        "generation_time": round(gen_time, 2),
                        **identity_meta,
                    },
                )
                continue

            url = result.image_urls[0]
            image_path = images_dir / f"{spec.creative_id}.png"
            download_image(url, image_path)
            success += 1

            _write_json(
                metadata_dir / f"{spec.creative_id}.json",
                {
                    "creative_id": spec.creative_id,
                    "template": spec.template,
                    "creative_spec": spec.to_dict(),
                    "lovart_prompt": item.lovart_prompt,
                    "job_id": result.thread_id,
                    "generation_time": round(gen_time, 2),
                    **identity_meta,
                },
            )
        except Exception as exc:
            gen_time = time.time() - t0
            times.append(gen_time)
            failed += 1
            _write_json(
                metadata_dir / f"{spec.creative_id}.json",
                {
                    "creative_id": spec.creative_id,
                    "template": spec.template,
                    "creative_spec": spec.to_dict(),
                    "lovart_prompt": item.lovart_prompt,
                    "job_id": "",
                    "generation_time": round(gen_time, 2),
                    **identity_meta,
                },
            )

    avg_time = sum(times) / len(times) if times else 0.0

    # ── Step 5.5: CAF Analysis (parallel, does not alter main pipeline) ──
    _run_caf_analysis(out_dir, metadata_dir, success > 0)

    _write_json(
        out_dir / "generation_report.json",
        {
            "run_id": run_id,
            "generated": args.count,
            "success": success,
            "failed": failed,
            "average_generation_time": round(avg_time, 2),
            "generated_at": _now_utc_iso(),
        },
    )
    print(f"[OK] run_id={run_id} generated={args.count} success={success} failed={failed} avg_time={avg_time:.2f}s")
    print(f"[OK] images_dir={images_dir}")
    print(f"[OK] metadata_dir={metadata_dir}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

