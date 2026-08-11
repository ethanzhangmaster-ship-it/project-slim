"""Policy Learner — 从 V3.8 因果变量 → Policy Set。

将 causal driver + effect size + failure distribution 编译为
生产级 Policy Set。

每个 Policy 包含：
  - causal_variable: V3.8 的变量名
  - rule: 可执行规则 (time-based, measurable)
  - threshold: 通过/不通过的数值阈值
  - time_constraint: 精确到秒的时间窗口
  - ae_instruction: AE 可直接执行的指令
  - anti_pattern: 必须避免的做法
"""
from __future__ import annotations
from typing import Dict, List, Optional


# ── V3.8 已验证的因果变量 → Policy 映射 ──

CAUSAL_TO_POLICY = {
    "subject_presence_score": {
        "policy_id": "P1",
        "priority": 1,
        "causal_variable": "subject_presence_score",
        "effect_size": 0.074,
        "rule": "Subject must appear in center 40% of frame within 0.8 seconds.",
        "threshold": "subject_presence_score >= 0.15 in frame 0",
        "time_constraint": "0-0.8s",
        "ae_instruction": "第一帧必须在画面中心 40% 区域内放置一个高对比度的主体（角色/人物）。使用径向渐变 spotlight 突出主体，背景压暗 30%。第一帧不允许纯 UI 或无主体的场景画面。",
        "anti_pattern": [
            "Do NOT start with empty background/landscape",
            "Do NOT start with text-only frame",
            "Do NOT start with gameplay UI without character",
            "Do NOT use center-empty composition",
        ],
        "measurement": "subject_presence_score = center_contrast * 0.6 + edge_density * 0.4",
        "validated_by": "V3.8 causal analysis: +0.074 ROAS delta, HIGH confidence, p<0.001",
    },
    "first_frame_contrast": {
        "policy_id": "P2",
        "priority": 2,
        "causal_variable": "first_frame_contrast",
        "effect_size": 0.047,
        "rule": "First frame contrast must be >= 0.15 (on 0-1 scale).",
        "threshold": "first_frame_contrast >= 0.15",
        "time_constraint": "Frame 0 only",
        "ae_instruction": "提高第一帧对比度: 使用 S-curve 曲线工具, 增强阴影和高光。确保画面有纯黑和纯白区域，避免中间灰平的画面。",
        "anti_pattern": [
            "Do NOT use flat/soft lighting in first frame",
            "Do NOT use low-contrast gradients",
            "Do NOT start with washed-out or hazy visuals",
        ],
        "measurement": "first_frame_contrast = std(grayscale) / 255",
        "validated_by": "V3.8: MEDIUM confidence, +0.047 delta",
    },
    "motion_change_0_3s": {
        "policy_id": "P3",
        "priority": 3,
        "causal_variable": "motion_change_0_3s",
        "effect_size": 0.022,
        "rule": "There must be at least 1 measurable visual structure change within the first 3 seconds.",
        "threshold": "motion_change_0_3s >= 0.10",
        "time_constraint": "Change must occur between 0.8s and 3.0s",
        "ae_instruction": "确保 0.8-3s 内有关键视觉变化: 角色入场动作、场景切换、UI 弹出等。不允许 3 秒内画面结构无变化（仅 camera pan/zoom 不计入）。",
        "anti_pattern": [
            "Do NOT keep same frame composition for >2s in first 3 seconds",
            "Do NOT use only camera movement without structural change",
            "Do NOT fade between similar compositions",
        ],
        "measurement": "motion_change_0_3s = |contrast_p0 - contrast_p1| + |brightness_p0 - brightness_p1|",
        "validated_by": "V3.8 failure analysis: 56% of low-ROAS videos fail at this point",
    },
    "reward_visual_surge": {
        "policy_id": "P4",
        "priority": 4,
        "causal_variable": "reward_visual_surge",
        "effect_size": 0.017,
        "rule": "The video must include a measurable visual reward event after 6 seconds.",
        "threshold": "reward_visual_surge >= 0.05 (brightness + saturation increase in last frames)",
        "time_constraint": "Must occur between 6s and end of video",
        "ae_instruction": "在 6s 后安排一次视觉奖励事件: 胜利画面/升级动画/收集展示。使用亮度提升 + 饱和度增强 + 粒子特效的组合。",
        "anti_pattern": [
            "Do NOT end on the same visual state as the middle section",
            "Do NOT use text-only CTA as the only payoff",
        ],
        "measurement": "reward_visual_surge = max(0, p4_saturation - p3_saturation) + max(0, p4_brightness - p3_brightness)",
        "validated_by": "V3.8 failure analysis: 32% of low-ROAS videos fail at reward",
    },
    "text_density_0_3s": {
        "policy_id": "P5",
        "priority": 5,
        "causal_variable": "text_density_0_3s",
        "effect_size": 0.054,
        "rule": "Text/UI overlay density in the first 3 seconds must be minimized.",
        "threshold": "text_density_0_3s <= 0.06",
        "time_constraint": "0-3s",
        "ae_instruction": "前 3 秒禁止任何 UI 文字覆盖。所有文字（品牌名/口号/说明）推迟到 3 秒后出现。如果必须出现，使用图标替代文字。",
        "anti_pattern": [
            "Do NOT put text overlay on first 3 seconds",
            "Do NOT show UI labels/menus in hook phase",
        ],
        "measurement": "text_density_0_3s = max(text_density_frame0, text_density_frame1)",
        "validated_by": "V3.8: HIGH confidence correlation, +0.054 delta",
    },
}


