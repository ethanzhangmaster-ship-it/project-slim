"""
P04项目历史视频素材详细分析报告 - 发送至飞书群
基于全部真实数据：905个FB视频、394个因果分析、385个创意模式、154个视觉帧分析
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from market_ops.clients.feishu_bot import FeishuBotClient
from market_ops.config import load_settings

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'output')
P04_DIR = os.path.join(OUTPUT_DIR, 'video_intelligence', 'p04')


def load_json(*paths):
    path = os.path.join(OUTPUT_DIR, *paths)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def build_report():
    # ========== 数据加载 ==========
    recipe = load_json('creatives_cache', '_recipe_P04.json')
    patterns = load_json('creatives_cache', '_patterns_P04.json')
    report_data = load_json('creatives_cache', '_report_P04.json')
    winner_v2 = load_json('video_intelligence', 'p04', 'winner_report_v2.json')
    policy = load_json('video_intelligence', 'p04', 'v3_9', 'policy_report.json')
    causal_v36 = load_json('video_intelligence', 'p04', 'v3_6', 'causal_report.json')
    causal_v38 = load_json('video_intelligence', 'p04', 'v3_8', 'causal_report.json')

    # ========== 基础总量 ==========
    total_creatives = patterns.get('total_analyzed', 385)
    total_fb = winner_v2.get('total_fb', 905)
    total_eagle = winner_v2.get('total_eagle', 615)
    n_videos_policy = policy.get('n_videos', 394)
    overall_spend = winner_v2.get('overall_spend', 68457.55)
    overall_revenue = winner_v2.get('overall_revenue', 34477.96)
    overall_roas = winner_v2.get('overall_roas', 0.5036)
    coverage_pct = winner_v2.get('coverage_pct', 74.3)

    # ========== 色调分布 ==========
    warm = patterns.get('palette_tones', {}).get('warm', 1039)
    cool = patterns.get('palette_tones', {}).get('cool', 790)
    light = patterns.get('palette_tones', {}).get('light', 620)
    dark_val = patterns.get('palette_tones', {}).get('dark', 264)

    # ========== Hook 分布 ==========
    hooks = patterns.get('dominant_hook', [])
    hooks_detail = "\n".join([f"  • {h[0]}: {h[1]}支 ({h[1]/total_creatives*100:.1f}%)" for h in hooks[:5]])

    # ========== 文本覆盖 / UI 元素 ==========
    top_uis = report_data.get('common_ui_elements', [])[:8]
    ui_detail = "\n".join([f"  • {u[0]}: {u[1]}次" for u in top_uis])

    # ========== 样本标题 ==========
    sample_texts = report_data.get('sample_overlay_texts', [])[:6]
    texts_detail = "\n".join([f"  • \"{t}\"" for t in sample_texts])

    # ========== 集群分析 (V2) ==========
    clusters = winner_v2.get('cluster_ranking', [])
    cluster_detail = ""
    for c in clusters:
        nm = c.get('cluster_name', '')
        sp = c.get('total_spend', 0)
        rv = c.get('total_revenue', 0)
        roas = c.get('roas', 0)
        sh = c.get('spend_share', 0)
        fb_c = c.get('fb_count', 0)
        cluster_detail += f"  #{c['rank']} [{nm}] 花费${sp:,.0f} 收入${rv:,.0f} ROAS={roas:.4f} 花费占比{sh:.1f}%（{fb_c}个FB视频）\n"

    # ========== TOP 5 高花费视频 ==========
    top_spend_partial = load_json('video_intelligence', 'p04', 'p4_campaign_summary.json') if os.path.exists(os.path.join(P04_DIR, 'p4_campaign_summary.json')) else {}
    top_spend_text = "(完整花费排名数据在 p4_campaign_summary.csv 中)"

    # ========== 因果分析 V3.6 ROAS 驱动力 ==========
    top_drivers = causal_v36[0].get('impact_quantification', {}).get('top_drivers', []) if causal_v36 else []
    pos_drivers = [d for d in top_drivers if d.get('direction') == 'positive'][:5]
    neg_drivers = [d for d in top_drivers if d.get('direction') == 'negative'][:5]
    pos_line = "\n".join([f"  ✅ +{d['impact']*100:.1f}%  {d['feature']}" for d in pos_drivers])
    neg_line = "\n".join([f"  ❌ {d['impact']*100:.1f}%  {d['feature']}" for d in neg_drivers])

    # ========== V3.8 因果分析策略验证 ==========
    policy_coverage = policy.get('policy_coverage', {}).get('policies', {})
    policy_detail = ""
    for pid, pdata in sorted(policy_coverage.items()):
        rule = pdata.get('rule', '')
        hr_pass = pdata.get('high_roas_pass_rate', 0) * 100
        lr_block = pdata.get('low_roas_block_rate', 0) * 100
        policy_detail += f"  {pid}: 高ROAS通过率{hr_pass:.0f}% / 低ROAS拦截率{lr_block:.0f}%\n    → {rule}\n"

    # ========== V3.9 winning structure ==========
    ws = policy.get('winning_structure', {})
    frame_bp = ws.get('frame_blueprint', [])
    frame_detail = ""
    for fbp in frame_bp:
        t = fbp.get('time', '')
        cat = fbp.get('category', '')
        instr = fbp.get('instruction', '')
        frame_detail += f"  ⏱{t} [{cat}]\n    {instr}\n"

    anti_patterns = ws.get('anti_patterns', [])
    anti_detail = "\n".join([f"  ❌ {a}" for a in anti_patterns[:10]])

    # ========== 视觉配方 V35 (154视频分析) ==========
    high_roas_sat = 0.4869
    low_roas_sat = 0.4359
    high_roas_entropy = 7.8769
    low_roas_entropy = 7.6711

    # ========== 赢家 vs 输家 DNA 差异 ==========
    wl = recipe.get('WINNER_VS_LOSER', {})
    winner_only = wl.get('winner_only_patterns', [])
    loser_only = wl.get('loser_only_patterns', [])
    winner_detail = "\n".join([f"  ✅ {w}" for w in winner_only[:5]])
    loser_detail = "\n".join([f"  ❌ {l}" for l in loser_only[:5]])

    # ========== 4个赢家DNA模板 ==========
    winner_dna_text = """  • Winner 1: 白发女王 + 宝宝龙 + 魔法生物环绕 → collection hook, 收集200+生物
  • Winner 2: 女巫 + 浮动城堡合并进度 → collection hook, 城堡升级, 暗黑奇幻
  • Winner 3: 女巫 + 魔法植物发光培育 → collection hook, 花园生长, 月光森林
  • Winner 4: 可爱女巫 + 魔法蛋孵化 → collection hook, 孵蛋, 200+生物"""

    # ========== 禁止方向 ==========
    forbidden = recipe.get('PROMPT_COMPILER_RULES', {}).get('forbidden_directions', [])
    forbidden_detail = "\n".join([f"  🚫 {f}" for f in forbidden])

    # ========== 构建完整报告 ==========
    report_text = f"""**📊 P04 Witch 项目·视频素材详细分析报告**
