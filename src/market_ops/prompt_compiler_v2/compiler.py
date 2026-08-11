from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.prompt_compiler_v2.schemas import CompiledPrompt, CreativeSpec
from market_ops.prompt_compiler_v2.identity_lock import identity_ref_constraint, SIZE_CONSTRAINT, validate_identity, identity_id_for_project


def _caf_feature_bias(project: str = "P04") -> str:
    """Inject CAF feature bias + pattern-mined recipe into the prompt."""
    parts = []
    # 1) Pattern-mined recipe (from historical winners, highest priority)
    try:
        from market_ops.pattern_mining.recipe_loader import load_recipe, recipe_to_prompt_section
        recipe = load_recipe(project)
        parts.append(recipe_to_prompt_section(recipe))
    except Exception:
        pass
    # 2) CAF feature bias (dynamic feature weights)
    try:
        from market_ops.caf.feature_bias import build_feature_boost_header, features_for_prompt
        features = features_for_prompt()
        if features:
            parts.append(build_feature_boost_header(features))
    except Exception:
        pass
    return ("\n\n" + "\n\n".join(parts) + "\n") if parts else ""


def compile_lovart_prompt(spec: CreativeSpec) -> tuple[str, str]:
    """Compile CreativeSpec -> (lovart_prompt, negative_prompt).

    Hard requirement: prompt MUST include at least:
      Hook / Reward / Mechanic / Identity / Camera / Composition / Lighting / Emotion / CTA / Style
    Identity: MUST be 'witch_v1', never expanded into free-text character description.
    """
    # ---------- Identity Lock enforcement ----------
    validate_identity(spec.identity)

    required = {
        "hook": spec.hook,
        "reward": spec.reward,
        "mechanic": spec.mechanic,
        "identity": spec.identity,
        "camera": spec.camera,
        "composition": spec.composition,
        "lighting": spec.lighting,
        "emotion": spec.emotion,
        "cta": spec.cta,
        "style": spec.style,
    }
    missing = [k for k, v in required.items() if not str(v or "").strip()]
    if missing:
        raise ValueError(f"CreativeSpec missing required fields: {', '.join(missing)} (creative_id={spec.creative_id})")

    # ---------- Build prompt ----------
    identity_id = identity_id_for_project(spec.identity or "witch_v1")
    ident_constraint = identity_ref_constraint(identity_id)
    
    prompt_lines = [
        "You are generating a production-grade Meta/Facebook mobile game ad image (static).",
        SIZE_CONSTRAINT,
        "Follow the Creative Spec strictly. The output must look like a real high-conversion ad creative.",
        "",
        # Identity constraint — project-specific, loaded from identity_lock
        ident_constraint,
        "",
        # ---------- CAF feature bias (generated from character_schema.json) ----------
        _caf_feature_bias(spec.identity or "P04"),
        f"[HOOK] {spec.hook}",
        f"[REWARD] {spec.reward}",
        f"[MECHANIC] {spec.mechanic}",
        f"[SCENE] {spec.scene}",
        f"[CAMERA] {spec.camera}",
        f"[COMPOSITION WEIGHTS] {spec.composition}",
        f"[LIGHTING] {spec.lighting}",
        f"[EMOTION] {spec.emotion}",
        f"[CTA] {spec.cta}",
        f"[STYLE] {spec.style}",
        "",
        "Constraints:",
        "- Mobile ad creative, crisp and readable UI.",
        "- Strong visual hierarchy: hook first, then mechanic, then reward, then CTA.",
        "- If any text is present, it must be clear and readable (not gibberish).",
        "- No watermark, no logos, no copyrighted brand marks.",
        "- High resolution, no blur, no artifacts.",
    ]
    lovart_prompt = "\n".join(prompt_lines).strip()

    negative_prompt = ", ".join([item.strip() for item in (spec.negative or []) if item.strip()])
    if negative_prompt:
        lovart_prompt += "\n\n[NEGATIVE]\n" + negative_prompt

    return lovart_prompt, negative_prompt


def compile_prompts(specs: list[CreativeSpec]) -> list[CompiledPrompt]:
    compiled: list[CompiledPrompt] = []
    for spec in specs:
        lovart_prompt, negative_prompt = compile_lovart_prompt(spec)
        compiled.append(
            CompiledPrompt(
                creative_id=spec.creative_id,
                lovart_prompt=lovart_prompt,
            )
        )
    return compiled


def write_compiled_prompts(path: Path, compiled: list[CompiledPrompt]) -> None:
    # V1 requirement: keep it human-checkable (plain array, minimal fields)
    payload = [item.to_dict() for item in compiled]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_compiled_prompts(path: Path) -> list[CompiledPrompt]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    result: list[CompiledPrompt] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        result.append(
            CompiledPrompt(
                creative_id=str(item.get("creative_id") or ""),
                lovart_prompt=str(item.get("lovart_prompt") or ""),
            )
        )
    return result
