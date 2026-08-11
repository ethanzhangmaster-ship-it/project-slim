"""P04 Video Generation Test Run

基于 Video Creative Director + Video Generation Layer，
真实生成第一批 P04 Witch 买量视频。

10 个变体，每个包含：
- Flux 首帧图生成
- Wan2.1 I2V 视频生成
- 验证 + Metadata 保存

Usage:
    python test_generation_run.py
"""
from __future__ import annotations

import sys
import os
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from market_ops.creative_intelligence.video_director import (
    VideoDirector, WinnerDNA, GameInfo, AdGoal,
)
from market_ops.creative_intelligence.video_generation import GenerationPipeline
from market_ops.creative_intelligence.video_generation.models import GenerationResult, GenerationStatus
from market_ops.creative_intelligence.video_generation.comfyui_client import ComfyUIClient
from market_ops.creative_intelligence.video_generation.workflow_executor import WorkflowExecutor
from market_ops.creative_intelligence.video_generation.video_validator import VideoValidator


OUTPUT_DIR = "outputs/P04_Video_Test_Set_001"
COMFYUI_HOST = "192.168.124.13"
COMFYUI_PORT = 8188

GAME_INFO = GameInfo(
    game="Merge Witch",
    genre="merge puzzle",
    core_loop="merge items upgrade castle",
    target="US female 25-45",
    art_style="fantasy 2D",
    key_characters=["witch", "dragon"],
    key_items=["magic crystal", "merge orb", "chest"],
)

AD_GOAL = AdGoal(
    goal="install",
    duration=15,
    platform="facebook",
    format="9:16",
)


VARIANTS: list[dict] = [
    {
        "id": "video_001",
        "angle": "dragon_attack",
        "dna": WinnerDNA(
            theme="dragon attacks castle, witch defends with magic shield",
            aspect_ratio="9X16",
            lighting="dramatic warm",
            contrast=0.2,
            saturation=0.5,
            hook="dragon attack",
            winning_elements=["dragon fire", "castle siege", "magic shield"],
            roas=44.68,
            source_video_id="v2601523",
            content_type="juqing",
            duration="15s",
        ),
        "seed": 1001,
    },
    {
        "id": "video_002",
        "angle": "witch_transformation",
        "dna": WinnerDNA(
            theme="weak witch to legendary witch magical transformation",
            aspect_ratio="9X16",
            lighting="warm golden",
            contrast=0.15,
            saturation=0.45,
            hook="transformation",
            winning_elements=["character evolution", "glowing particles", "legendary skin"],
            roas=44.68,
            source_video_id="v2601523",
            content_type="juesezhanshi",
            duration="15s",
        ),
        "seed": 1002,
    },
    {
        "id": "video_003",
        "angle": "merge_gameplay",
        "dna": WinnerDNA(
            theme="magic stones merge together with bright fusion glow, castle upgrade",
            aspect_ratio="9X16",
            lighting="bright magical",
            contrast=0.1,
            saturation=0.5,
            hook="merge",
            winning_elements=["merge action", "fusion glow", "building upgrade"],
            roas=18.36,
            source_video_id="v2601163",
            content_type="wanfashipin",
            duration="15s",
        ),
        "seed": 1003,
    },
    {
        "id": "video_004",
        "angle": "before_after_upgrade",
        "dna": WinnerDNA(
            theme="broken castle transforms into beautiful kingdom through merge magic",
            aspect_ratio="9X16",
            lighting="warm cinematic",
            contrast=0.15,
            saturation=0.45,
            hook="upgrade",
            winning_elements=["before after", "castle rebuild", "magical transformation"],
            roas=18.36,
            source_video_id="v2601163",
            content_type="wanfashipin",
            duration="15s",
        ),
        "seed": 1004,
    },
    {
        "id": "video_005",
        "angle": "reward_fantasy",
        "dna": WinnerDNA(
            theme="open treasure chest, coins explosion, new legendary character unlock",
            aspect_ratio="9X16",
            lighting="golden radiant",
            contrast=0.2,
            saturation=0.55,
            hook="reward",
            winning_elements=["treasure chest", "coin burst", "character unlock"],
            roas=44.68,
            source_video_id="v2601523",
            content_type="juesezhanshi",
            duration="15s",
        ),
        "seed": 1005,
    },
    {
        "id": "video_006",
        "angle": "fast_push_transform",
        "dna": WinnerDNA(
            theme="fast push in on witch, magical transformation with glowing particles",
            aspect_ratio="9X16",
            lighting="warm",
            contrast=0.15,
            saturation=0.45,
            hook="fast transformation",
            winning_elements=["fast push in", "transformation", "particles"],
            roas=44.68,
            source_video_id="v2601523",
            content_type="juesezhanshi",
            duration="15s",
        ),
        "seed": 1006,
    },
    {
        "id": "video_007",
        "angle": "orbit_merge",
        "dna": WinnerDNA(
            theme="orbit shot around witch merging magic crystals, bright fusion glow",
            aspect_ratio="9X16",
            lighting="magical",
            contrast=0.15,
            saturation=0.5,
            hook="merge",
            winning_elements=["orbit shot", "merge", "fusion glow"],
            roas=18.36,
            source_video_id="v2601163",
            content_type="wanfashipin",
            duration="15s",
        ),
        "seed": 1007,
    },
    {
        "id": "video_008",
        "angle": "tracking_upgrade",
        "dna": WinnerDNA(
            theme="tracking shot following witch upgrading legendary armor with golden light",
            aspect_ratio="9X16",
            lighting="golden",
            contrast=0.15,
            saturation=0.45,
            hook="upgrade",
            winning_elements=["tracking", "armor upgrade", "golden light"],
            roas=18.36,
            source_video_id="v2601163",
            content_type="juesezhanshi",
            duration="15s",
        ),
        "seed": 1008,
    },
    {
        "id": "video_009",
        "angle": "golden_explosion",
        "dna": WinnerDNA(
            theme="witch casting golden explosion spell, massive magic burst, particle cascade",
            aspect_ratio="9X16",
            lighting="golden dramatic",
            contrast=0.2,
            saturation=0.5,
            hook="explosion",
            winning_elements=["golden explosion", "magic burst", "particle cascade"],
            roas=44.68,
            source_video_id="v2601523",
            content_type="juqing",
            duration="15s",
        ),
        "seed": 1009,
    },
    {
        "id": "video_010",
        "angle": "magical_reward",
        "dna": WinnerDNA(
            theme="witch opens magical portal, rewards pouring out, new pet companion reveal",
            aspect_ratio="9X16",
            lighting="magical warm",
            contrast=0.15,
            saturation=0.5,
            hook="reward",
            winning_elements=["magical portal", "reward", "pet reveal"],
            roas=44.68,
            source_video_id="v2601523",
            content_type="chongwuzhanshi",
            duration="15s",
        ),
        "seed": 1010,
    },
]


