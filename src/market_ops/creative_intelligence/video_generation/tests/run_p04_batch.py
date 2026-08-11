"""P04 Batch Generation - Fixed version with progress logging

Writes progress to log file to avoid stdout buffering issues.
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
from market_ops.creative_intelligence.video_generation.comfyui_client import ComfyUIClient
from market_ops.creative_intelligence.video_generation.workflow_executor import WorkflowExecutor
from market_ops.creative_intelligence.video_generation.video_validator import VideoValidator

OUTPUT_DIR = "outputs/P04_Video_Test_Set_001"
COMFYUI_HOST = "192.168.124.13"
COMFYUI_PORT = 8188

GAME_INFO = GameInfo(
    game="Merge Witch", genre="merge puzzle",
    core_loop="merge items upgrade castle", target="US female 25-45",
    art_style="fantasy 2D",
    key_characters=["witch", "dragon"],
    key_items=["magic crystal", "merge orb", "chest"],
)
AD_GOAL = AdGoal(goal="install", duration=15, platform="facebook", format="9:16")

VARIANTS = [
    {"id": "video_002", "angle": "witch_transformation", "seed": 1002,
     "dna": WinnerDNA(theme="weak witch to legendary witch magical transformation", aspect_ratio="9X16",
                      lighting="warm golden", contrast=0.15, saturation=0.45, hook="transformation",
                      winning_elements=["character evolution", "glowing particles", "legendary skin"],
                      roas=44.68, source_video_id="v2601523", content_type="juesezhanshi", duration="15s")},
    {"id": "video_003", "angle": "merge_gameplay", "seed": 1003,
     "dna": WinnerDNA(theme="magic stones merge together with bright fusion glow, castle upgrade", aspect_ratio="9X16",
                      lighting="bright magical", contrast=0.1, saturation=0.5, hook="merge",
                      winning_elements=["merge action", "fusion glow", "building upgrade"],
                      roas=18.36, source_video_id="v2601163", content_type="wanfashipin", duration="15s")},
    {"id": "video_004", "angle": "before_after_upgrade", "seed": 1004,
     "dna": WinnerDNA(theme="broken castle transforms into beautiful kingdom through merge magic", aspect_ratio="9X16",
                      lighting="warm cinematic", contrast=0.15, saturation=0.45, hook="upgrade",
                      winning_elements=["before after", "castle rebuild", "magical transformation"],
                      roas=18.36, source_video_id="v2601163", content_type="wanfashipin", duration="15s")},
    {"id": "video_005", "angle": "reward_fantasy", "seed": 1005,
     "dna": WinnerDNA(theme="open treasure chest, coins explosion, new legendary character unlock", aspect_ratio="9X16",
                      lighting="golden radiant", contrast=0.2, saturation=0.55, hook="reward",
                      winning_elements=["treasure chest", "coin burst", "character unlock"],
                      roas=44.68, source_video_id="v2601523", content_type="juesezhanshi", duration="15s")},
    {"id": "video_006", "angle": "fast_push_transform", "seed": 1006,
     "dna": WinnerDNA(theme="fast push in on witch, magical transformation with glowing particles", aspect_ratio="9X16",
                      lighting="warm", contrast=0.15, saturation=0.45, hook="fast transformation",
                      winning_elements=["fast push in", "transformation", "particles"],
                      roas=44.68, source_video_id="v2601523", content_type="juesezhanshi", duration="15s")},
    {"id": "video_007", "angle": "orbit_merge", "seed": 1007,
     "dna": WinnerDNA(theme="orbit shot around witch merging magic crystals, bright fusion glow", aspect_ratio="9X16",
                      lighting="magical", contrast=0.15, saturation=0.5, hook="merge",
                      winning_elements=["orbit shot", "merge", "fusion glow"],
                      roas=18.36, source_video_id="v2601163", content_type="wanfashipin", duration="15s")},
    {"id": "video_008", "angle": "tracking_upgrade", "seed": 1008,
     "dna": WinnerDNA(theme="tracking shot following witch upgrading legendary armor with golden light", aspect_ratio="9X16",
                      lighting="golden", contrast=0.15, saturation=0.45, hook="upgrade",
                      winning_elements=["tracking", "armor upgrade", "golden light"],
                      roas=18.36, source_video_id="v2601163", content_type="juesezhanshi", duration="15s")},
    {"id": "video_009", "angle": "golden_explosion", "seed": 1009,
     "dna": WinnerDNA(theme="witch casting golden explosion spell, massive magic burst, particle cascade", aspect_ratio="9X16",
                      lighting="golden dramatic", contrast=0.2, saturation=0.5, hook="explosion",
                      winning_elements=["golden explosion", "magic burst", "particle cascade"],
                      roas=44.68, source_video_id="v2601523", content_type="juqing", duration="15s")},
    {"id": "video_010", "angle": "magical_reward", "seed": 1010,
     "dna": WinnerDNA(theme="witch opens magical portal, rewards pouring out, new pet companion reveal", aspect_ratio="9X16",
                      lighting="magical warm", contrast=0.15, saturation=0.5, hook="reward",
                      winning_elements=["magical portal", "reward", "pet reveal"],
                      roas=44.68, source_video_id="v2601523", content_type="chongwuzhanshi", duration="15s")},
]


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(os.path.join(OUTPUT_DIR, "generation.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def generate_video(variant: dict, director: VideoDirector, client: ComfyUIClient,
                   executor: WorkflowExecutor, validator: VideoValidator) -> dict:
    vid = variant["id"]
    angle = variant["angle"]
    dna = variant["dna"]
    seed = variant["seed"]

    result = {
        "id": vid, "creative_angle": angle, "source_dna": dna.source_video_id,
        "seed": seed, "status": "pending", "video_path": "", "flux_path": "",
        "prompt": "", "negative_prompt": "", "error": "", "validation": {},
    }

    try:
        log(f"{vid} START angle={angle} seed={seed}")

        # Step 1: Director
        log(f"{vid} Step 1: Director...")
        plan = director.direct(dna, GAME_INFO, AD_GOAL)
        result["prompt"] = plan.comfyui_workflow.positive
        result["negative_prompt"] = plan.comfyui_workflow.negative
        log(f"{vid}   Concept: {plan.creative_concept}")

        with open(os.path.join(OUTPUT_DIR, "prompts", f"{vid}_prompt.json"), "w", encoding="utf-8") as f:
            json.dump({"positive": plan.comfyui_workflow.positive, "negative": plan.comfyui_workflow.negative,
                       "flux_positive": plan.metadata.get("flux_positive", "")}, f, ensure_ascii=False, indent=2)

        # Step 2: Flux
        log(f"{vid} Step 2: Flux...")
        flux_wf = executor.build_flux_workflow(plan, seed=seed)
        flux_submit = client.submit(flux_wf)
        flux_pid = flux_submit["prompt_id"]
        log(f"{vid}   Flux submitted: {flux_pid}")

        # Wait for flux
        flux_wait = client.wait_for_completion(flux_pid, poll_interval=5, max_wait=300)
        if not flux_wait["completed"]:
            result["status"] = "failed"
            result["error"] = f"Flux timeout: {flux_wait['error']}"
            log(f"{vid}   FLUX FAILED: {result['error']}")
            return result

        flux_fn = client.get_output_filename(flux_wait["data"])
        flux_local = os.path.join(OUTPUT_DIR, "frames", f"{vid}_flux.png")
        client.download_file(flux_fn, flux_local)
        result["flux_path"] = flux_local
        log(f"{vid}   Flux done: {flux_local}")

        # Upload for I2V
        upload = client.upload_image(flux_local)
        image_ref = upload.get("name", os.path.basename(flux_local))

        # Step 3: Wan I2V
        log(f"{vid} Step 3: Wan I2V...")
        video_wf = executor.build_video_workflow(plan, model_preset="wan2.1_i2v_480p",
                                                  image_ref=image_ref, seed=seed)
        with open(os.path.join(OUTPUT_DIR, "workflows", f"{vid}_workflow.json"), "w", encoding="utf-8") as f:
            json.dump(video_wf, f, indent=2, ensure_ascii=False)

        video_submit = client.submit(video_wf)
        video_pid = video_submit["prompt_id"]
        log(f"{vid}   Wan submitted: {video_pid}")

        # Wait for video
        video_wait = client.wait_for_completion(video_pid, poll_interval=10, max_wait=900)
        if not video_wait["completed"]:
            result["status"] = "failed"
            result["error"] = f"Video timeout: {video_wait['error']}"
            log(f"{vid}   VIDEO FAILED: {result['error']}")
            return result

        video_fn = client.get_output_filename(video_wait["data"])
        video_local = os.path.join(OUTPUT_DIR, f"{vid}.mp4")
        client.download_file(video_fn, video_local)
        result["video_path"] = video_local
        log(f"{vid}   Video done: {video_local}")

        # Step 4: Validate
        log(f"{vid} Step 4: Validate...")
        val = validator.validate(video_local)
        result["validation"] = {"valid": val.valid, "resolution": val.resolution,
                                "duration": round(val.duration, 1), "fps": round(val.fps, 1),
                                "issues": val.issues}
        if val.valid:
            result["status"] = "success"
            log(f"{vid}   VALID: {val.resolution}, {val.duration:.1f}s")
        else:
            result["status"] = "failed"
            result["error"] = "; ".join(val.issues)
            log(f"{vid}   INVALID: {result['error']}")

        # Save metadata
        with open(os.path.join(OUTPUT_DIR, "metadata", f"{vid}_metadata.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        log(f"{vid}   EXCEPTION: {e}")

    return result


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for sub in ["prompts", "workflows", "metadata", "frames"]:
        os.makedirs(os.path.join(OUTPUT_DIR, sub), exist_ok=True)

    director = VideoDirector()
    client = ComfyUIClient(host=COMFYUI_HOST, port=COMFYUI_PORT)
    executor = WorkflowExecutor()
    validator = VideoValidator()

    health = client.health_check()
    log(f"ComfyUI Health: {health}")
    if not health.get("ok"):
        log("ComfyUI not available, exiting.")
        return

    results = []
    for variant in VARIANTS:
        r = generate_video(variant, director, client, executor, validator)
        results.append(r)
        success = sum(1 for x in results if x["status"] == "success")
        failed = sum(1 for x in results if x["status"] == "failed")
        log(f"PROGRESS: {len(results)}/9 | Success: {success} | Failed: {failed}")

    # Report
    report = {
        "task_id": "P04_Video_Test_Set_001",
        "generated_at": datetime.now().isoformat(),
        "total": len(results) + 1,  # +1 for video_001 done separately
        "success": sum(1 for r in results if r["status"] == "success") + 1,
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "videos": [{"id": "video_001", "creative_angle": "dragon_attack", "status": "success",
                    "source_dna": "v2601523", "seed": 1001}] + results,
    }

    with open(os.path.join(OUTPUT_DIR, "generation_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Manual review template
    lines = ["# P04 Video Test Set 001 - Manual Review", "", f"Generated: {datetime.now().isoformat()}", "",
             "## Review Instructions", "", "Rate 1-5:", "- 1 = Very Poor", "- 3 = Average", "- 5 = Excellent", "", "---", ""]
    for r in report["videos"]:
        if r["status"] != "success":
            continue
        lines.extend([
            f"### {r['id']} | {r['creative_angle']}", "",
            f"Video: `{OUTPUT_DIR}/{r['id']}.mp4`", "",
            "| Metric | Score (1-5) | Notes |", "|--------|-------------|-------|",
            "| First Glance Attraction | | |", "| Character Consistency | | |",
            "| Action Intensity | | |", "| Game Feel | | |",
            "| Looks Like UA Ad | YES / NO | |", "", "**Issues:**", "", "**Good Points:**", "", "---", "",
        ])
    with open(os.path.join(OUTPUT_DIR, "manual_review.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log("=" * 60)
    log(f"COMPLETE: Success {report['success']}/{report['total']}, Failed {report['failed']}")
    log("=" * 60)


if __name__ == "__main__":
    main()
