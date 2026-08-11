"""Extract Visual DNA from real FB winner images using GPT-4o Vision.

Uses the existing DNAExtractor from performance_grounded_intelligence.
"""
import json
import sys
import base64
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

ROOT = Path(r"d:\project_slim\project_slim")

# Load real winners DNA (with local image paths)
dna_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "real_winners_dna.json"
with open(dna_path, "r", encoding="utf-8") as f:
    winners = json.load(f)

print(f"Loaded {len(winners)} winners from real_winners_dna.json")

# Filter those with valid local images
valid = []
for w in winners:
    img_path = w.get("local_image_path", "")
    if img_path and Path(img_path).exists():
        valid.append(w)
    else:
        print(f"  SKIP {w['creative_id']}: no local image")

print(f"Valid with local images: {len(valid)}")
print(f"Top 5:")
for w in valid[:5]:
    print(f"  {w['creative_id']} ({w['platform']}) spend=${w['spend']:.0f} rev=${w['revenue']:.0f}")

# ── Vision DNA Extraction ──

VISION_PROMPT = """Analyze this mobile game ad creative image for a Merge Dragon-like puzzle game called "Evolution Merge".

Return a JSON object with:

{
  "subject": "main subject of the image (e.g., witch character, dragon, merge board)",
  "composition": "describe the overall layout and composition",
  "palette": "describe the color palette (main colors and accent colors)",
  "lighting": "describe the lighting style and mood",
  "ui_elements": ["list of visible UI elements (merge board, buttons, progress bars, etc.)"],
  "overlay_text": "any visible text overlay or copy on the image",
  "cta_style": "describe the call-to-action style if visible",
  "character_pose": "describe the main character's pose and action if visible",
  "mood": "describe the overall mood and atmosphere",
  "hook_type": "what type of hook this creative uses (e.g., merge_upgrade, reward_reveal, character_showcase, before_after, collection, story_hook, asmr_cleaning, hatching_egg)",
  "gameplay_elements": ["list of gameplay elements visible (merge items, dragon eggs, castles, gardens, etc.)"],
  "standout_features": ["what makes this creative visually distinctive"],
  "overall_summary": "one-line summary of why this creative works"
}

Only return the JSON, no explanations."""

# OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("ERROR: No OPENAI_API_KEY found!")
    sys.exit(1)

client = OpenAI(api_key=api_key)
model = "gpt-4o"

print(f"\nUsing model: {model}")
print(f"API key: {'YES' if api_key else 'NO'} ({len(api_key)} chars)")

# Extract DNA for each winner
DNA_MAX = 20  # Limit to top 20 for cost control
extract_count = min(len(valid), DNA_MAX)

print(f"\n{'='*60}")
print(f"Extracting Visual DNA for top {extract_count} winners...")
print(f"{'='*60}")

results = []
for i, w in enumerate(valid[:extract_count]):
    cid = w["creative_id"]
    img_path = w["local_image_path"]
    
    print(f"\n[{i+1}/{extract_count}] {cid}")
    print(f"  Image: {Path(img_path).name}")
    
    try:
        # Read and encode image
        with open(img_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        # Call GPT-4o Vision
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}",
                        "detail": "low"
                    }}
                ]
            }],
            max_tokens=1000,
            temperature=0.1,
        )
        
        content = response.choices[0].message.content
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        
        dna = json.loads(content)
        print(f"  Subject: {dna.get('subject', 'N/A')[:60]}")
        print(f"  Hook: {dna.get('hook_type', 'N/A')}")
        print(f"  Palette: {dna.get('palette', 'N/A')[:60]}")
        
        # Merge with performance data
        record = {
            "creative_id": cid,
            "creative_name": w.get("creative_name", ""),
            "platform": w.get("platform", "unknown"),
            "spend": w.get("spend", 0),
            "revenue": w.get("revenue", 0),
            "roas": w.get("roas", 0),
            "installs": w.get("installs", 0),
            "local_image_path": img_path,
            "eagle_filename": w.get("eagle_filename", ""),
            "visual_dna": dna,
            "extracted_at": json.loads(json.dumps(str(__import__('datetime').datetime.now()))),
        }
        results.append(record)
        
    except Exception as e:
        print(f"  ERROR: {e}")
        # Fallback: rule-based DNA
        record = {
            "creative_id": cid,
            "creative_name": w.get("creative_name", ""),
            "platform": w.get("platform", "unknown"),
            "spend": w.get("spend", 0),
            "revenue": w.get("revenue", 0),
            "roas": w.get("roas", 0),
            "installs": w.get("installs", 0),
            "local_image_path": img_path,
            "eagle_filename": w.get("eagle_filename", ""),
            "visual_dna": {
                "subject": "unknown",
                "composition": "unknown",
                "palette": "unknown",
                "hook_type": "unknown",
                "overall_summary": "Vision API failed",
                "status": "error",
                "error": str(e),
            },
            "extracted_at": str(__import__('datetime').datetime.now()),
        }
        results.append(record)

# Save enriched DNA
output_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "real_winners_dna_vision.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump({
        "version": "1.0.0",
        "source": "facebook_graph_api",
        "vision_model": model,
        "total": len(results),
        "winners": results,
    }, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"DNA Extraction Complete!")
print(f"  Extracted: {len(results)} records")
print(f"  Saved to: {output_path}")
print(f"{'='*60}")

# Summary stats
hook_types = {}
for r in results:
    ht = r["visual_dna"].get("hook_type", "unknown")
    hook_types[ht] = hook_types.get(ht, 0) + 1

print(f"\nHook Type Distribution:")
for ht, count in sorted(hook_types.items(), key=lambda x: -x[1]):
    print(f"  {ht}: {count}")