def generate_single(
    variant: dict,
    director: VideoDirector,
    client: ComfyUIClient,
    executor: WorkflowExecutor,
    validator: VideoValidator,
) -> dict:
    """生成单个视频"""
    vid = variant["id"]
    angle = variant["angle"]
    dna = variant["dna"]
    seed = variant["seed"]

    print(f"\n{'='*60}")
    print(f"[Generate] {vid} | Angle: {angle} | Seed: {seed}")
    print(f"{'='*60}")

    result = {
        "id": vid,
        "creative_angle": angle,
        "source_dna": dna.source_video_id,
        "seed": seed,
        "status": "pending",
        "video_path": "",
        "flux_path": "",
        "prompt": "",
        "negative_prompt": "",
        "error": "",
        "validation": {},
    }

    try:
        # Step 1: Video Director
        print(f"[{vid}] Step 1: Video Director...")
        plan = director.direct(dna, GAME_INFO, AD_GOAL)
        result["prompt"] = plan.comfyui_workflow.positive
        result["negative_prompt"] = plan.comfyui_workflow.negative
        print(f"[{vid}]   Concept: {plan.creative_concept}")

        # Save prompt
        prompt_path = os.path.join(OUTPUT_DIR, "prompts", f"{vid}_prompt.json")
        with open(prompt_path, "w", encoding="utf-8") as f:
            json.dump({
                "positive": plan.comfyui_workflow.positive,
                "negative": plan.comfyui_workflow.negative,
                "flux_positive": plan.metadata.get("flux_positive", ""),
            }, f, ensure_ascii=False, indent=2)

        # Step 2: Flux Keyframe
        print(f"[{vid}] Step 2: Flux Keyframe...")
        flux_wf = executor.build_flux_workflow(plan, seed=seed)
        flux_gen = client.generate(flux_wf, timeout=180)

        if not flux_gen["success"]:
            result["status"] = "failed"
            result["error"] = f"Flux failed: {flux_gen.get('error', '')}"
            print(f"[{vid}]   FLUX FAILED: {result['error']}")
            return result

        flux_filename = flux_gen["filename"]
        flux_local = os.path.join(OUTPUT_DIR, "frames", f"{vid}_flux.png")
        client.download_file(flux_filename, flux_local)
        result["flux_path"] = flux_local
        print(f"[{vid}]   Flux downloaded: {flux_local}")

        # Upload image for I2V
        upload_result = client.upload_image(flux_local)
        image_ref = upload_result.get("name", os.path.basename(flux_local))

        # Step 3: Wan I2V
        print(f"[{vid}] Step 3: Wan I2V Video...")
        video_wf = executor.build_video_workflow(
            plan, model_preset="wan2.1_i2v_480p", image_ref=image_ref, seed=seed
        )

        # Save workflow
        wf_path = os.path.join(OUTPUT_DIR, "workflows", f"{vid}_workflow.json")
        with open(wf_path, "w", encoding="utf-8") as f:
            json.dump(video_wf, f, indent=2, ensure_ascii=False)

        video_gen = client.generate(video_wf, timeout=900)

        if not video_gen["success"]:
            result["status"] = "failed"
            result["error"] = f"Video failed: {video_gen.get('error', '')}"
            print(f"[{vid}]   VIDEO FAILED: {result['error']}")
            return result

        video_filename = video_gen["filename"]
        video_local = os.path.join(OUTPUT_DIR, f"{vid}.mp4")
        client.download_file(video_filename, video_local)
        result["video_path"] = video_local
        print(f"[{vid}]   Video downloaded: {video_local}")

        # Step 4: Validate
        print(f"[{vid}] Step 4: Validate...")
        validation = validator.validate(video_local)
        result["validation"] = {
            "valid": validation.valid,
            "resolution": validation.resolution,
            "duration": round(validation.duration, 1),
            "fps": round(validation.fps, 1),
            "issues": validation.issues,
        }

        if validation.valid:
            result["status"] = "success"
            print(f"[{vid}]   VALID: {validation.resolution}, {validation.duration:.1f}s")
        else:
            result["status"] = "failed"
            result["error"] = "; ".join(validation.issues)
            print(f"[{vid}]   INVALID: {result['error']}")

        # Save metadata
        meta_path = os.path.join(OUTPUT_DIR, "metadata", f"{vid}_metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        print(f"[{vid}]   EXCEPTION: {e}")

    return result


def main():
    print("="*60)
    print("P04 Video Generation Test Run")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"ComfyUI: {COMFYUI_HOST}:{COMFYUI_PORT}")
    print("="*60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "prompts"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "workflows"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "metadata"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "frames"), exist_ok=True)

    director = VideoDirector()
    client = ComfyUIClient(host=COMFYUI_HOST, port=COMFYUI_PORT)
    executor = WorkflowExecutor()
    validator = VideoValidator()

    # Health check
    health = client.health_check()
    print(f"\nComfyUI Health: {health}")
    if not health.get("ok"):
        print("ComfyUI not available, exiting.")
        return

    results: list[dict] = []
    for variant in VARIANTS:
        result = generate_single(variant, director, client, executor, validator)
        results.append(result)

        # Progress summary
        success = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "failed")
        print(f"\n[Progress] {len(results)}/10 | Success: {success} | Failed: {failed}")

    # Generation Report
    report = {
        "task_id": "P04_Video_Test_Set_001",
        "generated_at": datetime.now().isoformat(),
        "total": len(results),
        "success": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "videos": results,
    }

    report_path = os.path.join(OUTPUT_DIR, "generation_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Manual Review Template
    review_lines = [
        "# P04 Video Test Set 001 - Manual Review",
        "",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Review Instructions",
        "",
        "For each video, rate 1-5:",
        "- 1 = Very Poor",
        "- 3 = Average",
        "- 5 = Excellent / Ready for Ads",
        "",
        "---",
        "",
    ]

    for r in results:
        if r["status"] != "success":
            continue
        review_lines.extend([
            f"### {r['id']} | {r['creative_angle']}",
            "",
            f"Video: `{r['video_path']}`",
            f"Flux Frame: `{r['flux_path']}`",
            "",
            "| Metric | Score (1-5) | Notes |",
            "|--------|-------------|-------|",
            "| First Glance Attraction | | |",
            "| Character Consistency | | |",
            "| Action Intensity | | |",
            "| Game Feel | | |",
            "| Looks Like UA Ad | YES / NO | |",
            "",
            "**Issues:**",
            "",
            "**Good Points:**",
            "",
            "---",
            "",
        ])

    review_path = os.path.join(OUTPUT_DIR, "manual_review.md")
    with open(review_path, "w", encoding="utf-8") as f:
        f.write("\n".join(review_lines))

    print("\n" + "="*60)
    print("P04 Video Generation Test Run COMPLETE")
    print(f"Success: {report['success']}/{report['total']}")
    print(f"Failed: {report['failed']}/{report['total']}")
    print(f"Report: {report_path}")
    print(f"Review Template: {review_path}")
    print("="*60)


if __name__ == "__main__":
    main()
