"""Video Generation Pipeline Runner - 视频生成流水线运行脚本"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.market_ops.video_generation.video_generation_api import VideoGenerationPipeline


def main():
    blueprint_dir = Path(__file__).resolve().parents[1] / "output" / "video_blueprint" / "V001"
    
    print("=" * 60)
    print("Video Generation Pipeline V4.5")
    print("=" * 60)
    
    print("\n[1/5] Compiling Blueprint...")
    pipeline = VideoGenerationPipeline(str(blueprint_dir))
    
    print("\n[2/5] Adapting to platforms...")
    platforms = ["veo", "kling", "runway", "pika", "hailuo", "luma", "comfyui"]
    platform_prompts = pipeline.adapt(platforms)
    
    print(f"  Generated prompts for {len(platform_prompts)} shots x {len(platforms)} platforms")
    
    print("\n[3/5] Scheduling generation...")
    schedule_result = pipeline.schedule(platform_prompts, mode="sequential")
    
    print(f"  Success: {len(schedule_result['success'])}")
    print(f"  Failed: {len(schedule_result['failed'])}")
    
    print("\n[4/5] Reviewing output...")
    review_result = pipeline.review()
    
    print(f"  Review: {'PASS' if review_result['review']['passed'] else 'FAIL'}")
    print(f"  Issues: {review_result['review']['issues']}")
    print(f"  Consistency Score: {review_result['consistency']}")
    print(f"  Quality Score: {review_result['quality']['score']}")
    print(f"  Predicted CTR: {review_result['quality']['predicted_ctr']}%")
    print(f"  Predicted IPM: {review_result['quality']['predicted_ipm']}")
    print(f"  Predicted ROAS: {review_result['quality']['predicted_roas']}x")
    
    print("\n[5/5] Exporting delivery package...")
    export_result = pipeline.export()
    
    print(f"  Variant ID: {export_result['variant_id']}")
    print(f"  Total Files: {export_result['total_files']}")
    print(f"  Blueprint: {export_result['blueprint_files']}")
    print(f"  Prompts: {export_result['prompt_files']}")
    print(f"  Review: {export_result['review_files']}")
    print(f"  Reports: {export_result['report_files']}")
    
    print("\n" + "=" * 60)
    print("Pipeline Complete!")
    print("=" * 60)
    
    output_dir = pipeline.output_dir
    print(f"\nOutput Directory: {output_dir}")
    
    files_generated = [
        "master_prompt.json",
        "platform_prompt.json",
        "generation_plan.json",
        "generation_log.json",
        "cost_report.json",
        "review.json",
        "consistency_report.json",
    ]
    
    print("\nFiles Generated:")
    for fname in files_generated:
        path = output_dir / fname
        status = "✓" if path.exists() else "✗"
        print(f"  {status} {fname}")
    
    delivery_dir = output_dir.parent / "delivery" / export_result["variant_id"]
    if delivery_dir.exists():
        print(f"\nDelivery Package: {delivery_dir}")


if __name__ == "__main__":
    main()