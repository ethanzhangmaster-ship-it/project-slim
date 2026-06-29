"""专门生成Progress和Mystery类型的裂变图片"""
import json
import os
import requests
import time
from datetime import datetime

# Progress和Mystery类型的提示词
PROGRESS_MYSTERY_PROMPTS = [
    {
        "id": "progress_dragon_chain",
        "type": "progress",
        "hook": "Lv1 → Lv100",
        "prompt": """Create a NEW Facebook ad for P04 Witch merge game. Mobile portrait 9:16, professional game ad quality, 3D cartoon style.

Show evolution progression: Egg → Baby Dragon → Teen Dragon → Legendary Dragon, with magical glow effects connecting each stage. Dark purple mystical background with glowing particles. Castle silhouette in far background.

Emotion: mysterious and enchanting
Hook text: "Can You Reach The End?"

Do NOT add watermarks or realistic photos. Keep art style consistent with mobile game advertising."""
    },
    {
        "id": "progress_flower_chain", 
        "type": "progress",
        "hook": "Seed → God Tree",
        "prompt": """Create a NEW Facebook ad for P04 Witch merge game. Mobile portrait 9:16, professional game ad quality, 3D cartoon style.

Show evolution progression: Seed → Sprout → Magic Flower → God Tree, with mystical purple energy flowing between stages. Enchanted forest background with floating sparkles.

Emotion: mysterious and enchanting
Hook text: "Wait For Final Evolution"

Do NOT add watermarks or realistic photos. Keep art style consistent with mobile game advertising."""
    },
    {
        "id": "mystery_secret_dragon",
        "type": "mystery",
        "hook": "??? Inside",
        "prompt": """Create a NEW Facebook ad for P04 Witch merge game. Mobile portrait 9:16, professional game ad quality, 3D cartoon style.

Show a giant glowing mysterious egg cracking open, with rays of golden light bursting out. Question mark floating above. Witch character looking shocked in the corner. Dark mysterious atmosphere with magical particles.

Emotion: mysterious and enchanting
Hook text: "What's Inside?"

Do NOT add watermarks or realistic photos. Keep art style consistent with mobile game advertising."""
    },
    {
        "id": "mystery_secret_witch",
        "type": "mystery",
        "hook": "??? Witch",
        "prompt": """Create a NEW Facebook ad for P04 Witch merge game. Mobile portrait 9:16, professional game ad quality, 3D cartoon style.

Show a mysterious hooded figure with magical aura around hands. Castle gate in background slightly open revealing magical light inside. Dark purple and black color scheme with glowing magical effects.

Emotion: mysterious and enchanting
Hook text: "Secret Witch Inside"

Do NOT add watermarks or realistic photos. Keep art style consistent with mobile game advertising."""
    }
]

OUTPUT_DIR = "output/P04_Progress_Mystery"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    from market_ops.clients.lovart import LovartClient
    client = LovartClient()
    
    print("\n=== 生成Progress和Mystery类型图片 ===\n")
    
    results = []
    
    for i, item in enumerate(PROGRESS_MYSTERY_PROMPTS):
        print(f"[{i+1}/{len(PROGRESS_MYSTERY_PROMPTS)}] {item['type']}: {item['hook']}")
        print(f"  Prompt: {item['prompt'][:80]}...")
        
        try:
            # 增加超时处理：Lovart默认300秒超时，我们增加轮询次数
            result = client.generate_image(item["prompt"])
            
            if result and hasattr(result, 'image_urls') and result.image_urls:
                img_url = result.image_urls[0]
                print(f"  ✓ 生成成功!")
                
                # 下载图片
                response = requests.get(img_url)
                img_path = f"{OUTPUT_DIR}/{item['id']}.png"
                with open(img_path, 'wb') as f:
                    f.write(response.content)
                print(f"  ✓ 保存: {img_path}")
                
                results.append({
                    "id": item["id"],
                    "type": item["type"],
                    "hook": item["hook"],
                    "url": img_url,
                    "path": img_path,
                    "success": True
                })
            else:
                print(f"  ✗ 无图片URL")
                results.append({
                    "id": item["id"],
                    "type": item["type"],
                    "hook": item["hook"],
                    "success": False
                })
                
        except Exception as e:
            print(f"  ✗ 错误: {e}")
            results.append({
                "id": item["id"],
                "type": item["type"],
                "hook": item["hook"],
                "error": str(e),
                "success": False
            })
        
        time.sleep(3)
    
    # 保存结果
    with open(f"{OUTPUT_DIR}/results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    success_count = sum(1 for r in results if r.get("success"))
    print(f"\n✅ 完成: {success_count}/{len(results)} 张图片")
    
    return results

if __name__ == "__main__":
    main()