"""V4.3 → 视频同事交接脚本

把 V4.3 的生成输出转成视频同事可直接执行的制作文档。
每个变体输出一份 Production Brief + 一份汇总总表。

用法:
    python scripts/export_production_briefs.py

输出:
    output/creative_generation/production_briefs/
        V001_production_brief.md       # 每个变体一份
        V002_production_brief.md
        ...
        zz_production_manifest.json    # 总表（给项目排期用）
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_json(path: Path) -> list[dict] | dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_production_brief(variant: dict, storyboard: dict | None, tasks: list[dict]) -> str:
    """生成一个变体的制作脚本（中文）"""
    vid = variant.get("variant_id", "unknown")
    dim = variant.get("changed_dimension", "unknown")
    new_val = variant.get("new_value", "unknown")
    decision_score = variant.get("decision_score", 0)
    risk_level = variant.get("risk_level", "N/A")
    budget_info = variant.get("budget", {})
    daily_budget = budget_info.get("daily_budget_usd", 0)

    # 维度中文映射
    dim_zh_map = {
        "lighting_temperature": "灯光温度",
        "creature_type": "生物类型",
        "character_pose": "角色姿势",
        "background": "背景",
        "camera": "镜头",
        "hook_type": "钩子类型",
        "lighting": "光照",
        "color": "颜色",
    }
    val_zh_map = {
        "cool": "冷色调", "warm": "暖色调", "neutral": "中性", "golden": "金色",
        "blue": "蓝色", "white": "白色", "orange": "橙色", "purple": "紫色",
        "dragon": "龙", "phoenix": "凤凰", "unicorn": "独角兽", "wolf": "狼",
    }
    dim_zh = dim_zh_map.get(dim, dim)
    val_zh = val_zh_map.get(new_val, new_val)

    # 钩子类型中文映射
    hook_zh_map = {
        "collection": "收藏", "reward": "奖励", "transformation": "变身",
        "fail": "失败", "emotion": "情感", "puzzle": "解谜", "merge": "合成",
    }
    hook_zh = hook_zh_map.get(storyboard.get("hook_type", "collection") if storyboard else "collection", "收藏")

    lines = [
        f"# {vid} - 制作脚本",
        f"## 决策信息",
        f"- **决策分数**: {decision_score}",
        f"- **风险等级**: {risk_level}",
        f"- **改动维度**: {dim_zh} → {val_zh}",
        f"- **每日预算**: ${daily_budget}",
        f"- **钩子类型**: {hook_zh}",
        f"- **总时长**: {storyboard.get('total_duration', 15)}秒" if storyboard else "",
        f"",
    ]

    # 分镜部分
    if storyboard:
        lines.extend([
            f"## 分镜（{storyboard.get('total_duration', 15)}秒，{len(storyboard.get('scenes', []))} 个场景）",
            f"",
        ])
        # 场景类型中文
        scene_type_zh = {
            "hook": "钩子（开头）", "gameplay": "玩法展示", "reward": "奖励时刻",
            "cta": "行动号召", "ending": "结尾",
        }
        # 镜头中文
        camera_zh = {
            "close-up": "特写", "medium": "中景", "wide": "远景", "extreme_close_up": "超特写",
            "low_angle": "仰拍", "top_down": "俯拍", "over_shoulder": "过肩镜头",
            "tilted": "倾斜", "dynamic": "动态", "hero_shot": "英雄镜头",
        }
        # 转场中文
        transition_zh = {
            "cut": "硬切", "fade": "淡入淡出", "zoom": "缩放", "fade_out": "淡出",
            "dissolve": "溶解", "flash": "闪白", "shake": "震动", "soft_fade": "柔淡入淡出",
            "explosion_zoom": "爆炸缩放", "glow_dissolve": "发光溶解", "sparkle_zoom": "闪光缩放",
        }
        # 音效中文
        sound_zh = {
            "强烈音效 / 魔法音效 / 惊喜声": "魔法音效 / 惊喜声 / 短促的上升和弦",
            "轻快背景音乐 / 交互音效": "轻快游戏背景音乐 / 交互音效",
            "胜利音乐 / 金币声 / 升级音效": "金币声 / 升级音效 / 欢快胜利音乐",
            "音乐渐强 / 号召性音效": "音乐渐强 / 轻微叮声 / 号召感音效",
            "品牌音效 / 柔和结尾音乐": "柔和结尾音乐 / 品牌 logo 音效",
        }

        for scene in storyboard.get("scenes", []):
            scene_type_cn = scene_type_zh.get(scene["scene_type"], scene["scene_type"])
            camera_cn = camera_zh.get(scene["camera"], scene["camera"])
            transition_cn = transition_zh.get(scene["transition"], scene["transition"])
            sound_cn = sound_zh.get(scene.get("sound_note", ""), scene.get("sound_note", ""))

            lines.extend([
                f"### 场景 {scene['scene_number']} - {scene_type_cn}（{scene['duration']}秒）",
                f"",
                f"**镜头**: {camera_cn}  |  **转场**: {transition_cn}",
                f"",
                f"**画面描述**: {scene['description']}",
                f"",
                f"**音效**: {sound_cn}",
                f"",
                f"**AI 提示词**:",
                f"```",
                f"{scene['prompt']}",
                f"```",
                f"",
            ])

        lines.append("---\n")

    # 优化版本 Prompt 部分
    lines.extend([
        f"## 提示词风格版本",
        f"",
    ])

    # 风格中文映射
    style_zh = {
        "pixar": "皮克斯 3D 风格", "disney": "迪士尼风格", "dreamworks": "梦工厂风格",
        "semi_realistic": "半写实风格", "chibi": "Q版超萌风格", "anime": "动漫风格",
        "watercolor": "水彩画风格",
    }
    for task in tasks:
        if task.get("variant_id") != vid:
            continue
        style_cn = style_zh.get(task.get('extra', {}).get('style', 'pixar'), '皮克斯风格')
        lines.extend([
            f"### 版本 {task['version']} - {style_cn}",
            f"",
            f"**AI 模型**: {task['model']}",
            f"**分辨率**: {task['width']}×{task['height']}",
            f"**画面比例**: {task['aspect_ratio']}",
            f"**迭代步数**: {task['steps']}  |  **CFG**: {task['cfg_scale']}  |  **采样器**: {task['scheduler']}",
            f"",
            f"**正面提示词**:",
            f"```",
            f"{task['prompt']}",
            f"```",
            f"",
        ])

    lines.append("---\n")
    lines.extend([
        f"## 制作说明",
        f"",
        f"### 路径 A：AI 视频生成（推荐，30分钟/条）",
        f"1. 拿上面 5 个场景的 AI 提示词",
        f"2. 用 {tasks[0]['model'] if tasks else 'Lovart'} 生成每张场景图",
        f"3. 用 Runway / Pika / Kling 把每张图变成 2-3 秒动态",
        f"4. 在 Premiere / After Effects 里按转场顺序串起来，加音效",
        f"5. 在底部 10% 区域加 Facebook 安全的 CTA 按钮",
        f"",
        f"### 路径 B：传统制作（高质量，1天/条）",
        f"1. 把分镜当创意脚本",
        f"2. 用提示词版本的 A/B/C/D 做视觉参考",
        f"3. 用游戏内实际素材替换 AI 场景",
        f"4. 设计 + 剪辑 + 音效",
        f"",
        f"### 质量检查清单",
        f"- [ ] 钩子：前 2 秒必须停住手指让用户停下来看",
        f"- [ ] 钩子类型清晰：收藏类（发现+收集）一目了然",
        f"- [ ] 核心玩法在场景 2-3 展示清楚",
        f"- [ ] 奖励时刻有爽感（场景 3-4）",
        f"- [ ] CTA 清晰可见",
        f"- [ ] 没有违反 Facebook 政策的内容",
        f"- [ ] 品牌一致：P04 项目女巫 + 魔法生物",
        f"- [ ] 开声音时：音乐 + 音效和画面同步",
        f"- [ ] 关声音时：没声音也能看懂",
        f"- [ ] 结尾有品牌 + CTA（1-2 秒）",
        f"",
        f"### Facebook Feed 安全区域提示",
        f"- ✅ 关键内容放在中间 80% 区域",
        f"- ⚠️ 顶部 15% 是头像 / 主页名称位置",
        f"- ⚠️ 底部 15% 是 CTA 按钮 / 广告标签位置",
        f"",
        f"---",
        f"_由 V4.3 创意生成引擎自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
    ])

    return "\n".join(lines)


def main():
    print("=" * 80)
    print("📤 V4.3 → 视频同事交接脚本")
    print("=" * 80)

    out_base = ROOT / "output" / "creative_generation" / "production_briefs"
    out_base.mkdir(parents=True, exist_ok=True)

    # 1. 加载数据
    storyboards = load_json(ROOT / "output" / "creative_generation" / "storyboard.json")
    tasks = load_json(ROOT / "output" / "creative_generation" / "image_tasks.json")
    variants = load_json(ROOT / "output" / "creative_decision" / "portfolio.json")

    print(f"  📖 Storyboards: {len(storyboards)}")
    print(f"  📖 Image Tasks: {len(tasks)}")
    print(f"  📖 Variants: {len(variants)}")

    # 2. 按 variant_id 索引
    sb_by_vid = {}
    for sb in storyboards:
        sb_by_vid[sb["variant_id"]] = sb

    # 3. 生成每个变体的 Production Brief
    manifest = {"generated_at": datetime.now().isoformat(), "variants": []}

    for variant in variants:
        vid = variant["variant_id"]
        sb = sb_by_vid.get(vid)
        variant_tasks = [t for t in tasks if t["variant_id"] == vid]

        if not sb and not variant_tasks:
            continue

        brief = build_production_brief(variant, sb, variant_tasks)

        brief_path = out_base / f"{vid}_production_brief.md"
        with open(brief_path, "w", encoding="utf-8") as f:
            f.write(brief)

        risk = variant.get("risk_level", "N/A")
        score = variant.get("decision_score", 0)
        budget = variant.get("budget", {})
        daily = budget.get("daily_budget_usd", 0)

        manifest["variants"].append({
            "variant_id": vid,
            "file": str(brief_path.name),
            "decision_score": score,
            "risk_level": risk,
            "daily_budget": daily,
            "hook_type": sb.get("hook_type", "collection") if sb else "N/A",
            "scenes": len(sb.get("scenes", [])) if sb else 0,
            "versions": len([t for t in variant_tasks if t["variant_id"] == vid]),
        })

        print(f"  ✅ {vid} - Score {score} - {risk} - ${daily}/day")

    # 4. 生成总表
    manifest_path = out_base / "zz_production_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 4. 打印汇总
    print(f"\n{'='*80}")
    print(f"📦 输出目录: {out_base}")
    print(f"📄 共生成 {len(manifest['variants'])} 份制作脚本")
    print(f"📄 总表: zz_production_manifest.json")
    print(f"\n📋 制作脚本包含:")
    print(f"   • 决策信息（分数 / 风险 / 预算）")
    print(f"   • 分镜（每场景：时长/镜头/描述/转场/音效/AI 提示词）")
    print(f"   • 提示词版本（A/B/C/D 风格，完整提示词）")
    print(f"   • 制作说明（AI 视频 / 传统制作 两条路径）")
    print(f"   • 质量检查清单（钩子/玩法/奖励/CTA 逐项检查）")
    print(f"   • 安全区域提示（Facebook Feed 安全区）")
    print(f"\n🎬 视频同事工作流:")
    print(f"   1. 打开 zz_production_manifest.json 看总表，按分数排优先级")
    print(f"   2. 从优先级最高的变体开始：打开 Vxxx_production_brief.md")
    print(f"   3. 按分镜的 5 个场景一个一个生成")
    print(f"   4. 用图像任务里的提示词生成各版本参考图")
    print(f"   5. 合成视频 + 加声音 + 加 CTA")
    print(f"   6. 跑质量检查清单")

    # 6. 给视频同事的建议
    print(f"\n{'='*80}")
    print(f"💡 给视频同事的建议:")
    print(f"")
    print(f"这条链路是：系统帮你决定 '做什么'（DNA + Portfolio）")
    print(f"                     ↓")
    print(f"            系统帮你生成 '怎么做'（提示词 + 分镜）")
    print(f"                     ↓")
    print(f"            ★ 视频同事负责 '做出来'（制作）")
    print(f"")
    print(f"推荐的 3 条制作路径:")
    print(f"")
    print(f"路径 A - AI 视频（最快，$0~5/条）:")
    print(f"  1. 分镜的 AI 提示词 → Lovart 出图（5张）")
    print(f"  2. 单张图 → Kling/Runway 生成 2-3 秒动态")
    print(f"  3. Premiere 串起来 + 音效 + CTA 按钮")
    print(f"  4. 约 30 分钟出 1 条 15 秒视频")
    print(f"")
    print(f"路径 B - 半 AI 创作（质量高，$10~30/条）:")
    print(f"  1. 分镜当创意脚本，给设计同事看")
    print(f"  2. 用提示词版本的 A/B/C/D 做风格参考")
    print(f"  3. 用游戏内实际素材替换 AI 生成的场景")
    print(f"  4. 设计 + 剪辑 + 音效")
    print(f"  5. 约 1 天出 1 条")
    print(f"")
    print(f"路径 C - 全 AI 批量（量最大，$0.5/条）:")
    print(f"  1. image_tasks.json 直接批量发送 Lovart API")
    print(f"  2. 自动出所有版本图")
    print(f"  3. 用 AI 视频工具批量加动态")
    print(f"  4. 批量投放测试")
    print(f"  5. 适合 Explore 桶的大胆尝试")
    print(f"")
    print(f"优先级建议:")
    modified_variants = [v for v in variants if v.get("changed_dimension") and v.get("new_value")]
    for v in sorted(modified_variants, key=lambda x: -x.get("decision_score", 0))[:3]:
        dim = v.get("changed_dimension", "")
        val = v.get("new_value", "")
        score = v.get("decision_score", 0)
        print(f"  ★ {v['variant_id']} 分数 {score}：{dim} → {val}（最有差异化，推荐先做）")


if __name__ == "__main__":
    main()
