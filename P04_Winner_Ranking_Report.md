# P04 Creative Winner Ranking V2 Report

Generated: 2026-07-13

---

## Overview

Winner Ranking V2 从单一 `iap_score` 排序升级为多维度综合评估：

```
winner_score =
  0.40 * revenue_quality
+ 0.25 * scale_confidence
+ 0.20 * user_value
+ 0.15 * hook_score
```

---

## Top 10 Ranking

| Rank | Creative ID | Winner Score | Revenue Q | Scale Conf | User Value | Hook Score | Spend | Installs | ROAS D7 | CTR | IAP Score |
|------|-------------|-------------|-----------|------------|------------|------------|-------|----------|---------|-----|-----------|
| 1 | 1499507254711059 | **0.6512** | 0.7020 | 0.4490 | 0.9375 | 0.4711 | $62 | 18 | **0.70** | 0.94 | 0.9375 |
| 2 | 1990899471816855 | 0.6124 | 0.6239 | 0.4642 | 0.8805 | 0.4714 | $71 | 12 | 0.62 | 0.94 | 0.8805 |
| 3 | 949494547740050 | 0.5314 | 0.1600 | 0.8004 | 0.8719 | 0.6194 | $1590 | 762 | 0.16 | 1.24 | 0.8719 |
| 4 | 3766813603623702 | 0.5223 | 0.1200 | **0.8667** | 0.8849 | 0.5376 | **$2929** | **1124** | 0.12 | 1.08 | 0.8849 |
| 5 | 2681080065641777 | 0.5019 | 0.0900 | 0.8057 | 0.9184 | 0.5389 | $1669 | 370 | 0.09 | 1.08 | 0.9184 |
| 6 | 3492356247605322 | 0.4825 | 0.0772 | 0.6809 | 0.9015 | **0.6738** | $528 | 150 | 0.08 | **1.35** | 0.9015 |
| 7 | 4567166340195853 | 0.4824 | 0.0815 | 0.8016 | 0.8971 | 0.4669 | $1607 | 344 | 0.08 | 0.93 | 0.8971 |
| 8 | 2476690466139884 | 0.4766 | 0.0820 | 0.7489 | 0.9078 | 0.5005 | $989 | 186 | 0.08 | 1.00 | 0.9078 |
| 9 | 26995257276809682 | 0.4489 | 0.1600 | 0.5866 | **0.9463** | 0.3268 | $221 | 50 | 0.16 | 0.65 | **0.9463** |
| 10 | 26658407410413513 | 0.4223 | 0.1100 | 0.5318 | 0.8985 | 0.4379 | $133 | 44 | 0.11 | 0.88 | 0.8985 |

---

## Four-Type Winner Comparison

### Balanced Winner (综合最佳)

| | Value |
|---|---|
| Creative ID | 1499507254711059 |
| Winner Score | **0.6512** |
| Subject | witch character with merge transformation sequence |
| Overlay | "Merge & Watch the Magic" |
| Palette | deep purple, violet glow, gold accents |
| Spend | $62 (small sample!) |
| ROAS D7 | **0.70** (highest) |
| CTR | 0.94 |

**Insight**: 尽管 spend 很低（$62），但 ROAS D7 高达 0.70，加上 iap_score 0.94，在 revenue_quality (40%) 和 user_value (20%) 加权下冲到了 Top 1。**这是一个小样本高回报的素材，V2  ranking 依然暴露了这个风险。**

---

### Revenue Winner (真实收入能力最高)

| | Value |
|---|---|
| Creative ID | 1499507254711059 |
| Revenue Quality | **0.7020** |
| ROAS D7 | 0.70 |

Same as Balanced Winner. The revenue signal is so strong it dominates the composite score.

---

### Scale Winner (放量能力最高)

| | Value |
|---|---|
| Creative ID | 3766813603623702 |
| Scale Confidence | **0.8667** |
| Spend | **$2929** |
| Installs | **1124** |
| Subject | witch character evolution progression from novice to cosmic sorceress |
| Overlay | "Merge Witches, Level 1, MAX COSMIC POWER, ASCEND TO COSMIC POWER!" |
| CTR | 1.08 |
| ROAS D7 | 0.12 |

**Insight**: 这是唯一花了近 $3000、带来 1124 安装的素材。**如果担心小样本风险，这才是最值得复制的商业 Winner。** ROAS 虽然不高，但已经通过大预算验证了规模化能力。

---

### Hook Winner (点击吸引力最高)

| | Value |
|---|---|
| Creative ID | 3492356247605322 |
| Hook Score | **0.6738** |
| CTR | **1.35** (highest) |
| Spend | $528 |
| Installs | 150 |
| Subject | witch character tending to glowing magical plant |
| Overlay | "MERGE WITCHES, Nurture Your Magic Garden" |

**Insight**: CTR 1.35% 全场最高，说明素材在吸引点击上很强。但 ROAS 只有 0.08，回收一般。适合用来拉新，不适合直接复制为付费主力。

---

### IAP Intent Winner (内购意向最高)

| | Value |
|---|---|
| Creative ID | 26995257276809682 |
| User Value | **0.9463** |
| IAP Score | **0.9463** |
| Spend | $221 |
| CTR | 0.65 (low) |
| ROAS D7 | 0.16 |

**Insight**: 这就是上一轮 Golden Sample 选的 Winner（花园女巫）。iap_score 确实最高，但 CTR 只有 0.65，hook 能力弱。V2 ranking 把它降到了第 9 名，说明综合商业价值并不突出。

---

## Key Findings

1. **小样本问题依然存在**: Balanced Winner 只花了 $62，虽然 ROAS 高，但样本极小。`scale_confidence=0.449` 已经反映了这一点。

2. **最值得商业复制的可能是 Scale Winner**: `3766813603623702`（进化女巫）花了 $2929，带来 1124 安装，是唯一通过大预算验证的素材。

3. **Hook Winner 与 Revenue Winner 是不同的人**: CTR 最高的（1.35）和 ROAS 最高的（0.70）是完全不同的两张素材。说明吸引点击和带来付费是两个不同的能力维度。

4. **V1 的 Top 1 在 V2 降到第 9**: `26995257276809682`（花园女巫）按 iap_score 是 V1 Top 1，但 V2 综合排名第 9，只因为它 CTR 低、spend 少。

---

## Recommendation

对于 **Merge 类 IAP 产品的长期买量优化**：

| 场景 | 推荐 Winner Type | 原因 |
|------|-----------------|------|
| 快速验证创意方向 | **Hook Winner** | CTR 高，能低成本测试吸引力 |
| 追求 ROI | **Revenue Winner** | ROAS 最高，但注意样本量 |
| 大规模放量 | **Scale Winner** | 已通过 $2929 预算验证 |
| 综合最优 | **Balanced Winner** | V2 算法选出的综合最佳 |

---

## Next Step

运行 Golden Sample 验证，使用 **Balanced Winner**（默认）或 **Scale Winner**（如果追求放量安全性）：

```bash
# Balanced (default)
python scripts/run_p04_golden_sample_verify.py --winner-type balanced --threshold 7.0

# Scale (for scale confidence)
python scripts/run_p04_golden_sample_verify.py --winner-type scale --threshold 7.0
```
