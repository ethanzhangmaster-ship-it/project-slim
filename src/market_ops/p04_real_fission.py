"""P04 Witch 真实裂变素材生成"""
from market_ops.clients.lovart import LovartClient
import time

SOURCE_DIR = r"D:\p4素材\新建文件夹 (3)"
OUTPUT_DIR = r"d:\ethan\Documents\市场会议\output\P04_Real_Fission"

def main():
    client = LovartClient()
    
    # 使用P04赢家的真实特征
    base_prompts = [
        {
            "hook": "Don't Merge Them!",
            "prompt": """3D cartoon style, cute baby dragon character sitting in witch's arms, surrounded by magical creatures including rainbow eggs, sparkles, small fairies, holding glowing treasure chest, purple witch queen with white hair wearing crown and elegant robe, castle silhouette background with full moon night sky, mystical forest setting with magical particles floating, whimsical mood, professional mobile game advertising art, mobile portrait 9:16 aspect ratio, high quality illustration"""
        },
        {
            "hook": "Only 1% Can Reach This",
            "prompt": """3D cartoon style, adorable baby dragon sitting on golden treasure pile, surrounded by magical creatures like phoenix, unicorn, rainbow eggs, sparkles everywhere, cute witch character with purple outfit holding magical staff, enchanted castle in background with glowing windows, magical glowing atmosphere, rich detailed fantasy scene, whimsical inviting mood, professional mobile game ad art, mobile portrait 9:16"""
        },
        {
            "hook": "Secret Dragon Inside",
            "prompt": """3D cartoon style, mysterious glowing egg cracking open revealing baby dragon inside, surrounded by magical creatures including unicorn, phoenix, cute fairies, magical sparkles, cute witch character with white hair and crown looking surprised, enchanted mystical forest background, magical glowing particles, dark purple and gold color scheme, professional game advertising art, mobile portrait 9:16 aspect ratio"""
        },
        {
            "hook": "Wait For Final Evolution",
            "prompt": """3D cartoon style, evolution sequence showing cute creatures transforming from egg to legendary dragon, magical energy swirling around creatures, witch character watching in amazement, floating castle merge mechanics in background, sparkles and magical effects, epic fantasy atmosphere, purple and gold magical lighting, professional mobile game ad, mobile portrait 9:16"""
        },
        {
            "hook": "Merge Witches Build Empire",
            "prompt": """3D cartoon style, witch character standing proudly with castle merge progression behind her showing hut to mansion to castle upgrade, surrounded by cute magical creatures, magical glowing purple energy streams connecting elements, dark fantasy atmosphere with warm golden castle window lighting, detailed fantasy art, professional game advertising, mobile portrait 9:16"""
        },
        {
            "hook": "200+ Creatures to Collect",
            "prompt": """3D cartoon style, variety of cute magical creatures displayed together - baby dragons, unicorns, phoenixes, rainbow eggs, fairies, magical plants, witch character in center with welcoming smile holding baby dragon, enchanted forest background, warm magical lighting, rich colorful detailed scene, professional mobile game ad art, 9:16 portrait"""
        }
    ]
    
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    results = []
    
    for i, item in enumerate(base_prompts):
        print(f"\n[{i+1}/{len(base_prompts)}] Generating: {item['hook']}")
        
        try:
            result = client.generate_image(item["prompt"])
            
            if result and hasattr(result, 'image_urls') and result.image_urls:
                img_url = result.image_urls[0]
                print(f"    Success! URL: {img_url[:50]}...")
                
                results.append({
                    "hook": item["hook"],
                    "prompt": item["prompt"],
                    "url": img_url
                })
                
                # 下载图片
                import requests
                response = requests.get(img_url)
                img_path = f"{OUTPUT_DIR}/{i+1:02d}_{item['hook'].replace(' ', '_')[:20]}.png"
                with open(img_path, 'wb') as f:
                    f.write(response.content)
                print(f"    Saved: {img_path}")
                
            time.sleep(2)
            
        except Exception as e:
            print(f"    Error: {e}")
            continue
    
    # 保存结果
    import json
    with open(f"{OUTPUT_DIR}/prompts.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n\nDone! Generated {len(results)} images in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
