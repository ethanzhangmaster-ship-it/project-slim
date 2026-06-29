"""调试Lovart API调用"""
import json
import os
from datetime import datetime

OUTPUT_DIR = "output/P04_Progress_Mystery"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    from market_ops.clients.lovart import LovartClient
    from market_ops.clients.lovart import LovartResult
    
    client = LovartClient()
    
    test_prompt = """Create a NEW Facebook ad for P04 Witch merge game. Mobile portrait 9:16, professional game ad quality, 3D cartoon style.

Show evolution progression: Egg → Baby Dragon → Teen Dragon → Legendary Dragon, with magical glow effects connecting each stage. Dark purple mystical background with glowing particles. Castle silhouette in far background.

Emotion: mysterious and enchanting
Hook text: "Can You Reach The End?"

Do NOT add watermarks or realistic photos. Keep art style consistent with mobile game advertising."""
    
    print("\n=== 调试Lovart API ===\n")
    print(f"Models: {client._models}")
    
    print("\n发送请求...")
    result = client.generate_image(test_prompt)
    
    if result.image_urls:
        import requests
        img_url = result.image_urls[0]
        response = requests.get(img_url)
        img_path = f"{OUTPUT_DIR}/debug_test.png"
        with open(img_path, 'wb') as f:
            f.write(response.content)
        print(f"\n✓ 图片已保存: {img_path}")

if __name__ == "__main__":
    main()