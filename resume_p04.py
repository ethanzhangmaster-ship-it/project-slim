"""Resume P04 - Generate remaining videos only"""
import sys, os, json, requests
from datetime import datetime
sys.path.insert(0, 'src')
os.environ['NO_PROXY'] = '192.168.124.13'

from market_ops.creative_intelligence.video_director import VideoDirector, WinnerDNA, GameInfo, AdGoal
from market_ops.creative_intelligence.video_generation.comfyui_client import ComfyUIClient
from market_ops.creative_intelligence.video_generation.workflow_executor import WorkflowExecutor
from market_ops.creative_intelligence.video_generation.video_validator import VideoValidator

OUTPUT_DIR = "outputs/P04_Video_Test_Set_001"
client = ComfyUIClient(host="192.168.124.13", port=8188)
executor = WorkflowExecutor()
validator = VideoValidator()
director = VideoDirector()

game = GameInfo(game="Merge Witch", genre="merge puzzle", core_loop="merge items upgrade castle",
                target="US female 25-45", key_characters=["witch","dragon"], key_items=["magic crystal","merge orb","chest"])
goal = AdGoal(goal="install", duration=15, platform="facebook", format="9:16")

VARIANTS = [
    {"id":"video_003","angle":"merge_gameplay","seed":1003,
     "dna":WinnerDNA(theme="magic stones merge together with bright fusion glow, castle upgrade",aspect_ratio="9X16",
                      lighting="bright magical",contrast=0.1,saturation=0.5,hook="merge",
                      winning_elements=["merge action","fusion glow","building upgrade"],
                      roas=18.36,source_video_id="v2601163",content_type="wanfashipin",duration="15s")},
    {"id":"video_005","angle":"reward_fantasy","seed":1005,
     "dna":WinnerDNA(theme="open treasure chest, coins explosion, new legendary character unlock",aspect_ratio="9X16",
                      lighting="golden radiant",contrast=0.2,saturation=0.55,hook="reward",
                      winning_elements=["treasure chest","coin burst","character unlock"],
                      roas=44.68,source_video_id="v2601523",content_type="juesezhanshi",duration="15s")},
    {"id":"video_007","angle":"orbit_merge","seed":1007,
     "dna":WinnerDNA(theme="orbit shot around witch merging magic crystals, bright fusion glow",aspect_ratio="9X16",
                      lighting="magical",contrast=0.15,saturation=0.5,hook="merge",
                      winning_elements=["orbit shot","merge","fusion glow"],
                      roas=18.36,source_video_id="v2601163",content_type="wanfashipin",duration="15s")},
    {"id":"video_008","angle":"tracking_upgrade","seed":1008,
     "dna":WinnerDNA(theme="tracking shot following witch upgrading legendary armor with golden light",aspect_ratio="9X16",
                      lighting="golden",contrast=0.15,saturation=0.45,hook="upgrade",
                      winning_elements=["tracking","armor upgrade","golden light"],
                      roas=18.36,source_video_id="v2601163",content_type="juesezhanshi",duration="15s")},
    {"id":"video_009","angle":"golden_explosion","seed":1009,
     "dna":WinnerDNA(theme="witch casting golden explosion spell, massive magic burst, particle cascade",aspect_ratio="9X16",
                      lighting="golden dramatic",contrast=0.2,saturation=0.5,hook="explosion",
                      winning_elements=["golden explosion","magic burst","particle cascade"],
                      roas=44.68,source_video_id="v2601523",content_type="juqing",duration="15s")},
    {"id":"video_010","angle":"magical_reward","seed":1010,
     "dna":WinnerDNA(theme="witch opens magical portal, rewards pouring out, new pet companion reveal",aspect_ratio="9X16",
                      lighting="magical warm",contrast=0.15,saturation=0.5,hook="reward",
                      winning_elements=["magical portal","reward","pet reveal"],
                      roas=44.68,source_video_id="v2601523",content_type="chongwuzhanshi",duration="15s")},
]

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(os.path.join(OUTPUT_DIR, "generation.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()

def gen(v):
    vid = v["id"]
    dna = v["dna"]
    seed = v["seed"]
    angle = v["angle"]

    result = {"id":vid,"creative_angle":angle,"source_dna":dna.source_video_id,
              "seed":seed,"status":"pending","video_path":"","flux_path":"",
              "prompt":"","negative_prompt":"","error":"","validation":{}}

    try:
        # Skip if already exists
        if os.path.exists(os.path.join(OUTPUT_DIR, f"{vid}.mp4")):
            log(f"{vid} SKIP - already exists")
            result["status"] = "success"
            result["video_path"] = os.path.join(OUTPUT_DIR, f"{vid}.mp4")
            return result

        log(f"{vid} START {angle} seed={seed}")

        # Step 1: Director
        log(f"{vid} Director...")
        plan = director.direct(dna, game, goal)
        result["prompt"] = plan.comfyui_workflow.positive
        result["negative_prompt"] = plan.comfyui_workflow.negative
        with open(os.path.join(OUTPUT_DIR, "prompts", f"{vid}_prompt.json"), "w", encoding="utf-8") as f:
            json.dump({"positive":plan.comfyui_workflow.positive,"negative":plan.comfyui_workflow.negative}, f, ensure_ascii=False, indent=2)

        # Step 2: Flux
        flux_local = os.path.join(OUTPUT_DIR, "frames", f"{vid}_flux.png")
        if not os.path.exists(flux_local):
            log(f"{vid} Flux...")
            flux_wf = executor.build_flux_workflow(plan, seed=seed)
            flux_submit = client.submit(flux_wf)
            flux_pid = flux_submit["prompt_id"]
            flux_wait = client.wait_for_completion(flux_pid, poll_interval=5, max_wait=600)
            if not flux_wait["completed"]:
                result["status"] = "failed"
                result["error"] = f"Flux timeout: {flux_wait['error']}"
                log(f"{vid} FLUX FAILED")
                return result
            flux_fn = client.get_output_filename(flux_wait["data"])
            client.download_file(flux_fn, flux_local)
            log(f"{vid} Flux done")
        else:
            log(f"{vid} Flux SKIP - already exists")

        result["flux_path"] = flux_local
        upload = client.upload_image(flux_local)
        image_ref = upload.get("name", os.path.basename(flux_local))

        # Step 3: Wan I2V
        log(f"{vid} Wan I2V...")
        video_wf = executor.build_video_workflow(plan, model_preset="wan2.1_i2v_480p", image_ref=image_ref, seed=seed)
        with open(os.path.join(OUTPUT_DIR, "workflows", f"{vid}_workflow.json"), "w", encoding="utf-8") as f:
            json.dump(video_wf, f, indent=2, ensure_ascii=False)

        video_submit = client.submit(video_wf)
        video_pid = video_submit["prompt_id"]
        video_wait = client.wait_for_completion(video_pid, poll_interval=10, max_wait=1800)
        if not video_wait["completed"]:
            result["status"] = "failed"
            result["error"] = f"Video timeout: {video_wait['error']}"
            log(f"{vid} VIDEO FAILED")
            return result

        video_fn = client.get_output_filename(video_wait["data"])
        video_local = os.path.join(OUTPUT_DIR, f"{vid}.mp4")
        client.download_file(video_fn, video_local)
        result["video_path"] = video_local
        log(f"{vid} Video done")

        # Step 4: Validate
        val = validator.validate(video_local)
        result["validation"] = {"valid":val.valid,"resolution":val.resolution,"duration":round(val.duration,1),"fps":round(val.fps,1),"issues":val.issues}
        result["status"] = "success" if val.valid else "failed"
        if val.valid:
            log(f"{vid} VALID {val.resolution} {val.duration:.1f}s")
        else:
            log(f"{vid} INVALID {val.issues}")

        with open(os.path.join(OUTPUT_DIR, "metadata", f"{vid}_metadata.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        log(f"{vid} EXCEPTION: {e}")

    return result

def main():
    for sub in ["prompts","workflows","metadata","frames"]:
        os.makedirs(os.path.join(OUTPUT_DIR, sub), exist_ok=True)

    results = []
    for v in VARIANTS:
        r = gen(v)
        results.append(r)
        ok = sum(1 for x in results if x["status"]=="success")
        fail = sum(1 for x in results if x["status"]=="failed")
        log(f"PROGRESS: {len(results)}/6 | OK:{ok} | FAIL:{fail}")

    # Final report
    existing = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.mp4')]
    log(f"FINAL: {len(existing)}/10 MP4 files generated")
    log("="*60)

if __name__ == "__main__":
    main()