def get_policy_set() -> List[Dict]:
    """返回完整 Policy Set，按 priority 排序。"""
    return sorted(CAUSAL_TO_POLICY.values(), key=lambda p: p["priority"])


def validate_policy_coverage(samples: List[Dict], policy_set: List[Dict]) -> Dict:
    """验证 Policy Set 对高/低 ROAS 视频的覆盖率。

    对每个 policy, 检查：
      - high ROAS videos: 多少条通过 (PASS)
      - low ROAS videos: 多少条被阻止 (BLOCKED)

    输出：
      {
        "policies": {
          "P1": {
            "high_roas_pass_rate": 0.87,
            "low_roas_block_rate": 0.81,
          }
        },
        "overall": {
          "high_roas_match": 0.85,
          "low_roas_blocked": 0.78,
        }
      }
    """
    if not samples:
        return {"error": "No samples provided"}

    sorted_samples = sorted(samples, key=lambda s: s.get("roas", 0), reverse=True)
    n = len(sorted_samples)
    top_n = max(10, n // 5)
    bottom_n = max(10, n // 5)
    high_group = sorted_samples[:top_n]
    low_group = sorted_samples[-bottom_n:]

    policy_results = {}
    for policy in policy_set:
        pid = policy["policy_id"]
        var_name = policy["causal_variable"]

        high_pass = 0
        low_block = 0

        for s in high_group:
            val = s.get("frame_features", {}).get(var_name, 0)
            if pid == "P1" and val >= 0.15:
                high_pass += 1
            elif pid == "P2" and val >= 0.15:
                high_pass += 1
            elif pid == "P3" and val >= 0.10:
                high_pass += 1
            elif pid == "P4" and val >= 0.05:
                high_pass += 1
            elif pid == "P5" and val <= 0.06:
                high_pass += 1

        for s in low_group:
            val = s.get("frame_features", {}).get(var_name, 0)
            if pid == "P1" and val < 0.15:
                low_block += 1
            elif pid == "P2" and val < 0.15:
                low_block += 1
            elif pid == "P3" and val < 0.10:
                low_block += 1
            elif pid == "P4" and val < 0.05:
                low_block += 1
            elif pid == "P5" and val > 0.06:
                low_block += 1

        policy_results[pid] = {
            "rule": policy["rule"],
            "high_roas_pass_rate": round(high_pass / max(len(high_group), 1), 4),
            "low_roas_block_rate": round(low_block / max(len(low_group), 1), 4),
            "high_pass_count": high_pass,
            "high_total": len(high_group),
            "low_block_count": low_block,
            "low_total": len(low_group),
        }

    # Overall: all policies must pass for a video to be "covered"
    high_match = 0
    for s in high_group:
        passes_all = True
        for policy in policy_set:
            pid = policy["policy_id"]
            var = policy["causal_variable"]
            val = s.get("frame_features", {}).get(var, 0)
            if pid == "P1" and val < 0.15: passes_all = False
            elif pid == "P2" and val < 0.15: passes_all = False
            elif pid == "P3" and val < 0.10: passes_all = False
            elif pid == "P4" and val < 0.05: passes_all = False
            elif pid == "P5" and val > 0.06: passes_all = False
        if passes_all:
            high_match += 1

    low_blocked = 0
    for s in low_group:
        any_fail = False
        for policy in policy_set:
            pid = policy["policy_id"]
            var = policy["causal_variable"]
            val = s.get("frame_features", {}).get(var, 0)
            if pid == "P1" and val < 0.15: any_fail = True
            elif pid == "P2" and val < 0.15: any_fail = True
            elif pid == "P3" and val < 0.10: any_fail = True
            elif pid == "P4" and val < 0.05: any_fail = True
            elif pid == "P5" and val > 0.06: any_fail = True
        if any_fail:
            low_blocked += 1

    return {
        "n_high": len(high_group),
        "n_low": len(low_group),
        "policies": policy_results,
        "overall": {
            "high_roas_match": round(high_match / max(len(high_group), 1), 4),
            "low_roas_blocked": round(low_blocked / max(len(low_group), 1), 4),
        },
    }
