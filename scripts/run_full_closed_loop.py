"""端到端真实闭环: Prompt → 生成图片 → 上传Facebook → 创建广告

完整链路:
  1. 读取 pipeline_prompts.md 中的 5 个 prompt
  2. 使用 Lovart ImageGenerator 生成图片
  3. 使用 FacebookPublisher 上传图片到 Facebook
  4. 创建广告创意 + 广告 (默认 PAUSED 状态)
  5. 输出执行报告

用法:
  python scripts/run_full_closed_loop.py
  python scripts/run_full_closed_loop.py --auto-activate  # 创建后自动激活
  python scripts/run_full_closed_loop.py --dry-run  # 仅生成图片, 不上传 FB
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Load .env
ROOT = Path(__file__).parent.parent
_ENV_PATH = ROOT / ".env"


def load_env():
    if _ENV_PATH.exists():
        with open(_ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ[key.strip()] = val.strip()
    sys.path.insert(0, str(ROOT / "src"))


def parse_prompts() -> list[dict]:
    """从 pipeline_prompts.md 提取 prompt 文本."""
    prompt_path = ROOT / "output" / "pipeline_prompts.md"
    text = prompt_path.read_text(encoding="utf-8")

    # 提取 Variant prompt 块
    variants = re.findall(
        r"### Variant (\d+)\n```\n(.*?)\n```",
        text, re.DOTALL,
    )

    prompts = []
    for vnum, prompt_text in variants:
        prompts.append({
            "variant": int(vnum),
            "prompt_text": prompt_text.strip(),
            "hook": "gameplay",
            "reward": "satisfying",
            "emotion": "curious",
        })
    return prompts


def generate_images(prompts: list[dict], dry_run: bool = False) -> list[dict]:
    """使用 ImageGenerator / Lovart 生成图片."""
    from market_ops.clients.lovart import LovartClient, download_image

    run_id = datetime.now(timezone.utc).strftime("closed_loop_%Y%m%d_%H%M%S")
    output_dir = ROOT / "output" / "creative_growth_loop" / "images" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Step 2: 图片生成 (Lovart)")
    print(f"{'='*60}")
    print(f"  Run ID: {run_id}")
    print(f"  Output: {output_dir}")

    if dry_run:
        print("\n  [DRY RUN] 跳过图片生成, 使用占位符")
        return []

    # 逐个生成 (Lovart 需要轮询, 逐个生成更稳定)
    generated = []
    client = LovartClient()

    for i, p in enumerate(prompts):
        prompt_text = p["prompt_text"]
        print(f"\n  [{i+1}/{len(prompts)}] 生成: {prompt_text[:80]}...")

        try:
            result = client.generate_image(prompt_text)
            if result.status == "done" and result.image_urls:
                print(f"    ✅ 成功 ({result.elapsed_sec:.1f}s), {len(result.image_urls)} 张图")
                for j, url in enumerate(result.image_urls):
                    fname = f"variant_{p['variant']:02d}_{j:02d}.png"
                    fpath = output_dir / fname
                    try:
                        download_image(url, fpath)
                        generated.append({
                            "variant": p["variant"],
                            "file_path": str(fpath),
                            "prompt": prompt_text,
                            "model": "lovart",
                            "url": url,
                        })
                        print(f"    📥 下载: {fname}")
                    except Exception as e:
                        print(f"    ❌ 下载失败: {e}")
            else:
                print(f"    ❌ 生成失败: status={result.status}")
                if result.assistant_text:
                    print(f"       {result.assistant_text[:200]}")
        except Exception as e:
            print(f"    ❌ 异常: {e}")

    # 保存 manifest
    manifest = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(generated),
        "images": generated,
    }
    with open(output_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n  生成完成: {len(generated)}/{len(prompts)} 个 prompt 成功")
    return generated


def publish_to_facebook(images: list[dict], auto_activate: bool = False, dry_run: bool = False):
    """上传图片到 Facebook, 创建广告创意和广告."""
    # 需要手动导入 (目录名含数字 14_publish)
    import sys as _sys
    _publish_dir = str(ROOT / "src" / "market_ops" / "creative_growth_loop" / "14_publish")
    _sys.path.insert(0, _publish_dir)
    from facebook_publisher import FacebookPublisher

    print(f"\n{'='*60}")
    print(f"  Step 3: Facebook 发布 (上传 + 创意 + 广告)")
    print(f"{'='*60}")

    if dry_run or not images:
        if not images:
            print("  ⚠️  无图片可发布")
        else:
            print(f"  [DRY RUN] 跳过 Facebook 发布, 已生成 {len(images)} 张图片")
        return None

    token = os.getenv("META_ACCESS_TOKEN", "")
    # 新 Token 用不同的 ad account / adset (APP_INSTALLS campaign)
    ad_account_id = os.getenv("META_AD_ACCOUNT_ID", "")
    adset_id = os.getenv("META_ADSET_ID_APP_INSTALLS") or os.getenv("CLOSED_LOOP_ADSET_ID", "")
    store_url = os.getenv("META_STORE_URL", "https://apps.apple.com/app/id000000000")

    # 读取 page_id (从 me/accounts 动态获取)
    import requests as _req
    page_id = os.getenv("CLOSED_LOOP_PAGE_ID", "")
    if not page_id:
        r_pg = _req.get(
            f"https://graph.facebook.com/{os.getenv('META_API_VERSION','v19.0')}/me/accounts",
            params={"access_token": token, "fields": "id", "limit": 1}
        )
        page_id = r_pg.json().get("data", [{}])[0].get("id", "864287563441749")

    if not token or not ad_account_id:
        print("  ❌ 缺少 Facebook 凭证")
        return None

    print(f"  Ad Account: {ad_account_id}")
    print(f"  Page ID: {page_id}")
    print(f"  Adset ID: {adset_id}")
    print(f"  Store URL: {store_url}")
    print(f"  Images: {len(images)}")

    publisher = FacebookPublisher(
        access_token=token,
        ad_account_id=ad_account_id,
        api_version=os.getenv("META_API_VERSION", "v19.0"),
        page_id=page_id,
    )

    # 读取 pipeline_directives 获取 winner 信息
    directives_path = ROOT / "output" / "pipeline_directives.json"
    if directives_path.exists():
        directives = json.loads(directives_path.read_text(encoding="utf-8"))
    else:
        directives = {}

    # 构建 headlines 和 primary_texts
    headlines = []
    for img in images:
        winners = directives.get("directives", {})
        game_w = winners.get("game", {}).get("target", "P04 Witch")
        tone_w = winners.get("color_tone", {}).get("target", "cool")
        layout_w = winners.get("layout", {}).get("target", "top_bottom")
        headlines.append(f"{game_w} - {tone_w} {layout_w}")

    primary_texts = [
        "Can you solve this? 🔮",
        "Merge & conquer! Try now 👇",
        "The most satisfying puzzle game!",
        "Test your skills - can you beat it?",
        "Addictive puzzle fun awaits!",
    ]

    run_id = datetime.now().strftime("closed_loop_%Y%m%d_%H%M%S")
    ad_names = [f"AI_{run_id}_{img['variant']:02d}" for img in images]

    # 收集图片路径
    image_paths = []
    for img in images:
        p = Path(img["file_path"])
        if p.exists():
            image_paths.append(str(p))

    if not image_paths:
        print("  ❌ 找不到图片文件")
        return None

    print(f"\n  📤 上传 {len(image_paths)} 张图片到 Facebook...")
    image_hashes = publisher.upload_images(image_paths)
    print(f"  ✅ 上传成功: {len(image_hashes)}/{len(image_paths)} 张")

    if not image_hashes:
        print("  ❌ 上传全部失败")
        return None

    print(f"\n  🎨 创建广告创意...")
    creative_ids = publisher.create_ad_creatives(
        image_hashes=image_hashes,
        headlines=headlines[:len(image_hashes)],
        primary_texts=primary_texts[:len(image_hashes)],
        app_link=store_url,
    )
    print(f"  ✅ 创意创建: {len(creative_ids)}/{len(image_hashes)} 个")

    if not creative_ids:
        print("  ❌ 创意创建全部失败")
        return None

    print(f"\n  📢 创建广告 (adset={adset_id})...")
    status = "ACTIVE" if auto_activate else "PAUSED"
    ad_ids = publisher.create_ads(
        creative_ids=creative_ids,
        adset_id=adset_id,
        names=ad_names[:len(creative_ids)],
        status=status,
    )
    print(f"  ✅ 广告创建: {len(ad_ids)}/{len(creative_ids)} 个, 状态={status}")

    # 汇总结果
    result = {
        "run_id": run_id,
        "ad_account_id": ad_account_id,
        "adset_id": adset_id,
        "status": status,
        "image_hashes": image_hashes,
        "creative_ids": creative_ids,
        "ad_ids": ad_ids,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }

    result_path = ROOT / "output" / "closed_loop" / "publish_results" / f"publish_{run_id}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n  📋 发布结果: {result_path}")
    return result


def main():
    parser = argparse.ArgumentParser(description="端到端真实闭环: Prompt → 图片 → FB 发布")
    parser.add_argument("--auto-activate", action="store_true", help="创建广告后自动激活")
    parser.add_argument("--dry-run", action="store_true", help="仅生成图片, 不上传 Facebook")
    parser.add_argument("--generate-only", action="store_true", help="仅生成图片, 不发布")
    args = parser.parse_args()

    load_env()

    print("=" * 60)
    print("  端到端真实闭环")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # Step 1: 解析 prompts
    print(f"\n{'='*60}")
    print(f"  Step 1: 读取 Prompts")
    print(f"{'='*60}")
    prompts = parse_prompts()
    print(f"  {len(prompts)} 个 prompt:")
    for p in prompts:
        print(f"    Variant {p['variant']}: {p['prompt_text'][:80]}...")

    # Step 2: 生成图片
    images = generate_images(prompts, dry_run=args.dry_run)

    # Step 3: 发布到 Facebook
    if not args.generate_only:
        result = publish_to_facebook(
            images,
            auto_activate=args.auto_activate,
            dry_run=args.dry_run,
        )
    else:
        result = None
        print(f"\n  [--generate-only] 跳过 Facebook 发布")

    # 输出汇总
    print(f"\n{'='*60}")
    print(f"  闭环执行完成")
    print(f"{'='*60}")
    print(f"  Prompts: {len(prompts)}")
    print(f"  图片生成: {len(images)}")
    if result:
        print(f"  上传: {len(result['image_hashes'])} 张")
        print(f"  创意: {len(result['creative_ids'])} 个")
        print(f"  广告: {len(result['ad_ids'])} 个, 状态={result['status']}")
    print(f"  结果目录: output/creative_growth_loop/images/")

    return 0 if (images or args.dry_run) else 1


if __name__ == "__main__":
    sys.exit(main())