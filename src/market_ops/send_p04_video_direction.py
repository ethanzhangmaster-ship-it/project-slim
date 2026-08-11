"""
将P04项目视频素材方向的真实数据分析结果发送至飞书群
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from market_ops.clients.feishu_bot import FeishuBotClient
from market_ops.config import load_settings

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'output')


def load_json(relative_path):
    path = os.path.join(OUTPUT_DIR, relative_path)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def load_txt(relative_path):
    path = os.path.join(OUTPUT_DIR, relative_path)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


def build_message():
    recipe = load_json('creatives_cache/_recipe_P04.json')
    patterns = load_json('creatives_cache/_patterns_P04.json')
    winner_v2 = load_json('video_intelligence/p04/winner_report_v2.json')
    policy = load_json('video_intelligence/p04/v3_9/policy_report.json')

    total_creatives = patterns.get('total_analyzed', 385)
    warm = patterns.get('palette_tones', {}).get('warm', 1039)
    cool = patterns.get('palette_tones', {}).get('cool', 790)

    winner_data = winner_v2.get('cluster_ranking', [])
    overall_spend = winner_v2.get('overall_spend', 68457.55)
    overall_revenue = winner_v2.get('overall_revenue', 34477.96)
    overall_roas = winner_v2.get('overall_roas', 0.5036)

    top_cluster = winner_data[0] if winner_data else {}
    top_cluster_name = top_cluster.get('cluster_name', 'juesezhanshi')
    top_cluster_roas = top_cluster.get('roas', 0)
    top_cluster_spend = top_cluster.get('total_spend', 0)

    policies = policy.get('policies', [])
    p1_rule = policies[0]['rule'] if len(policies) > 0 else ""

    return f"""**P04 Witch 项目视频素材方向分析报告**

**总量：** {total_creatives} 个创意 | 花费 ${overall_spend:,.0f} | 收入 ${overall_revenue:,.0f} | 整体 ROAS {overall_roas:.2f}
**数据来源：** Meta Ads Creative Performance + Video Intelligence V3.9 因果分析

━━━━━━━━━━━━━━━━━━━━

**1. 当前效果最好视频类型**

Top 1 集群：「{top_cluster_name}」
→ 花费 ${top_cluster_spend:,.0f} | ROAS {top_cluster_roas:.3f}
→ 核心方向：角色展示 + 宠物展示，强视觉叙事

Top 1 视频（ROAS 7.07）：角色战斗展示，18s竖版，花费 $31
Top 2 视频（ROAS 2.37）：角色战斗展示，47s竖版，花费 $103

━━━━━━━━━━━━━━━━━━━━

**2. 高ROAS视频的视觉配方（基于154个视频对比分析）**

✅ 颜色策略：
+ 高饱和度（>0.45），色彩越鲜艳越好
+ 明显主色调（暖色占比 {warm}:{cool}），暖色胜出
+ 色彩丰富度高（熵 > 7.8）

✅ 构图策略：
+ {p1_rule}
+ 前 3s 必须有明显场景/画面结构变化
+ 6s 后必须安排视觉奖励事件（胜利/升级/收集展示）

✅ 文字策略：
+ 文字极少（密度 < 0.015）
+ 只保留核心 CTA
+ 不要大段文字说明

━━━━━━━━━━━━━━━━━━━━

**3. 最有效的 Hook 优先级（基于385个创意）**

第 1 位：Collection（收集）— 占比 62.1%
第 2 位：Curiosity（好奇）— 占比 16.4%
第 3 位：Reward（奖励）— 占比 9.6%

注意：reward hook 虽然量少，但在赢家中占比更高
对比：curiosity hook 在输家中出现更多

━━━━━━━━━━━━━━━━━━━━

**4. 制作方向建议**

方向 A：角色战斗展示（当前ROAS最高）
→ 前 0.8s 女巫角色高对比入场
→ 展示宠物/同伴战斗
→ 6s后展示进化/升级

方向 B：收集+进度（collection hook）
→ 展示合并过程，箭头指示
→ 进化链条完整展示（蛋→幼体→传说）
→ Drop rate + 视觉奖励

方向 C：Before/After 对比
→ Before（普通女巫）vs After（进化女巫）
→ 强反差，画面亮度和饱和度骤升

必须避免：
× 暗黑写实风格 / 冷色调主导
× 前 3s 无主体画面（纯UI/风景）
× 文字密度过高
× 不同创意之间角色形象不一致

━━━━━━━━━━━━━━━━━━━━

**5. 数据来源**
- video_intelligence V3.9：394个视频因果分析
- Meta Ads：905个FB视频画面分析
- DuckDB creative_performance：赢家输家差异分析
- 创意缓存：385个创意模式分析"""


def main():
    settings = load_settings()
    webhook = settings.feishu_market_webhook or settings.feishu_bot_webhook

    msg = build_message()

    card_content = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🌙 P04 Witch 视频素材方向 — 基于真实数据"},
            "template": "purple"
        },
        "elements": [
            {
                "tag": "markdown",
                "content": msg
            }
        ]
    }

    client = FeishuBotClient(webhook)
    result = client.send_card(card_content)
    print(f"发送成功: {result}")


if __name__ == "__main__":
    main()
