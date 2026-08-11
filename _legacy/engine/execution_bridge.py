"""Execution Bridge — Direction Card → AE / AI 可执行制作脚本。

桥接分析层与制作层。输入是 Direction Card（创意方向），
输出是 AE 可以直接执行的 Shot-by-Shot 脚本 + AI 生图 Prompt + 动态约束。

转换逻辑：
  Direction Card (what) → Execution Script (how)

核心输出：
  TITLE: 视频制作脚本（按秒分段）
  0-1s, 1-3s, 3-8s, 8-15s, 15-20s
  AE TASK LIST: 具体动画指令
  AI TASK LIST: 生成素材的 Prompt
  CONSTRAINTS: 制作红线（不许做什么）
"""
from __future__ import annotations
from typing import Any
from datetime import datetime


# ═══════════════════════════════════════════════════════════
# Archetype → Shot Template Map
# ═══════════════════════════════════════════════════════════

SHOT_TEMPLATES = {

    "Character Reveal": {
        "duration": 31,
        "shots": [
            ("0-1s", "SHOCK REVEAL — 角色正面特写，占画面 70%+，背景模糊",
             "Camera: 固定机位，角色直视镜头，背景高斯模糊",
             "AE: 角色入场动画（缩放 120%→100%，0.3s），景深模糊过渡",
             "AI: cinematic portrait of a magical character, glowing eyes, dark fantasy style, 9:16, intense gaze"),
            ("1-3s", "角色转头/微笑/施展小魔法 → 画面切到游戏场景",
             "Camera: 快速转场（0.1s wipe），角色切为游戏中的角色",
             "AE: 角色→游戏场景 morph 过渡，粒子散开效果",
             "AI: same character in game world, casting spell, magical particles, vibrant colors"),
            ("3-8s", "角色展示核心能力：战斗/收集/建造片段",
             "Camera: 中景，展示角色在游戏中的动作",
             "AE: 角色技能动画（3-step combo），伤害数字弹出，血条动画",
             "AI: character performing special ability in game, enemies, effects, action pose"),
            ("8-15s", "角色升级/进化/获得新外观 — 进度展示",
             "Camera: 前后对比 split screen",
             "AE: 角色进化动画（渐变过渡），等级数字滚动，特效粒子",
             "AI: character evolution sequence, before and after, level up glow"),
            ("15-20s", "角色 Collection 展示 + CTA按钮",
             "Camera: 多角色画廊滚动展示",
             "AE: 画廊滚动动画（auto-scroll），角色卡片弹出，CTA按钮脉冲",
             "AI: character collection gallery, multiple heroes,稀有度标签，'Download Now' overlay"),
        ],
        "ae_tasks": [
            "角色入场动画：缩放 120%→100% + 淡入（0.3s）",
            "角色→游戏场景 Morph 过渡（0.5s wipe + 粒子）",
            "技能动画：3-step combo sequence",
            "数字弹出动画：伤害数字（size 40→60 → fade）",
            "进化过渡：渐变 + 光效 + 粒子爆发",
            "画廊滚动：auto-scroll + 卡片 3D 翻转",
            "CTA 脉冲：按钮 105% → 100% loop, 1.5s周期",
        ],
        "ai_tasks": [
            "角色立绘：9:16, 全身, 魔法风格, 发光眼睛, 暗黑奇幻",
            "角色技能展示：9:16, 战斗中, 技能特效, 粒子",
            "角色进化对比：split screen before/after, 光效",
        ],
    },

    "Narrative": {
        "duration": 41,
        "shots": [
            ("0-1s", "CURIOSITY HOOK — 角色面临困境/神秘画面，不加说明",
             "Camera: 特写 + 轻微晃动，制造紧张感",
             "AE: 画面震动（0.1s周期），暗角遮罩渐显",
             "AI: hero in trouble, mysterious environment, dramatic lighting, cinematic 9:16"),
            ("1-3s", "展开困境上下文：角色在做什么，遇到了什么",
             "Camera: 中景推近，展示环境",
             "AE: 镜头推近（slow zoom in 100%→120%），环境元素渐显",
             "AI: wide shot of hero in dangerous environment, showing the scale of challenge"),
            ("3-8s", "角色尝试解决问题 — 使用游戏机制",
             "Camera: 跟随角色动作，展示交互",
             "AE: 点击/滑动指示器动画，UI元素按步骤高亮",
             "AI: hero interacting with game objects, solving puzzle, hands-on gameplay"),
            ("8-15s", "出现转折/意外 — 更大挑战出现",
             "Camera: 镜头拉远揭示全局",
             "AE: 遮罩展开（reveal transition），新元素从画面外飞入",
             "AI: twist reveal, bigger enemy, unexpected challenge, dramatic reveal"),
            ("15-25s", "角色使用高级能力应对挑战 — 高光时刻",
             "Camera: 慢动作 + 多角度快速剪辑",
             "AE: 慢动作效果（speed ramp 100%→30%→100%），屏幕震动",
             "AI: epic moment, hero using ultimate power, cinematic slow motion"),
            ("25-30s", "Cliffhanger — 故事未结束，引导点击",
             "Camera: 定格在关键时刻，画面冻结",
             "AE: 画面冻结效果（motion blur fade），'继续？'文字渐入",
             "AI: cliffhanger frame, hero in mid-action, freeze frame dramatic"),
        ],
        "ae_tasks": [
            "画面震动：0.1s 周期, X轴偏移 3px",
            "Slow zoom: 100%→120%, 15s duration, ease-out",
            "点击指示器：手指图标 淡入→脉冲→淡出（2s cycle）",
            "UI 高亮：目标元素 发光描边 + 周围暗化",
            "Reveal 遮罩展开：从上到下 0.5s",
            "Speed ramp: 100%→30%→100%, 关键帧插值",
            "画面冻结：motion blur 渐入, 冻结帧持续 1s",
        ],
        "ai_tasks": [
            "角色困境场景：9:16, 黑暗奇幻, 戏剧光, 电影感",
            "游戏交互画面：展示角色操作游戏元素",
            "转折画面：reveal moment, 新敌人/挑战出现",
        ],
    },

    "Gameplay Loop": {
        "duration": 30,
        "shots": [
            ("0-1s", "RESULT FIRST — 直接展示最爽的游戏瞬间（金币/升级/胜利）",
             "Camera: 满屏游戏画面，无 UI 干扰",
             "AE: 数字飞入动画（金币 +100），分数滚动",
             "AI: gameplay screenshot, satisfying moment, rewards popping, vibrant UI"),
            ("1-3s", "倒带回放：这个结果是怎么达成的",
             "Camera: 快速回放（2x speed）",
             "AE: 回放效果（反向播放指示器），时间倒流粒子",
             "AI: gameplay recording, player action, tapping and swiping"),
            ("3-10s", "详细展示核心玩法循环",
             "Camera: 正常速度，展示操作 + 反馈",
             "AE: 点击高亮 circle，拖拽路径线，反馈动画（正确/错误）",
             "AI: core gameplay loop demonstration, step by step, clear UI"),
            ("10-18s", "展示更多玩法变体/更高难度",
             "Camera: 快速切换不同关卡",
             "AE: 关卡切换转场（卡片翻转），难度标签渐显",
             "AI: multiple game levels, increasing difficulty, new mechanics"),
            ("18-22s", "收集/成就/进度展示",
             "Camera: 进度条动画",
             "AE: 进度条填充动画，成就徽章弹出序列",
             "AI: progress screen, achievements, collection completion"),
            ("22-25s", "CTA — '你现在就能做到'",
             "Camera: 回到结果画面",
             "AE: 'Play Now' 按钮脉冲，社交证明（rating stars）渐入",
             "AI: final screen with download button, social proof, ratings"),
        ],
        "ae_tasks": [
            "数字飞入：+100 从画面外飞入 → 缩放 150%→100% → 消失（1.2s）",
            "分数滚动：数字逐位翻转动画",
            "回放效果：反向播放指示器 + 时间粒子",
            "点击高亮：圆形脉冲 0→30px, 透明度 100%→0%",
            "拖拽路径线：追踪 touch 路径, 虚线动画",
            "关卡切换：卡片 3D 翻转 0.6s",
            "进度条填充：从左到右, ease-out, 1.5s",
            "成就徽章：逐个弹入, 缩放 0%→120%→100%, 间隔 0.3s",
        ],
        "ai_tasks": [
            "游戏爽点截图：金币爆炸, 升级画面, 胜利界面",
            "玩法展示序列：step-by-step 操作指南",
            "关卡多样性展示：不同难度关卡预览",
        ],
    },

    "Hook Opener": {
        "duration": 20,
        "shots": [
            ("0-1s", "SHOCK FRAME — 最意想不到的画面，必须 stop scroll",
             "Camera: 固定，画面 100% 填充",
             "AE: 无，原生画面即可",
             "AI: shocking/mysterious image, something unexpected, high contrast, 9:16"),
            ("1-3s", "快速解谜：刚才看到的是什么？",
             "Camera: 快速拉远揭示上下文",
             "AE: 画面展开（expand reveal 0.3s），标注元素出现",
             "AI: wider view revealing context of the shocking image"),
            ("3-8s", "游戏玩法速览 — 最精华的 5 秒",
             "Camera: 高节奏剪辑，2-3 个画面各 1.5s",
             "AE: 快速转场（zoom blur transition），速度线",
             "AI: fast-paced gameplay montage, multiple scenes"),
            ("8-12s", "社交证明/为什么这么多人玩",
             "Camera: 用户好评/数据展示",
             "AE: 好评卡片逐个飞入, 数字统计滚动",
             "AI: review cards, player count, rating display"),
            ("12-15s", "CTA — 悬念延续",
             "Camera: 回到 hook 画面，但这次有上下文",
             "AE: hook 画面重新出现（已理解的版本），CTA 按钮渐显",
             "AI: callback to hook image, now with context, download button"),
        ],
        "ae_tasks": [
            "画面展开：从中心向四周展开, 0.3s",
            "Zoom blur transition：缩放 100%→140% + 模糊 → 切下一画面",
            "好评卡飞入：从画面底部弹入, 间隔 0.4s",
            "数字滚动：玩家数量数字翻转动画",
            "CTA 按钮：渐显 + 脉冲, 1.5s cycle",
        ],
        "ai_tasks": [
            "Hook 画面：震撼/意外/美丽的单帧, 9:16",
            "玩法蒙太奇：快速切换多个游戏画面",
            "社交证明：好评卡片设计",
        ],
    },

    "Text Scroll": {
        "duration": 35,
        "shots": [
            ("0-1s", "PROBLEM HEADLINE — 大字标题直击痛点",
             "Camera: 纯文字，背景虚化或纯色",
             "AE: 文字从中心放大弹出（120%→100%），停留 2s",
             "AI: bold text on clean background, 'Stuck on Level 15?', minimalist"),
            ("1-3s", "问题场景展示 — 用户现在的状态",
             "Camera: 展示问题相关的游戏画面",
             "AE: 问题相关 UI 高亮（红色闪烁），暗淡滤镜",
             "AI: gameplay screenshot showing the problem state"),
            ("3-10s", "解决方案 — 玩法展示",
             "Camera: 展示如何解决上述问题",
             "AE: 分步指示器（Step 1/2/3），操作路径动画",
             "AI: solution demonstration, step by step gameplay"),
            ("10-18s", "更多好处展示 — bullet list",
             "Camera: 文字 + 对应画面交替",
             "AE: 文字滑动入（从右到左），对应画面渐显",
             "AI: benefit showcase, text overlay on gameplay"),
            ("18-25s", "结果对比 — before vs after",
             "Camera: 左右分屏",
             "AE: 分屏过渡（wipe 从中间展开），'之前'暗淡 '之后'鲜艳",
             "AI: before and after comparison, dramatic improvement"),
            ("25-30s", "CTA — 立即解决",
             "Camera: 回到 headline 但加上了 CTA",
             "AE: CTA 按钮渐显，限时标签（'限时 50% OFF'）闪烁",
             "AI: final CTA screen with download button and urgency"),
        ],
        "ae_tasks": [
            "标题弹出：缩放 120%→100%, 0.3s, Bounce easing",
            "UI 高亮：问题元素红色闪烁 0.5s cycle",
            "暗淡滤镜：60% 透明度黑色覆盖层",
            "Step 指示器：Step X 文字 + 进度点",
            "文字滑动：从右边缘滑入, ease-out 0.5s",
            "分屏过渡：wipe 从中间向两边, 0.8s",
            "闪烁标签：透明度 100%→30%→100%, 0.3s cycle",
        ],
        "ai_tasks": [
            "痛点标题设计：大字, 高对比度, 简洁背景",
            "问题状态截图：展示用户困境",
            "解决方案截图：展示如何解决问题",
            "Before/After 对比图",
        ],
    },

    # ── 默认 fallback ──
    "default": {
        "duration": 30,
        "shots": [
            ("0-1s", "HOOK — 吸引注意力的画面",
             "Camera: 固定，满屏",
             "AE: 简单入场动画",
             "AI: eye-catching mobile game ad frame, 9:16"),
            ("1-3s", "上下文展示",
             "Camera: 展示游戏类型",
             "AE: 过渡动画",
             "AI: gameplay context"),
            ("3-8s", "核心玩法展示",
             "Camera: 正常游戏画面",
             "AE: UI 指示器",
             "AI: core gameplay loop"),
            ("8-15s", "更多内容展示",
             "Camera: 多画面切换",
             "AE: 转场动画",
             "AI: more game features"),
            ("15-20s", "CTA",
             "Camera: 下载按钮",
             "AE: 按钮脉冲动画",
             "AI: download screen"),
        ],
        "ae_tasks": [
            "入场动画：淡入 0.5s",
            "过渡：cross dissolve 0.3s",
            "CTA 按钮：脉冲 105%→100% loop",
        ],
        "ai_tasks": [
            "游戏广告画面：9:16, mobile game style",
        ],
    },
}


