"""生成三种类型各一张测试图"""
import json
import os
import requests
import time
from market_ops.clients.lovart import LovartClient

OUTPUT_DIR = "output/P04_Witch_Factory/test_samples"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    # 读取提示词文件
    with open("output/P04_Witch_Factory/batch_001_prompts.json", "r", encoding="utf-8") as f:
        prompts = json.load(f)
    
    # 各选一个代表
    samples = {
        "collection": next(p for p in prompts if p["hook_type"] == "collection" and p["reward_type"] == "dragon"),
        "progress": next(p for p in prompts if p["hook_type"] == "progress" and p["reward_type"] == "dragon"),
        "mystery": next(p for p in prompts if p["hook_type"] == "curiosity" and p["reward_type"] == "secret_dragon"),
    }
    
    client = LovartClient()
    
    for hook_type, data in samples.items():
        print(f"\n=== 生成 {hook_type} 类型 ===")
        print(f"ID: {data['creative_id']}")
        print(f"Reward: {data['reward_type']}")
        print(f"Prompt: {data['prompt']}")
        
        try:
            # 生成图片
            result = client.generate_image(data["prompt"])
            
            if result and hasattr(result, 'image_urls') and result.image_urls:
                img_url = result.image_urls[0]
                print(f"✓ 生成成功: {img_url[:50]}...")
                
                # 下载图片
                response = requests.get(img_url)
                img_path = f"{OUTPUT_DIR}/{hook_type}_{data['creative_id']}.png"
                with open(img_path, 'wb') as f:
                    f.write(response.content)
                print(f"✓ 保存成功: {img_path}")
                
            time.sleep(2)
            
        except Exception as e:
            print(f"✗ 生成失败: {e}")
            continue
    
    print(f"\n✅ 测试图已生成在: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()