**数据日期：** 截至 2026-07-09
**数据规模：** {total_fb}个FB视频 | {total_eagle}个Eagle素材 | {n_videos_policy}个因果分析 | {total_creatives}个创意模式 | 154个视觉帧分析

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**一、整体表现概况**

总花费：${overall_spend:,.0f}
总收入：${overall_revenue:,.0f}
整体 ROAS：{overall_roas:.4f}
创意-视频映射覆盖率：{coverage_pct:.1f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**二、创意集群分析（6大聚类）**

基于{total_fb}个FB视频的视觉聚类分析：

{cluster_detail}

→ 核心发现：「角色战斗展示 + 宠物展示」类视频占据 43.9% 花费且 ROAS 最高 (0.5748)
→ 「角色展示 + 解说 + 场景展示」类视频花费占比 11.9% 但 ROAS 仅 0.4229

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**三、HOOK 分布分析（基于{total_creatives}个创意）**

{hooks_detail}

→ 赢家独有特征：
{winner_detail}

→ 输家独有特征：
{loser_detail}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**四、因果分析：影响ROAS的关键特征（V3.6，394个视频）**

🎯 ROAS正向驱动（每提升1个标准差）：
{pos_line}

🎯 ROAS负向驱动：
{neg_line}

→ 解读：第一帧对比度和饱和度是最重要的ROAS驱动因素
→ 第一帧边缘密度过高（画面杂乱）是最大的扣分项
→ 中间段（3-6s）的颜色丰富度和中心聚焦也很关键

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**五、策略验证：高ROAS vs 低ROAS 对比（V3.8，394个视频）**

{policy_detail}

→ 整体：高ROAS视频平均符合 11.5% 的策略规则集，低ROAS视频被拦截率 97.4%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**六、必胜视频结构蓝图（V3.9）**

{frame_detail}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**七、视觉配方对比（154个视频分析）**

| 特征 | 高ROAS均值 | 低ROAS均值 | 差异 |
|------|-----------|-----------|------|
| 饱和度 | {high_roas_sat:.4f} | {low_roas_sat:.4f} | +{((high_roas_sat/low_roas_sat)-1)*100:.1f}% |
| 主色占比 | 0.0960 | 0.0594 | +61.6% |
| 色彩丰富度 | {high_roas_entropy:.4f} | {low_roas_entropy:.4f} | +{((high_roas_entropy/low_roas_entropy)-1)*100:.1f}% |
| 文字密度 | 0.0134 | 0.0210 | -36.2% |

→ 结论：高饱和度、强主色调、高色彩多样性、少文字

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**八、色调与UI元素分析**

暖色:冷色 = {warm}:{cool}（暖色主导）
亮色:暗色 = {light}:{dark_val}

最常见UI元素：
{ui_detail}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**九、赢家DNA模板**

{winner_dna_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**十、禁止方向**

{forbidden_detail}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**十一、样本文案参考**

{texts_detail}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**十二、制作建议总结**

1. 方向A（ROAS最高）：角色战斗展示 - 女巫+宠物高对比入场→展示战斗/进化→奖励画面
2. 方向B（最大量级）：收集+进度展示 - 合并链条完整展示→箭头指引→进化完成
3. 方向C（高点击率）：好奇心悬念 - 神秘物品/蛋→揭开→惊喜

最关键的3个制作规则：
  P1 - 第一帧必须有主体在画面中心40%（ROAS差异+0.074）
  P5 - 前3秒减少文字覆盖（ROAS差异+0.054）  
  P2 - 第一帧对比度≥0.15（ROAS差异+0.047）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

数据来源：
 • Meta Ads: {total_fb}个FB视频
 • Eagle素材库: {total_eagle}个素材
 • Creative Intelligence V3.5: {total_creatives}个创意分析
 • Video Intelligence V3.9: {n_videos_policy}个视频因果分析
 • DuckDB creative_performance: 赢家输家差异分析"""

    return report_text, n_videos_policy


def main():
    settings = load_settings()
    webhook = settings.feishu_market_webhook or settings.feishu_bot_webhook

    msg, n_videos = build_report()

    card_content = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "📊 P04 Witch 历史视频素材详细分析报告"},
            "template": "indigo"
        },
        "elements": [
            {
                "tag": "markdown",
                "content": msg
            },
            {
                "tag": "hr"
            },
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": f"报告自动生成时间: 2026-07-09 | 数据来源: Meta Ads + Video Intelligence V3.9 | 分析样本: {n_videos}个视频"
                    }
                ]
            }
        ]
    }

    client = FeishuBotClient(webhook)
    result = client.send_card(card_content)
    print(f"发送成功: {result}")


if __name__ == "__main__":
    main()