# ═══════════════════════════════════════════════════════════
# Main Bridge Function
# ═══════════════════════════════════════════════════════════

def card_to_script(card: dict) -> dict:
    """转换 Direction Card → 可执行制作脚本。

    Args:
        card: Direction Card（来自 direction_engine.generate_direction_card
              或 pattern_lock.generate_locked_card）

    Returns:
        execution_script
    """
    arch = card.get("archetype", "default")
    template = SHOT_TEMPLATES.get(arch, SHOT_TEMPLATES["default"])
    hook_info = card.get("hook_direction", {})
    trigger_info = card.get("cognitive_trigger", {})
    anti = card.get("anti_patterns", [])
    perf = card.get("expected_performance", {})
    variant_style = card.get("variant_styling", {})

    # ── Apply variant-specific AI prompt suffix ──
    ai_suffix = variant_style.get("ai_prompt_suffix", "")
    variant_name = variant_style.get("style", "")

    # ── Build shot-by-shot script ──
    script = []
    for timecode, visual, camera, ae_instr, ai_prompt in template["shots"]:
        # Append variant style to AI prompt if available
        full_ai = f"{ai_prompt} {ai_suffix}".strip() if ai_suffix else ai_prompt
        script.append({
            "timecode": timecode,
            "visual_direction": visual,
            "camera_movement": camera,
            "ae_instruction": ae_instr,
            "ai_generation_prompt": full_ai,
        })

    # ── Assemble AE task list ──
    ae_tasks = template.get("ae_tasks", [])
    if hook_info.get("hook_type") == "shock reveal":
        ae_tasks.insert(0, "⭐ PRIORITY: Hook frame must be ready in first render pass")
    elif hook_info.get("hook_type") == "curiosity gap":
        ae_tasks.insert(0, "⭐ PRIORITY: Mystery element must not be fully revealed until second half")

    # ── Assemble AI task list ──
    ai_tasks = template.get("ai_tasks", [])

    # ── Constraints (from card + template) ──
    constraints = list(anti)
    hook = hook_info.get("hook_type", "")

    if "shock" in hook:
        constraints.append("HOOK FRAME: 必须用 AI 生成，不可用截图或素材拼凑")
    if "curiosity" in hook:
        constraints.append("STORY: 不能在最后 5 秒前解决悬念")
    if "result" in hook:
        constraints.append("OPENING: 必须用游戏内画面，不可用黑场/Logo")

    constraints.append("FRAMING: 9:16 竖屏，安全区预留上下 10%")
    constraints.append("TEXT: 所有文字 ≥ 36pt，高对比度")
    constraints.append("NO: 黑场开场（>0.5s）、Logo开场、慢速淡入")

    # ── Validation goals ──
    ctr_uplift = perf.get("ctr_uplift_estimate", "+5%")
    cvr_uplift = perf.get("cvr_uplift_estimate", "+5%")

    execution = {
        "title": f"AE 制作脚本 — {card.get('cluster_id','?')} | {arch}" + (f" [{variant_name}]" if variant_name else ""),
        "archetype": arch,
        "cluster_id": card.get("cluster_id", "?"),
        "total_duration": f"{template['duration']}s",
        "generated_at": datetime.now().isoformat(),

        "winning_direction": card.get("winning_direction", ""),

        "hook_type": hook_info.get("hook_type", ""),
        "narrative_type": card.get("narrative_structure", {}).get("narrative_type", ""),
        "cognitive_trigger": trigger_info.get("primary", ""),

        "script_segments": script,

        "ae_tasks": ae_tasks,
        "ai_tasks": ai_tasks,

        "constraints": constraints,

        "validation_targets": {
            "ctr_uplift_goal": ctr_uplift,
            "cvr_uplift_goal": cvr_uplift,
            "watch_time_goal": f"≥{template['duration'] * 0.4:.0f}s average (40%+ of video)",
            "hook_retention": "≥60% retention at 3s mark",
        },

        "validation_placeholder": {
            "actual_ctr": None,
            "actual_cvr": None,
            "actual_watch_time": None,
            "drop_off_point": None,
            "verdict": None,
            "notes": "",
        },
    }

    return execution


def script_to_markdown(execution: dict) -> str:
    """渲染 Execution Script 为可打印的 Markdown 文本。

    AE 可以直接复制粘贴到工作文档中。
    """
    lines = []
    lines.append(f"# {execution['title']}")
    lines.append(f"")
    lines.append(f"🎯 方向: {execution['winning_direction']}")
    lines.append(f"📐 时长: {execution['total_duration']}  |  Hook: {execution['hook_type']}  |  Narrative: {execution['narrative_type']}")
    lines.append(f"🧠 触发: {execution['cognitive_trigger']}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    for seg in execution["script_segments"]:
        lines.append(f"### ⏱ {seg['timecode']}")
        lines.append(f"")
        lines.append(f"**画面:** {seg['visual_direction']}")
        lines.append(f"")
        lines.append(f"**镜头:** {seg['camera_movement']}")
        lines.append(f"")
        lines.append(f"**AE 动画:** {seg['ae_instruction']}")
        lines.append(f"")
        lines.append(f"**AI 生图 Prompt:** {seg['ai_generation_prompt']}")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    lines.append(f"## 🎬 AE 任务清单")
    lines.append(f"")
    for i, task in enumerate(execution["ae_tasks"], 1):
        lines.append(f"{i}. {task}")
    lines.append(f"")

    lines.append(f"## 🤖 AI 生图任务")
    lines.append(f"")
    for i, task in enumerate(execution["ai_tasks"], 1):
        lines.append(f"{i}. {task}")
    lines.append(f"")

    lines.append(f"## 🚫 制作红线")
    lines.append(f"")
    for c in execution["constraints"]:
        lines.append(f"- ❌ {c}")
    lines.append(f"")

    lines.append(f"## 🎯 验证目标")
    lines.append(f"")
    for k, v in execution.get("validation_targets", {}).items():
        lines.append(f"- {k}: {v}")
    lines.append(f"")

    lines.append(f"## 📝 结果回收（上线后填写）")
    lines.append(f"")
    lines.append(f"- 实际 CTR: ________")
    lines.append(f"- 实际 CVR: ________")
    lines.append(f"- 平均观看时长: ________")
    lines.append(f"- 跳出点: ________")
    lines.append(f"- 结论: ________")

    return "\n".join(lines)


def generate_single_run_output(fb_creative_id: str, card: dict) -> dict:
    """生成 single_run 完整输出包。

    包含：
      - direction_card
      - execution_script
      - validation_placeholder
    """
    script = card_to_script(card)
    markdown = script_to_markdown(script)

    return {
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "fb_creative_id": fb_creative_id,
        "archetype": script["archetype"],
        "cluster_id": script["cluster_id"],
        "direction_card": card,
        "execution_script": script,
        "execution_markdown": markdown,
        "validation": script["validation_placeholder"],
        "generated_at": script["generated_at"],
    }
