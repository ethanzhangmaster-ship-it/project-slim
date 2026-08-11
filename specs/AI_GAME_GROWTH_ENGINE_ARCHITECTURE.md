# AI Game Growth Engine — 系统架构白皮书 v1.0

**日期**: 2026-07-20  
**系统代码量**: 1,215 文件, 232,406 行 Python  
**覆盖阶段**: E9.4 → E9.5 → E9.6 → E9.7 → E9.8 (完整闭环)  
**架构状态**: FROZEN — E9 Architecture v1.0

---

# 1. 系统定位

## 1.1 这个系统解决什么问题？

**一句话**：让 AI 代替人类完成"分析广告 → 理解玩家 → 预测新广告效果 → 投放后自动修正"的完整闭环。

**传统方式**：
```
人类投手 → 看报表 → 凭经验 → 猜下一个广告 → 投放 → 看结果 → 再猜
```

**本系统**：
```
AI → 从历史广告学习 → 理解玩家类型 → 预测新广告效果 → 投放反馈 → 自动修正模型 → 生成下一代广告
```

## 1.2 输入是什么？

| 输入 | 来源 | 内容 |
|------|------|------|
| 历史广告素材 | Facebook Ads 历史库 | 1,315 个视频/图片广告 |
| 玩家行为数据 | Firebase / Game Backend | 10,000+ 玩家, 1M+ 事件 |
| 广告表现数据 | Facebook Ads API | 安装量、花费、收入、留存 |
| 付费数据 | IAP Backend | 付费金额、付费率、商品ID |
| 归因数据 | Adjust / AppsFlyer | 安装来源、广告来源 |

## 1.3 输出是什么？

| 输出 | 说明 | 示例 |
|------|------|------|
| 玩家画像 | 每个广告吸引什么类型的玩家 | "这个广告 45% 是 Power 型玩家" |
| 广告预测 | 新广告上线前预估 LTV 和玩家构成 | "预计 LTV $18.5, 吸引 35% Power 玩家" |
| 学习报告 | 预测与实际对比，模型自动修正 | "challenge hook 的 Power 预测偏高 15%，已自动调低权重" |
| 新广告基因 | AI 自动生成下一代广告创意方向 | "hook=challenge + reward=collection 预计 LTV $22.3" |

## 1.4 最终决策是什么？

系统最终回答三个问题：

1. **这个广告吸引谁？**（E9.4 → E9.5）
2. **新广告会吸引谁？**（E9.6）
3. **预测错了怎么办？下一批广告怎么做？**（E9.7 → E9.8）

---

# 2. 完整系统架构流程

```
                        ┌─────────────────────────────────────┐
                        │        DATA ASSET LAYER             │
                        │                                     │
                        │  Facebook Ads  │  Firebase Events   │
                        │  Adjust/AppsFlyer │ IAP Revenue     │
                        │  Creative Assets (Video/Image)      │
                        └──────────────┬──────────────────────┘
                                       │
          ┌────────────────────────────┼────────────────────────────┐
          │                            │                            │
          ▼                            ▼                            ▼
┌──────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│ Creative DNA     │    │  Player Events       │    │ Campaign Performance │
│ Engine (E9.4)    │    │  (E9.4)              │    │ (E9.7)               │
│                  │    │                      │    │                      │
│ 输入: 视频/图片   │    │ 输入: Firebase事件    │    │ 输入: Facebook API    │
│ 输出: DNA 基因   │    │ 输出: PlayerDNA      │    │ 输出: LTV/ROAS/留存   │
│                  │    │                      │    │                      │
│ hook: emotional  │    │ progression_dna      │    │ ltv_d30: 19.2        │
│ reward: discovery│    │ collection_dna       │    │ payer_rate: 0.40     │
│ visual: 2d_flat  │    │ payment_dna          │    │ d30_retention: 0.67  │
│ fantasy:  dragons│    │ retention_dna        │    │                      │
└────────┬─────────┘    └──────────┬───────────┘    └──────────┬───────────┘
         │                         │                           │
         │                         ▼                           │
         │              ┌──────────────────────┐               │
         │              │ Player Intelligence  │               │
         │              │ (E9.5)               │               │
         │              │                      │               │
         │              │ 输入: PlayerDNA      │               │
         │              │ 输出: PlayerGenome   │               │
         │              │                      │               │
         │              │ 5种玩家原型:          │               │
         │              │ Power | Collector    │               │
         │              │ Explorer | Progression│              │
         │              │ Casual               │               │
         │              └──────────┬───────────┘               │
         │                         │                           │
         │                         ▼                           │
         │              ┌──────────────────────┐               │
         │              │ Creative-Archetype   │               │
         │              │ Matrix (E9.5)        │               │
         │              │                      │               │
         │              │ 每个广告 → 吸引的     │               │
         │              │ 玩家类型分布           │               │
         │              └──────────┬───────────┘               │
         │                         │                           │
         ├─────────────────────────┘                           │
         │                                                     │
         ▼                                                     │
┌──────────────────────────────────────┐                      │
│ Creative Matching Engine (E9.6)      │                      │
│                                      │                      │
│ 输入: Creative DNA + Archetype Matrix│                      │
│ 输出: CreativePrediction             │                      │
│                                      │                      │
│ P(arch | DNA) = 0.8×affinity + 0.2×prior                   │
│                                      │                      │
│ 预测:                                │                      │
│ - 玩家类型分布: Power 35%, Collector 20%...                 │
│ - 预期 LTV: $18.5                    │                      │
│ - 预期 D30: 42%                      │                      │
│ - 预期付费率: 31%                     │                      │
└──────────────┬───────────────────────┘                      │
               │                                              │
               ▼                                              │
┌──────────────────────────────────────┐                      │
│ Feedback Learning Engine (E9.7)      │◄─────────────────────┘
│                                      │
│ 输入: Prediction + Actual Performance│
│ 输出: DNA Weight Updates             │
│                                      │
│ new_weight = old_weight + 0.25×error │
│                                      │
│ 发现:                                │
│ - challenge hook → Power 预测偏高 15% │
│ - emotional → collector 预测偏低 12%  │
│                                      │
│ → 自动调低 challenge 的 power_weight │
│ → 自动调高 emotional 的 collector_weight│
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ Creative Evolution Engine (E9.8)     │
│                                      │
│ 输入: Winner DNA + Failure DNA       │
│       + E9.7 Learned Weights         │
│ 输出: 1,250 个 New Creative Genome   │
│                                      │
│ Mutation:                            │
│ - Hook: emotional → challenge        │
│ - Reward: discovery → collection     │
│ - Visual: 2d_flat → 3d_cartoon       │
│ - Fantasy: dragons → power_growth    │
│ - Archetype: collector → power       │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ Experiment Layer (E9.9+)             │
│                                      │
│ 输入: Top 20 New Genomes             │
│ 输出: A/B Test Results               │
│                                      │
│ → 投放测试 → 收集结果 → 反馈给 E9.7   │
└──────────────────────────────────────┘
```

---

# 3. 完整 Pipeline 拆解（Step by Step）

## Step 1: Creative DNA 构建

**模块**: Creative DNA Engine (E9.4)  
**作用**: 从历史广告素材中提取创意基因  
**输入**: 1,315 个 Facebook 广告视频/图片  
**处理逻辑**:
- 分析视频内容：钩子类型、核心机制、奖励类型、视觉风格
- 分析文案：幻想驱动、情感强度、付费触发点
- 结构化输出：每个广告 → 一张 DNA 卡片
**输出**: `creative_dna_master.json` (1,315 entries, 2.1 MB)

```
广告视频 → Creative DNA Engine → DNA 卡片
                                  ├── hook: "emotional"
                                  ├── mechanism: "merge"
                                  ├── reward: "discovery"
                                  ├── fantasy: ["collect_dragons", "become_powerful"]
                                  ├── visual: "2d_flat"
                                  └── payment_trigger: [...]
```

## Step 2: 玩家 DNA 提取

**模块**: PlayerDNA Engine (E9.4)  
**作用**: 从游戏事件中提取玩家行为 DNA  
**输入**: Firebase 玩家事件 (10,000+ 玩家, 1M+ 事件)  
**处理逻辑**:
- 提取 progression_dna: 合并速度、关卡深度、区域解锁
- 提取 collection_dna: 收集率、稀有物品比例、完成度
- 提取 payment_dna: 付费金额、付费频率、首次付费时间
- 提取 retention_dna: D7/D30 留存、会话频率
**输出**: `player_genomes.json` (500 玩家基因组, 694 KB)

## Step 3: 玩家原型分类

**模块**: Player Intelligence (E9.5)  
**作用**: 把玩家行为数据转化为"玩家类型"  
**输入**: `{player_id: PlayerDNA}` + `{player_id: [PlayerEvent]}`  
**处理逻辑**:

```
PlayerDNA → BehaviorFeatureEngine → 16维特征 (0-1归一化)
                                    ├── merge_velocity, merge_depth
                                    ├── collection_rate, rare_item_ratio
                                    ├── purchase_intent, spending_level
                                    └── session_frequency, retention_strength

16维特征 → ArchetypeClassifier → 5种原型评分
                                   ├── Collector: 收藏率×0.4 + 稀有物品×0.3 + 完成度×0.3
                                   ├── Power: 强度×0.35 + 付费×0.35 + 等级×0.3
                                   ├── Explorer: 解锁×0.35 + 活动×0.35 + 多样性×0.3
                                   ├── Progression: 合并速度×0.4 + 关卡×0.3 + 速度×0.3
                                   └── Casual: 1 - max(其他四项)
```

**输出**: `player_genomes.json` (每个玩家有 archetype + value_segment + payment_profile)

## Step 4: 创意-玩家矩阵

**模块**: ArchetypeClassifier (E9.5)  
**作用**: 建立"每个广告吸引什么类型玩家"的映射  
**输入**: 所有 PlayerGenome 按 creative_id 分组  
**处理逻辑**: 统计每个 creative 吸引的玩家类型分布  
**输出**: `creative_archetype_matrix.json`
```
creative_A: {Power: 45%, Collector: 20%, Explorer: 25%, Progression: 8%, Casual: 2%}
creative_B: {Power: 15%, Collector: 50%, Explorer: 18%, Progression: 12%, Casual: 5%}
```

## Step 5: 创意 DNA → 特征编码

**模块**: DNAFeatureEncoder (E9.6)  
**作用**: 把 DNA 文字描述转化为 10 维数值向量  
**输入**: Creative DNA 卡片  
**处理逻辑**: 关键词匹配 → 数字映射 → 归一化  
**输出**: `DNAFeatureVector` (10 维, 0-1)
```
collection_strength: 0.15    ← 关键词: "collect", "complete", "all"
progression_strength: 0.22   ← 关键词: "merge", "level", "upgrade"
power_expression: 0.45       ← 关键词: "powerful", "strong", "win"
exploration_strength: 0.28   ← 关键词: "discover", "explore", "secret"
emotion_intensity: 0.62      ← 关键词: "amazing", "exciting", "magical"
reward_value: 0.55           ← 关键词: "reward", "prize", "gift"
novelty_score: 0.35
urgency_signal: 0.12
payment_affinity: 0.40
retention_hook_strength: 0.68
```

## Step 6: 创意 → 玩家类型预测

**模块**: ArchetypePredictor (E9.6)  
**作用**: 预测一个新广告会吸引什么类型玩家  
**输入**: DNAFeatureVector + 市场先验分布  
**处理逻辑**: 贝叶斯混合公式
```
P(arch | DNA) = 0.8 × DNA_affinity(arch) + 0.2 × prior(arch)
```
**输出**: `CreativePrediction`
```
creative_001:
  power: 35% (confidence 0.72)
  collector: 20% (confidence 0.65)
  explorer: 28% (confidence 0.68)
  progression: 12% (confidence 0.60)
  casual: 5% (confidence 0.55)
Expected LTV: $18.5
Expected D30: 42%
Expected payer_rate: 31%
```

## Step 7: 预测快照保存

**模块**: PredictionTracker (E9.7)  
**作用**: 保存预测结果，建立预测历史数据库  
**输入**: `creative_prediction.json` (来自 E9.6)  
**输出**: `prediction_history.json` (912 条, 1.1 MB)

## Step 8: 收集真实表现数据

**模块**: PerformanceCollector (E9.7)  
**作用**: 收集广告投放后的真实数据  
**输入**: Facebook Ads API / CSV / JSON  
**输出**: `actual_performance.json` (912 条, 423 KB)

## Step 9: 重建真实玩家类型

**模块**: ArchetypeReconstructionEngine (E9.7)  
**作用**: 用真实数据重新运行 E9.5 分类器  
**输入**: 真实投放后的玩家行为数据  
**输出**: 每个 creative 的真实玩家类型分布

## Step 10: 计算预测误差

**模块**: PredictionErrorAnalyzer (E9.7)  
**作用**: 比较预测 vs 实际  
**输入**: predictions + actuals  
**处理逻辑**:
```
Archetype Error = |Predicted - Actual|
LTV Error = (Predicted - Actual) / Actual
MAE = mean(|error|)
```
**输出**: `prediction_error_report.json` (912 条, 1.7 MB)

## Step 11: 学习 DNA 权重调整

**模块**: DNAWeightOptimizer (E9.7)  
**作用**: 发现哪些 DNA 特征导致预测偏差  
**输入**: errors + predictions + actuals  
**处理逻辑**:
```
1. 按 DNA 特征值分组 (challenge hook, emotional hook, ...)
2. 计算每组平均误差
3. new_weight = old_weight + 0.25 × mean_error
4. 跳过 empty/unknown 特征值
```
**输出**: `dna_weight_config.json` (31 条更新, 8.8 KB)

## Step 12: 赢家 DNA 分析

**模块**: WinnerDNAAnalyzer (E9.8)  
**作用**: 提取 top 20% LTV 赢家的共同 DNA  
**输入**: creative_dna_master + actual_performance  
**处理逻辑**:
- 按 LTV 排序，取 top 20%
- 统计赢家的 hook/reward/visual/fantasy 分布
- 计算赢家的 archetype 亲和力
**输出**: WinnerPattern
```
Top hooks: emotional (86.4%)
Top rewards: discovery (86.4%)
Top fantasies: become_powerful (86.4%), discovery_world (86.0%)
Avg winner LTV: $21.3
Archetype affinity: collector: 41.3%, power: 22.3%, explorer: 18.7%
```

## Step 13: 失败模式分析

**模块**: FailurePatternAnalyzer (E9.8)  
**作用**: 识别 bottom 20% 的失败 DNA 模式  
**输入**: creative_dna_master + actual_performance  
**处理逻辑**: 分析失败广告的 DNA 特征共性  
**输出**: FailureAnalysis
```
Avoid hooks: empty, secret
Avoid rewards: empty, unlock
10 failure patterns identified
```

## Step 14: 生成变异策略

**模块**: MutationStrategyEngine (E9.8)  
**作用**: 决定"怎么变异"  
**输入**: WinnerPattern + FailureAnalysis  
**处理逻辑**: 4 种策略并行
- winner_emulation: 向赢家 DNA 靠拢
- failure_avoidance: 避免失败 DNA
- exploration: 探索未使用的 DNA 值
- archetype_targeting: 瞄准弱势玩家类型
**输出**: 46 条 MutationStrategy

## Step 15: 核心变异

**模块**: CreativeGenomeMutator (E9.8)  
**作用**: 生成 1,250 个新创意基因候选  
**输入**: 228 个赢家 DNA + 46 条策略  
**处理逻辑**:
- 每个赢家 DNA 作为模板
- 对每个维度尝试所有替代值
- 生成 SHA256 确定性 ID
- 排除失败模式
**输出**: 1,250 个 (CreativeGenome, MutationRecord) 对

## Step 16: 市场机会检测

**模块**: OpportunityDetector (E9.8)  
**作用**: 发现未探索的 DNA 组合  
**输入**: 全部 DNA 数据 + WinnerPattern  
**输出**: 20 个 MarketOpportunity
```
"Under-explored hook: 'secret' (only 1.1%)"
"Missing combination: hook='challenge' + reward='collection'"
"Under-represented archetype 'casual' in winners (4.1%)"
```

## Step 17: 预测 + 排序

**模块**: MutationRanker (E9.8)  
**作用**: 为新基因组预测 LTV 并排序  
**输入**: 1,250 个 genomes + E9.6 predictor + E9.7 weights  
**处理逻辑**:
```
Composite Score = 0.25×DNA_Alignment + 0.20×Winner_Similarity
                + 0.15×Opportunity + 0.25×LTV + 0.15×Novelty
```
**输出**: 1,250 个 ranked MutationCandidate

## Step 18: 导出

**模块**: EvolutionExporter (E9.8)  
**输出**:
- `mutation_candidates.json` (1,250 条, 1,518 KB)
- `top_mutations.json` (Top 20, 22 KB)
- `evolution_report.json` (汇总, 29 KB)

---

# 4. 核心模块详解

## 4.1 Creative DNA Builder (E9.4)

**为什么存在**？
没有统一的创意描述语言，就无法让 AI 理解广告。每个广告需要被翻译成"基因"。

**解决什么问题**？
把 1,315 个视频/图片广告 → 统一的 DNA 结构化描述。

**依赖什么数据**？
- 广告素材文件 (视频/图片)
- 广告文案
- 元数据 (时长、分辨率、文件名)

**产生什么资产**？
`creative_dna_master.json` — 1,315 条 DNA 记录，每条包含：
- hook: 钩子类型 (emotional/challenge/secret/curiosity)
- mechanism: 核心机制 (merge/collect/upgrade)
- reward: 奖励类型 (discovery/unlock/collection)
- fantasy: 幻想驱动 (become_powerful/discovery_world/collect_dragons)
- visual: 视觉风格 (2d_flat/3d_cartoon)
- payment_trigger: 付费触发点
- retention: 留存钩子

**如何影响下一步**？
Creative DNA 是 E9.6 预测的输入，也是 E9.8 变异的模板。

## 4.2 Winner Pattern Miner (E9.8)

**为什么存在**？
AI 需要知道"什么是好广告"，才能生成更好的广告。

**解决什么问题**？
从 912 个广告中找到 top 20% LTV 的赢家共性。

**依赖什么数据**？
- creative_dna_master.json
- actual_performance.json

**产生什么资产**？
WinnerPattern — 赢家共同 DNA：
- Top hooks: emotional (86.4%)
- Top rewards: discovery (86.4%)
- Avg winner LTV: $21.3
- Archetype affinity: collector 41.3%

**如何影响下一步**？
WinnerPattern 是变异策略的输入，告诉系统"朝哪个方向变异"。

## 4.3 Creative Intelligence / Player Intelligence (E9.5)

**为什么存在**？
只知道"广告是什么"不够，还需要知道"玩家是什么类型"。

**解决什么问题**？
把 10,000+ 玩家的行为数据 → 5 种玩家原型。

**5 种原型**：

| 原型 | 特征 | 付费驱动 | 识别方式 |
|------|------|---------|---------|
| Power | 高等级、稀有物品、升级 | 强度提升 | 高 level_growth + 高 purchase_intent |
| Collector | 高收集率、完成度 | 收藏完成 | 高 collection_rate + 高 completion_bias |
| Explorer | 区域解锁、活动参与 | 新内容解锁 | 高 area_unlock + 高 event_participation |
| Progression | 快速升级、合并深度 | 进度加速 | 高 merge_velocity + 高 merge_depth |
| Casual | 低参与度、随机 | 便利性 | 低全部指标 |

**依赖什么数据**？
- Firebase 玩家事件 (session, level, purchase, retention)
- 每个玩家的 creative_id (来自 Adjust 归因)

**产生什么资产**？
- `player_genomes.json` — 500 玩家基因组
- `creative_archetype_matrix.json` — 每个广告的玩家类型分布
- `archetype_report.json` — 全局玩家类型分布

**如何影响下一步**？
Creative-Archetype Matrix 是 E9.6 预测的先验分布来源。

## 4.4 Archetype Classification (E9.5)

**为什么存在**？
玩家行为数据太原始，需要转化为"类型"才能做预测。

**解决什么问题**？
PlayerEvent → 16 维特征 → 5 种原型评分 → 分类。

**Pipeline**：
```
PlayerEvent → PlayerDNAEngine → PlayerDNA
    ↓
PlayerDNA → BehaviorFeatureEngine → 16 features (0-1)
    ↓
BehaviorFeatures → ArchetypeClassifier → 5 scores
    ↓
max(score) → Archetype
```

**16 维特征**：
- Progression: merge_velocity, merge_depth, level_growth_rate, area_unlock_speed
- Collection: collection_rate, rare_item_ratio, completion_bias, missing_item_pressure
- Monetization: purchase_intent, purchase_frequency, offer_conversion, spending_level
- Engagement: session_frequency, daily_return, event_participation, retention_strength

## 4.5 Creative → Archetype Matching (E9.6)

**为什么存在**？
知道"广告的 DNA"和"玩家的类型"，需要建立两者的映射关系。

**解决什么问题**？
一个新广告上线前，预测它会吸引什么类型的玩家。

**预测公式**：
```
P(arch | DNA) = 0.8 × DNA_affinity + 0.2 × historical_prior

DNA_affinity = Σ(feature_i × weight_i(arch))
```

**为什么用 0.8/0.2 贝叶斯混合？**
- 0.8: 信任 DNA 特征匹配 (如果广告有 dragon 元素，大概率吸引 Collector)
- 0.2: 参考市场先验 (如果整个市场 41% 是 Collector，新广告也不例外)

**依赖什么数据**？
- Creative DNA (1,315 条)
- Creative-Archetype Matrix (先验分布)
- E9.7 learned weights (如果有)

**产生什么资产**？
- `creative_prediction.json` (912 条, 2.9 MB)
- `creative_archetype_rank.json` (6 维度排名, 40 KB)

**如何影响下一步**？
Prediction 是 E9.7 反馈学习的输入，也是 E9.8 候选排序的输入。

## 4.6 Creative Prediction (E9.6)

**为什么存在**？
预测是"分析"和"学习"之间的桥梁。没有预测，就无法计算误差。

**解决什么问题**？
给每个广告一个预测分数，包括：
- 会吸引什么玩家类型
- 预期 LTV 是多少
- 付费率是多少
- 置信度是多少

**输出格式**：
```json
{
  "creative_id": "787567970297102",
  "prediction": {
    "power": {"probability": 0.35, "confidence": 0.72},
    "collector": {"probability": 0.20, "confidence": 0.65}
  },
  "expected": {"ltv": 18.5, "d30": 0.42, "payer_rate": 0.31},
  "confidence": 0.72
}
```

## 4.7 Evolution Engine (E9.8)

**为什么存在**？
E9.6 只能预测已有广告。E9.8 让系统能创造新广告。

**解决什么问题**？
从"分析历史广告"升级到"自动生成下一代广告基因"。

**9 步流水线**：
```
1. Load Data          → 加载 DNA + Performance
2. Analyze Winners    → 提取赢家模式
3. Analyze Failures   → 识别失败模式
4. Generate Strategies → 4 种变异策略
5. Detect Opportunities → 20 个市场机会
6. Mutate             → 1,250 个新基因组
7. Predict & Rank     → E9.6 预测 + 5 维评分
8. Build Report       → EvolutionReport
9. Export             → 3 个输出文件
```

**依赖什么数据**？
- creative_dna_master.json
- actual_performance.json
- dna_weight_config.json (E9.7)
- E9.6 DNAFeatureEncoder + ArchetypePredictor

**产生什么资产**？
- 1,250 个 mutation candidates
- Top 20 ranked mutations
- evolution_report.json

**如何影响下一步**？
Top 20 候选进入 E9.9 实验引擎，投放 A/B 测试。

## 4.8 Experiment Engine (E9.9+, 规划中)

**为什么存在**？
变异后的基因需要验证，不能直接全量投放。

**解决什么问题**？
自动编排 A/B 测试：小预算 → 收集数据 → 胜出 → 放量 → 失败 → 暂停。

**闭环**：
```
Top 20 Genomes
    ↓
A/B Test (小预算)
    ↓
收集结果 (Facebook Ads API)
    ↓
胜出者放量 / 失败者暂停
    ↓
结果反馈给 E9.7 Learning
```

## 4.9 Feedback Loop (E9.7)

**为什么存在**？
没有反馈，预测就是静态的。有了反馈，系统会自我修正。

**解决什么问题**？
预测错了 → 发现原因 → 自动修正 → 下次更准。

**学习公式**：
```
new_weight = old_weight + 0.25 × error

例如:
  challenge hook → power_expression weight
  预测 Power 45%, 实际 25%, error = -0.20
  new_weight = 0.50 + 0.25 × (-0.20) = 0.45
  → 下次预测时，challenge 广告的 Power 分会降低
```

**实际效果**：
- 31 条权重更新
- 发现: emotional → collector +0.037, secret → explorer +0.028
- 发现: challenge → collector -0.020

---

# 5. 完整数据流

```
Facebook 历史广告数据 (1,315 条)
    │
    ▼
Creative DNA Engine (E9.4)
    │
    ├── hook: emotional / challenge / secret
    ├── reward: discovery / unlock / collection
    ├── visual: 2d_flat / 3d_cartoon
    ├── fantasy: become_powerful / collect_dragons / discovery_world
    └── mechanism: merge / collect / upgrade
    │
    ▼
creative_dna_master.json (1,315 entries)
    │
    ├──────────────────────────────────────┐
    │                                      │
    ▼                                      ▼
Winner Pattern Miner (E9.8)        DNAFeatureEncoder (E9.6)
    │                                      │
    │ Winner Pattern:                      │ DNAFeatureVector:
    │ - hook: emotional 86.4%              │ - collection_strength: 0.15
    │ - reward: discovery 86.4%            │ - power_expression: 0.45
    │ - avg LTV: $21.3                     │ - emotion_intensity: 0.62
    │                                      │ - ... (10 dimensions)
    │                                      │
    └──────────────┬───────────────────────┘
                   │
                   ▼
            Creative Genome Mutator (E9.8)
                   │
                   │ 1,250 new genomes
                   │
                   ├──────────────────────────────────────┐
                   │                                      │
                   ▼                                      ▼
            E9.6 Predictor                        E9.7 Learned Weights
            (archetype + LTV)                     (dna_weight_config.json)
                   │                                      │
                   └──────────────┬───────────────────────┘
                                  │
                                  ▼
                          Mutation Ranker (E9.8)
                                  │
                                  │ 5-dimension scoring
                                  │
                                  ▼
                          Top 20 New Genomes
                                  │
                                  ▼
                          Experiment (E9.9+)
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
                Winner        Neutral        Loser
                    │             │             │
                    │             │             ▼
                    │             │        Feedback to E9.7
                    │             │        (avoid this pattern)
                    │             │
                    ▼             ▼
              Scale Up        Continue Test
                    │             │
                    └──────┬──────┘
                           │
                           ▼
                    Performance Data
                           │
                           ▼
                    E9.7 Feedback Loop
                    (update weights)
                           │
                           ▼
                    Better Predictions
                           │
                           ▼
                    Next Evolution Cycle
```

---

# 6. 版本演进历史

## V3.x — Creative Intelligence (早期)

**完成内容**: 创意素材分析、视频智能识别、基础 DNA 提取  
**核心能力**: 把广告素材转化为结构化 DNA  
**输入**: Facebook 广告视频/图片  
**输出**: Creative DNA 卡片  
**解决的问题**: "这个广告是什么？"

## V4.x — Creative Growth Loop (中期)

**完成内容**: Creative Growth Loop, Creative Factory, Creative Ranking, Creative Decision  
**核心能力**: 创意生产流水线、创意评分、预算决策  
**输入**: Creative DNA + 表现数据  
**输出**: 创意排名、预算分配建议  
**解决的问题**: "哪个广告更好？应该投多少？"

## V5.x — Evolution Framework (架构)

**完成内容**: Evolution Engine, Genome Manager, Population Manager, Fitness Calculator  
**核心能力**: 创意进化框架、种群管理、适应度计算  
**输入**: 创意基因组 + 表现数据  
**输出**: 进化状态、突变建议  
**解决的问题**: "如何让创意系统自我进化？"

## E9.4 — Player Value Attribution

**完成内容**: PlayerEvent, PlayerDNA, PlayerDNAEngine, CreativePlayerAttribution  
**核心能力**: 将玩家行为归因到具体广告  
**输入**: Firebase 玩家事件 + 广告 ID  
**输出**: PlayerDNA, 每个广告的玩家画像  
**解决的问题**: "这个广告带来了什么玩家？"

## E9.5 — Player Archetype Intelligence

**完成内容**: 5 种玩家原型, 16 维行为特征, BehaviorFeatureEngine, ArchetypeClassifier, Creative-Archetype Matrix  
**核心能力**: 玩家行为 → 玩家类型  
**输入**: 10,000+ 玩家, 1M+ 事件  
**输出**: PlayerGenome, 创意-玩家矩阵  
**解决的问题**: "这些玩家是什么类型？为什么喜欢这个广告？"

## E9.6 — Creative → Archetype Prediction

**完成内容**: DNAFeatureEncoder (10 维), ArchetypePredictor (贝叶斯), MatchingEngine, Creative Ranking (6 维)  
**核心能力**: 预测新广告会吸引什么玩家  
**输入**: Creative DNA + Archetype Matrix  
**输出**: CreativePrediction (912 条), CreativeArchetypeRank  
**解决的问题**: "一个新广告上线前，会吸引什么玩家？预期 LTV 多少？"

## E9.7 — Prediction Feedback Learning

**完成内容**: PredictionTracker, PerformanceCollector, PredictionErrorAnalyzer, DNAWeightOptimizer, LearningEngine, ArchetypeReconstructionEngine, LearningExporter  
**核心能力**: 预测→实际→误差→学习→修正  
**输入**: E9.6 Prediction + 真实投放数据  
**输出**: 31 条权重更新, 5 个输出文件  
**解决的问题**: "预测错了怎么办？怎么自动修正？"

## E9.8 — Creative Mutation Engine

**完成内容**: WinnerDNAAnalyzer, FailurePatternAnalyzer, MutationStrategyEngine, CreativeGenomeMutator, OpportunityDetector, MutationRanker, EvolutionEngine, EvolutionExporter  
**核心能力**: 自动生成下一代创意基因  
**输入**: 228 赢家 DNA + 269 失败 DNA + E9.7 权重  
**输出**: 1,250 个新基因组, Top 20 推荐  
**解决的问题**: "下一批应该创造什么广告？"

---

# 7. 未来自动化闭环

## 每日自动运行流程

```
00:00 — 数据采集
├── Facebook Ads API: 拉取昨日广告表现数据
├── Adjust API: 拉取归因数据
├── Firebase: 拉取玩家行为事件
└── Game Backend: 拉取 IAP 付费数据

02:00 — 数据处理
├── Creative DNA Engine: 更新新广告 DNA
├── PlayerDNA Engine: 更新玩家行为 DNA
└── PerformanceCollector: 更新表现数据

04:00 — 分析与预测
├── E9.5: 重新分类玩家类型 (有新数据)
├── E9.6: 预测新广告效果
└── E9.7: 计算预测误差

06:00 — 学习与进化
├── DNAWeightOptimizer: 更新 DNA 权重
├── WinnerDNAAnalyzer: 更新赢家模式
├── FailurePatternAnalyzer: 更新失败模式
└── CreativeGenomeMutator: 生成新基因组

08:00 — 决策与执行
├── MutationRanker: 排序新基因组
├── Top 20 → 投放队列
├── 预算调整建议 (增长/暂停)
└── 报告生成

09:00 — 人类审核
├── 查看 Top 20 推荐
├── 审批或拒绝
└── 批准后 → 自动创建广告

10:00 — 投放执行
├── Facebook Ads API: 创建 Campaign
├── A/B 测试: 小预算启动
└── 监控: 实时表现追踪

次日 00:00 — 循环
└── 收集投放结果 → 反馈给 E9.7 → 修正模型 → 下一轮
```

## 最终如何提高 ROI？

```
第 1 天: 系统预测 → 投放 20 个新广告
第 3 天: 收集数据 → 发现 5 个胜出者
第 5 天: 胜出者放量 → 失败者暂停
第 7 天: 反馈学习 → 修正预测模型
第 8 天: 生成新一批广告 → 比上一批更准
第 30 天: 模型已学习 4 轮反馈 → 预测准确率显著提升
第 90 天: 系统自主运行 → 持续优化 → ROI 持续增长
```

---

# 8. AI Game Growth Engine 总体架构图

```
╔══════════════════════════════════════════════════════════════════╗
║                   AI GAME GROWTH ENGINE v1.0                    ║
║                     Creative Evolution OS                       ║
╚══════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────┐
│                     EXPERIMENT LAYER (E9.9+)                    │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ A/B Test     │  │ Budget       │  │ Creative Scaling     │  │
│  │ Orchestrator │  │ Auto-Adjust  │  │ Engine               │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                 │                      │              │
│         └─────────────────┼──────────────────────┘              │
│                           │                                      │
│              Facebook Ads API / Google Ads API                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ 投放结果
                            │
┌───────────────────────────┴─────────────────────────────────────┐
│                     EVOLUTION LAYER (E9.8)                      │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ Winner DNA       │  │ Failure Pattern  │  │ Opportunity  │  │
│  │ Analyzer         │  │ Analyzer         │  │ Detector     │  │
│  │                  │  │                  │  │              │  │
│  │ Top 20% LTV      │  │ Bottom 20% LTV   │  │ Market Gaps  │  │
│  │ → WinnerPattern  │  │ → FailureAnalysis│  │ → 20 opps    │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘  │
│           │                     │                    │          │
│           └─────────────────────┼────────────────────┘          │
│                                 │                                │
│                    ┌────────────┴────────────┐                  │
│                    │  Mutation Strategy      │                  │
│                    │  Engine                 │                  │
│                    │                         │                  │
│                    │  4 strategies:          │                  │
│                    │  - winner_emulation     │                  │
│                    │  - failure_avoidance    │                  │
│                    │  - exploration          │                  │
│                    │  - archetype_targeting  │                  │
│                    └────────────┬────────────┘                  │
│                                 │                                │
│                    ┌────────────┴────────────┐                  │
│                    │  Creative Genome        │                  │
│                    │  Mutator                │                  │
│                    │                         │                  │
│                    │  SHA256 deterministic IDs│                 │
│                    │  1,250+ candidates      │                  │
│                    │  5 mutation types:      │                  │
│                    │  hook/reward/visual/    │                  │
│                    │  fantasy/archetype      │                  │
│                    └────────────┬────────────┘                  │
│                                 │                                │
│                    ┌────────────┴────────────┐                  │
│                    │  Mutation Ranker        │                  │
│                    │                         │                  │
│                    │  Score = 0.25×Alignment │                  │
│                    │  + 0.20×Similarity      │                  │
│                    │  + 0.15×Opportunity     │                  │
│                    │  + 0.25×LTV             │                  │
│                    │  + 0.15×Novelty         │                  │
│                    │                         │                  │
│                    │  → Top 20 Candidates    │                  │
│                    └─────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                            │ feedback
                            │
┌─────────────────────────────────────────────────────────────────┐
│                    LEARNING LAYER (E9.7)                        │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ Prediction       │  │ Performance      │  │ Archetype    │  │
│  │ Tracker          │  │ Collector        │  │ Reconstruction│ │
│  │                  │  │                  │  │              │  │
│  │ Save E9.6        │  │ Collect real     │  │ Re-run E9.5  │  │
│  │ predictions      │  │ campaign data    │  │ on real data │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘  │
│           │                     │                    │          │
│           └─────────────────────┼────────────────────┘          │
│                                 │                                │
│                    ┌────────────┴────────────┐                  │
│                    │  Prediction Error       │                  │
│                    │  Analyzer               │                  │
│                    │                         │                  │
│                    │  Archetype MAE          │                  │
│                    │  LTV Error              │                  │
│                    │  Payer Rate Error       │                  │
│                    └────────────┬────────────┘                  │
│                                 │                                │
│                    ┌────────────┴────────────┐                  │
│                    │  DNA Weight Optimizer   │                  │
│                    │                         │                  │
│                    │  new_weight = old       │                  │
│                    │  + 0.25 × error         │                  │
│                    │                         │                  │
│                    │  → 31 weight updates    │                  │
│                    └────────────┬────────────┘                  │
│                                 │                                │
│                         dna_weight_config.json                  │
│                         (feedback to E9.6)                      │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                            │
┌─────────────────────────────────────────────────────────────────┐
│                    INTELLIGENCE LAYER (E9.4-E9.6)               │
│                                                                 │
│  ┌──────────────────────────┐  ┌──────────────────────────────┐│
│  │  Creative DNA Engine     │  │  Player Intelligence         ││
│  │  (E9.4)                  │  │  (E9.4 + E9.5)               ││
│  │                          │  │                              ││
│  │  Video/Image → DNA       │  │  Events → PlayerDNA          ││
│  │                          │  │    ↓                         ││
│  │  hook, reward, visual,   │  │  BehaviorFeatures (16 dim)   ││
│  │  fantasy, mechanism,     │  │    ↓                         ││
│  │  payment_trigger         │  │  ArchetypeClassifier         ││
│  │                          │  │    ↓                         ││
│  │  1,315 DNA entries       │  │  5 Archetypes:               ││
│  │                          │  │  Power / Collector           ││
│  │                          │  │  Explorer / Progression      ││
│  │                          │  │  / Casual                    ││
│  └────────────┬─────────────┘  └──────────────┬───────────────┘│
│               │                               │                 │
│               │          ┌────────────────────┘                 │
│               │          │                                      │
│               ▼          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Creative Matching Engine (E9.6)                         │  │
│  │                                                          │  │
│  │  DNAFeatureEncoder                                       │  │
│  │  Creative DNA → 10-dim feature vector                    │  │
│  │      ↓                                                   │  │
│  │  ArchetypePredictor                                      │  │
│  │  P(arch|DNA) = 0.8×affinity + 0.2×prior                 │  │
│  │      ↓                                                   │  │
│  │  CreativePrediction + LTV + D30 + Payer Rate             │  │
│  │      ↓                                                   │  │
│  │  Creative Ranking (6 dimensions)                         │  │
│  │                                                          │  │
│  │  Output: 912 predictions, 6 ranking categories           │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                            │
┌─────────────────────────────────────────────────────────────────┐
│                     DATA ASSET LAYER                            │
│                                                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────┐ │
│  │ Facebook Ads │ │ Firebase     │ │ Adjust/      │ │ Game   │ │
│  │ API          │ │ Events       │ │ AppsFlyer    │ │ Backend│ │
│  │              │ │              │ │              │ │        │ │
│  │ 广告表现     │ │ 玩家行为     │ │ 归因数据     │ │ IAP    │ │
│  │ 花费/展示    │ │ 关卡/付费    │ │ 安装来源     │ │ 付费   │ │
│  │ 点击/安装    │ │ 留存/会话    │ │ 广告ID关联   │ │ 商品ID │ │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └───┬────┘ │
│         │                │                │              │      │
│         └────────────────┼────────────────┼──────────────┘      │
│                          │                │                      │
│              ┌───────────┴────────┐ ┌─────┴──────────┐          │
│              │ Campaign          │ │ Player          │          │
│              │ Performance       │ │ Events          │          │
│              │ ltv_d30, retention│ │ session,level,  │          │
│              │ revenue, spend    │ │ purchase,retain │          │
│              └───────────────────┘ └─────────────────┘          │
└─────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════

系统规模: 1,215 files, 232,406 lines of Python
数据资产: 1,315 DNA entries, 500+ player genomes, 912 predictions
学习能力: 31 weight updates per cycle, 1,250 mutations per evolution
闭环状态: E9.4 → E9.5 → E9.6 → E9.7 → E9.8 (完整闭环)
下一阶段: E9.9 Autonomous Experiment Agent
最终目标: E10 AI Game Company Operating System
```

---

*本文档为 AI Game Growth Engine v1.0 系统架构白皮书，随系统演进持续更新。*

---

# 9. 系统边界（System Boundary）

## 9.1 系统负责

```
历史 Creative 分析
        ↓
玩家价值理解（Player Archetype）
        ↓
Creative 预测（Archetype + LTV + Payer Rate）
        ↓
Creative 变异（生成新广告基因）
        ↓
实验假设生成（Top 20 Candidates）
        ↓
反馈学习（预测 vs 实际 → 权重修正）
```

具体能力边界：

| 能力域 | 负责范围 | 版本 |
|--------|---------|------|
| Creative DNA 提取 | 从视频/图片中提取结构化基因 | E9.4 |
| 玩家行为分析 | 从游戏事件中提取16维行为特征 | E9.5 |
| 玩家原型分类 | 5种原型：Power/Collector/Explorer/Progression/Casual | E9.5 |
| 创意-玩家匹配 | 预测新广告吸引什么玩家 | E9.6 |
| 预测反馈学习 | 比较预测与实际，自动修正权重 | E9.7 |
| 创意基因变异 | 基于赢家/失败模式生成新基因 | E9.8 |
| 实验假设生成 | 输出 Top 20 候选供验证 | E9.8 |
| 决策建议输出 | 创意排名、玩家匹配建议 | E9.6 |

## 9.2 系统不负责

```
❌ 游戏客户端开发
❌ UA 账户管理（Facebook/Google Ads 账户创建/配置）
❌ 广告自动投放执行（Facebook Ads API 调用）
❌ 美术生产执行（视频渲染/图片生成）
❌ 人工审核（最终投放决策）
❌ 游戏内经济系统设计
❌ 支付系统对接
❌ 用户隐私合规（GDPR/CCPA）
❌ 实时竞价引擎（RTB）
❌ CDN 分发
```

## 9.3 边界原则

1. **系统输出建议，不自动执行**：E9.8 输出 Top 20 候选，但不自动创建 Facebook Campaign
2. **系统理解创意，不生产创意**：E9.8 生成基因蓝图，不渲染视频
3. **系统学习规律，不替代人类判断**：E9.7 修正权重，但最终投放决策由人类审核
4. **E9.9+ 可扩展至执行层**：但需通过 Human-in-the-loop 审批

---

# 10. 核心对象模型（Core Entity Model）

整个系统围绕 7 个核心对象运转。这是系统设计的基石。

## 10.1 对象关系总览

```
CreativeAsset (原始素材)
        │
        │ 1:1
        ▼
CreativeDNA (素材基因 — E9.4)
        │
        │ 1:1 (E9.6 预测) / 1:N (E9.8 变异)
        ▼
CreativeGenome (下一代基因 — E9.8)
        │
        │ 1:N (每个 Genome 可吸引多种玩家)
        ▼
PlayerArchetype (玩家原型 — E9.5)
        │
        │ 1:1
        ▼
CreativePrediction (预测结果 — E9.6)
        │
        │ 1:1 (预测 vs 实际)
        ▼
PredictionError (预测误差 — E9.7)
        │
        │ N:1 (多个误差汇总)
        ▼
LearningUpdate (权重修正 — E9.7)
        │
        │ 反馈
        ▼
(回到 CreativePrediction，下一轮更准)
```

## 10.2 对象定义

### CreativeAsset（原始素材）

**定位**: 系统最底层的数据单位。  
**来源**: Facebook Ads 历史库、内部素材库。  
**生命周期**: 上传后不可变。  
**关键字段**:

```json
{
  "asset_id": "string",
  "asset_type": "video | image | playable",
  "file_url": "string",
  "duration_seconds": 30,
  "resolution": "1080x1920",
  "created_at": "ISO datetime"
}
```

**代码位置**: 外部数据源，系统内无独立模型（通过 `creative_dna_master.json` 引用）。

---

### CreativeDNA（素材基因）

**定位**: 把 CreativeAsset 翻译成 AI 可理解的"基因"。  
**来源**: E9.4 Creative DNA Engine。  
**生命周期**: 一旦提取，作为历史数据冻结。  
**1:1 关系**: 一个 CreativeAsset 对应一个 CreativeDNA。  
**关键字段**:

```json
{
  "creative_id": "787567970297102",
  "hook": {"type": "emotional", "confidence": 0.85},
  "mechanism": {"type": "merge"},
  "reward": {"type": "discovery", "confidence": 0.80},
  "visual": {"style": "2d_flat", "confidence": 0.90},
  "fantasy": {"drives": ["become_powerful", "collect_dragons"]},
  "psychology": {"type": "curiosity"},
  "payment_trigger": ["rare_item", "time_limited"],
  "retention": {"hooks": ["daily_reward", "progress_save"]}
}
```

**代码位置**: `src/market_ops/creative_analysis/`  
**数据资产**: `output/active/creative_dna_master.json` (1,315 entries)

---

### CreativeGenome（下一代基因）

**定位**: E9.8 变异引擎的输出。从 CreativeDNA 通过变异生成。  
**来源**: E9.8 CreativeGenomeMutator。  
**1:N 关系**: 一个 CreativeDNA 可以变异出多个 CreativeGenome。  
**核心区别**: CreativeDNA 描述"已有广告"，CreativeGenome 描述"应该创造的广告"。  
**关键字段**:

```json
{
  "genome_id": "G001_a1b2c3d4e5f6",
  "generation": 1,
  "hook": "challenge",
  "mechanism": "merge",
  "reward": "collection",
  "fantasy": "become_powerful",
  "visual_style": "2d_flat",
  "target_archetype": "power",
  "target_ltv": 22.3,
  "parent_genome_id": "787567970297102",
  "mutation_type": "hook",
  "created_at": "2026-07-20T12:00:00Z",
  "mutation_round": 1
}
```

**ID 生成规则**: `SHA256(parent_id | mutation_type | before | after | generation)`  
**代码位置**: `src/market_ops/creative_evolution/schemas.py` → `CreativeGenome`

---

### PlayerArchetype（玩家原型）

**定位**: 玩家价值模型。5 种原型的枚举。  
**来源**: E9.5 ArchetypeClassifier。  
**生命周期**: 每次有新玩家数据时重新分类。  
**FROZEN**: 5 种原型不可增删改。  
**枚举值**:

```python
class PlayerArchetype(Enum):
    COLLECTOR = "collector"      # 收藏驱动
    PROGRESSION = "progression"  # 进度驱动
    POWER = "power"              # 强度驱动
    EXPLORER = "explorer"        # 探索驱动
    CASUAL = "casual"            # 休闲
```

**关联对象**: 每个 PlayerGenome 包含一个 `archetype` + `archetype_scores` + `value_segment`。  
**代码位置**: `src/market_ops/player_intelligence/player_genome.py` → `PlayerArchetype`

---

### CreativePrediction（预测结果）

**定位**: E9.6 的输出。一个 CreativeDNA 预测会吸引什么玩家。  
**来源**: E9.6 ArchetypePredictor。  
**1:1 关系**: 一个 CreativeDNA → 一个 CreativePrediction。  
**关键字段**:

```json
{
  "creative_id": "787567970297102",
  "prediction": {
    "power": {"probability": 0.35, "confidence": 0.72},
    "collector": {"probability": 0.20, "confidence": 0.65},
    "explorer": {"probability": 0.28, "confidence": 0.68},
    "progression": {"probability": 0.12, "confidence": 0.60},
    "casual": {"probability": 0.05, "confidence": 0.55}
  },
  "expected": {"ltv": 18.5, "d30": 0.42, "payer_rate": 0.31},
  "confidence": 0.72
}
```

**预测公式**: `P(arch | DNA) = 0.8 × DNA_affinity + 0.2 × prior`  
**代码位置**: `src/market_ops/creative_matching/schemas.py` → `CreativePrediction`  
**数据资产**: `output/creative_matching/creative_prediction.json` (912 entries)

---

### PredictionError（预测误差）

**定位**: E9.7 的核心对象。量化预测与实际之间的差距。  
**来源**: E9.7 PredictionErrorAnalyzer。  
**1:1 关系**: 一个 CreativePrediction vs 一个 CreativeActualPerformance → 一个 PredictionError。  
**关键字段**:

```json
{
  "creative_id": "787567970297102",
  "archetype_errors": {
    "power": {"predicted": 0.35, "actual": 0.25, "absolute_error": 0.10}
  },
  "metric_errors": {
    "ltv": {"predicted": 18.5, "actual": 12.5, "absolute_error": 6.0}
  },
  "archetype_mae": 0.08,
  "ltv_error": 6.0
}
```

**代码位置**: `src/market_ops/creative_learning/schemas.py` → `PredictionError`

---

### LearningUpdate（权重修正）

**定位**: E9.7 的最终输出。从 PredictionError 推导出的权重修正。  
**来源**: E9.7 DNAWeightOptimizer。  
**N:1 关系**: 多个 PredictionError → 汇总 → 一个 LearningUpdate。  
**学习公式**: `new_weight = old_weight + 0.25 × mean_error`  
**关键字段**:

```json
{
  "feature": "emotion_intensity",
  "archetype": "collector",
  "old_weight": 0.58,
  "new_weight": 0.62,
  "delta": 0.037,
  "reason": "emotional hook_type: increased emotion_intensity weight by 0.037"
}
```

**代码位置**: `src/market_ops/creative_learning/schemas.py` → `DNAWeightUpdate`  
**数据资产**: `output/creative_learning/dna_weight_config.json` (31 updates)

---

## 10.3 对象生命周期

```
CreativeAsset ──(E9.4提取)──▶ CreativeDNA ──(E9.6预测)──▶ CreativePrediction
                                                                    │
                                                                    │ (E9.7 对比)
                                                                    ▼
                                                              PredictionError
                                                                    │
                                                                    │ (E9.7 学习)
                                                                    ▼
                                                              LearningUpdate ──▶ (反馈修正 E9.6)
                                                                    
CreativeDNA ──(E9.8 变异)──▶ CreativeGenome ──(E9.6 预测)──▶ CreativePrediction
                                                                    │
                                                                    │ (E9.9 实验)
                                                                    ▼
                                                              ExperimentResult
                                                                    │
                                                                    │ (E9.7 反馈)
                                                                    ▼
                                                              (回到 PredictionError)
```

---

# 11. 数据资产关系图

```
                       Facebook Ads API
                              │
                              ▼
                    ┌─────────────────┐
                    │ Creative Asset  │
                    │ Store           │
                    │ (1,315 videos)  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Creative DNA    │
                    │ Layer (E9.4)    │
                    │                 │
                    │ 1,315 DNA       │
                    │ entries         │
                    └───┬─────────┬───┘
                        │         │
          ┌─────────────┘         └─────────────┐
          │                                     │
          ▼                                     ▼
┌─────────────────┐                   ┌─────────────────┐
│ Player          │                   │ Creative        │
│ Intelligence    │                   │ Intelligence    │
│ (E9.5)          │                   │ (E9.6)          │
│                 │                   │                 │
│ 500 player      │                   │ 912 predictions │
│ genomes         │                   │ 6 ranking dims  │
└────────┬────────┘                   └────────┬────────┘
         │                                     │
         │ Creative-Archetype                  │ CreativePrediction
         │ Matrix (JSON)                       │ (JSON)
         │                                     │
         └──────────────┬──────────────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │ Learning Loop   │
              │ (E9.7)          │
              │                 │
              │ 31 weight       │
              │ updates         │
              └────────┬────────┘
                       │
                       │ dna_weight_config.json
                       │
                       ▼
              ┌─────────────────┐
              │ Mutation Engine │
              │ (E9.8)          │
              │                 │
              │ 1,250 new       │
              │ genomes         │
              └────────┬────────┘
                       │
                       │ Top 20 Candidates
                       │
                       ▼
              ┌─────────────────┐
              │ Experiment      │
              │ Layer (E9.9+)   │
              │                 │
              │ A/B Test        │
              │ Results         │
              └────────┬────────┘
                       │
                       │ Feedback
                       │
                       ▼
              (回到 Learning Loop)
```

**数据资产文件清单**:

| 文件 | 层 | 条目数 | 大小 | 不可变性 |
|------|-----|--------|------|---------|
| `creative_dna_master.json` | DNA | 1,315 | 2.1 MB | 只追加 |
| `player_genomes.json` | Player | 500 | 694 KB | 可重算 |
| `creative_archetype_matrix.json` | Matrix | 912 | 59 KB | 可重算 |
| `creative_prediction.json` | Prediction | 912 | 2.9 MB | 快照 |
| `prediction_history.json` | Learning | 912 | 1.1 MB | 不可变 |
| `actual_performance.json` | Learning | 912 | 423 KB | 只追加 |
| `prediction_error_report.json` | Learning | 912 | 1.7 MB | 可重算 |
| `dna_weight_config.json` | Learning | 31 | 8.8 KB | 可覆盖 |
| `mutation_candidates.json` | Evolution | 1,250 | 1.5 MB | 快照 |
| `top_mutations.json` | Evolution | 20 | 22 KB | 快照 |
| `evolution_report.json` | Evolution | 1 | 29 KB | 快照 |

---

# 12. 模块依赖规则

## 12.1 层级依赖约束

```
┌──────────────────────────────────────────────┐
│              Evolution Layer (E9.8)          │
│                                              │
│  允许: 读取 Intelligence 层输出 (JSON)        │
│  允许: 调用 E9.6 Predictor (预测新基因)       │
│  禁止: 修改 Data Layer 原始数据               │
│  禁止: 直接修改 E9.6 模型权重                 │
│  禁止: 调用 Decision Layer                   │
└──────────────────────┬───────────────────────┘
                       │ 单向依赖
                       ▼
┌──────────────────────────────────────────────┐
│              Learning Layer (E9.7)           │
│                                              │
│  允许: 读取 Intelligence 层输出 (JSON)        │
│  允许: 调用 E9.6 Predictor (重新预测)         │
│  允许: 输出 dna_weight_config.json           │
│  禁止: 修改 Data Layer 原始数据               │
│  禁止: 调用 Evolution Layer                  │
└──────────────────────┬───────────────────────┘
                       │ 单向依赖
                       ▼
┌──────────────────────────────────────────────┐
│            Intelligence Layer (E9.4-E9.6)    │
│                                              │
│  允许: 读取 Data Layer 数据 (JSON)            │
│  允许: 输出预测结果                           │
│  允许: 加载 E9.7 权重 (set_weights)           │
│  禁止: 修改数据源文件                         │
│  禁止: 调用 Learning/Evolution Layer         │
└──────────────────────┬───────────────────────┘
                       │ 单向依赖
                       ▼
┌──────────────────────────────────────────────┐
│              Data Asset Layer                │
│                                              │
│  只做: Collect → Normalize → Store           │
│  禁止: 调用任何上层                           │
│  禁止: 内置预测/决策逻辑                      │
└──────────────────────────────────────────────┘
```

## 12.2 实际模块依赖矩阵

```
                    被依赖方
                player_    creative_  creative_  creative_
                 intel     matching   learning   evolution
依赖方
player_intel       ✓           ✗          ✗          ✗
creative_matching  ✗(JSON)     ✓          ✗          ✗
creative_learning  ✗           ✓(延迟)     ✓          ✗
creative_evolution ✗           ✓(延迟)     ✗          ✓

✓  = 直接 import
✗  = 禁止 import
JSON = 通过 JSON 文件间接读取（解耦）
延迟 = 延迟 import（在方法内部，非模块顶层）
```

**关键设计决策**:

1. `creative_matching` 不直接 import `player_intelligence`，而是通过 `creative_archetype_matrix.json` 读取 E9.5 输出。**解耦**。
2. `creative_learning` 和 `creative_evolution` 都通过延迟 import 调用 `creative_matching` 的预测器。**避免循环依赖**。
3. 没有任何下层模块调用上层模块。**单向依赖**。

## 12.3 违规范例

以下模式**禁止**出现在代码中：

```python
# ❌ 禁止：Learning Layer 调用 Evolution Layer
from market_ops.creative_evolution import EvolutionEngine

# ❌ 禁止：Intelligence Layer 修改数据源
with open('creative_dna_master.json', 'w') as f:  # 写入

# ❌ 禁止：Evolution Layer 直接修改 E9.6 权重
predictor._weights['power']['emotion_intensity'] = 0.5

# ❌ 禁止：Data Layer 调用任何上层
from market_ops.creative_matching import ArchetypePredictor
```

---

# 13. 当前系统能力矩阵

| 能力域 | 版本 | 模块 | 状态 | 验收 |
|--------|------|------|------|------|
| Creative DNA 提取 | V3.5 | `creative_analysis/` | DONE | 1,315 entries |
| Creative 排名 | V4.2 | `creative_ranking/` | DONE | 6 排名维度 |
| Creative 增长决策 | V4.5 | `creative_decision/` | DONE | — |
| Creative 工厂 | V4.6 | `creative_factory/` | DONE | — |
| 创意进化框架 | V5.0 | `v5_evolution/` | DONE | 535/535 回归 |
| 玩家价值归因 | E9.4 | `player_intelligence/` | DONE | 500 player genomes |
| 玩家原型分类 | E9.5 | `player_intelligence/` | DONE | 5 archetypes, 16 features |
| 创意-玩家匹配 | E9.6 | `creative_matching/` | DONE | 912 predictions |
| 预测反馈学习 | E9.7 | `creative_learning/` | DONE | 31 weight updates |
| 创意基因变异 | E9.8 | `creative_evolution/` | DONE | 1,250 candidates, 5 mutation types |
| 实验自动化 | E9.9 | — | PLANNING | 待设计 |
| UA 反馈自动化 | E10 | — | PLANNING | 待设计 |
| 游戏公司OS | E10+ | — | VISION | 待设计 |

---

# 14. E9.8 之后系统状态

## 14.1 系统性质变化

```
E9.7 之前：

    AI 分析系统
    ┌─────────────┐
    │ 分析历史广告  │
    │ 预测广告效果  │
    │ 输出报告     │
    └─────────────┘
    角色：AI Analyst


E9.8 之后：

    AI Creative Growth Agent
    ┌─────────────────────────┐
    │ 分析历史广告 → 理解玩家   │
    │ 预测新广告 → 投放验证    │
    │ 发现误差 → 自动修正      │
    │ 发现机会 → 生成新广告    │
    │ 下一轮 → 更准           │
    └─────────────────────────┘
    角色：AI Growth Agent
```

## 14.2 能力变化

| 维度 | 以前 (E9.6) | 现在 (E9.8) |
|------|------------|------------|
| 分析能力 | 告诉人"哪个广告好" | 自己发现"哪里有机会" |
| 预测能力 | 预测已有广告效果 | 预测新基因效果 |
| 创造能力 | 无 | 自动生成 1,250 个新广告基因 |
| 学习能力 | 无 | 31 条权重自动修正 |
| 闭环 | 开放 | 完整闭环：预测→变异→实验→反馈 |
| 自主性 | 0（完全依赖人类输入） | Level 2（辅助决策） |

## 14.3 系统定位

当前系统不是普通的"AI素材分析工具"。

**准确定位**：

> **面向 IAA 游戏增长的 Creative Intelligence Operating System**

**核心资产（非代码）**：

1. **Creative DNA Database** — 1,315 条结构化创意基因
2. **Player Archetype Model** — 5 种玩家原型分类器
3. **Prediction Model** — 贝叶斯混合预测器
4. **Evolution Engine** — 基于赢家/失败模式的变异引擎
5. **Learning Loop** — 预测→实际→误差→修正的闭环

---

# 15. 下一阶段 E9.9 定义

## 15.1 E9.9 定位

E9.8 解决了"生成什么"（What to create）。  
E9.9 需要解决"怎么验证"（How to validate）。

## 15.2 E9.9 Experiment Intelligence Engine

**目标**：连接 E9.8 的 Top 20 候选到实际投放验证。

**Pipeline**：

```
E9.8 Top 20 Candidates
        │
        ▼
Experiment Planner
  设计实验方案
  (A/B 分组、预算分配、时长)
        │
        ▼
Test Allocator
  分配测试预算
  (小预算起步，胜出者放量)
        │
        ▼
Hypothesis Engine
  生成可验证假设
  ("challenge hook 的 Power 型 LTV > emotional hook")
        │
        ▼
Experiment Tracker
  追踪实验状态
  (RUNNING → COLLECTING → COMPLETE)
        │
        ▼
Result Analyzer
  分析实验结果
  (胜出者/失败者/统计显著性)
        │
        ▼
E9.7 Feedback Loop
  反馈学习 → 更新权重
```

## 15.3 核心模块设计

| 模块 | 文件 | 职责 |
|------|------|------|
| ExperimentPlanner | `experiment_planner.py` | 设计实验方案（A/B 分组、预算、时长） |
| TestAllocator | `test_allocator.py` | 预算分配（小预算→胜出→放量） |
| HypothesisEngine | `hypothesis_engine.py` | 生成可验证的因果假设 |
| ExperimentTracker | `experiment_tracker.py` | 状态机：PENDING→RUNNING→COLLECTING→COMPLETE |
| ResultAnalyzer | `result_analyzer.py` | 统计显著性、胜出者/失败者判定 |

## 15.4 E9.9 输入/输出

**输入**：
- E9.8 `top_mutations.json` (Top 20 candidates)
- E9.6 `creative_prediction.json` (预测 LTV/archetype)
- 历史表现数据 (baseline 对比)

**输出**：
- `experiment_plan.json` (实验方案)
- `experiment_results.json` (实验结果)
- `hypothesis_report.json` (假设验证报告)
- → 反馈给 E9.7 Learning Loop

## 15.5 E9.9 验收标准

| 标准 | 目标 |
|------|------|
| AC1 | 支持 2-4 组 A/B 测试设计 |
| AC2 | 自动预算分配（小预算→胜出放量） |
| AC3 | 生成 5+ 可验证假设 |
| AC4 | 实验结果闭环反馈给 E9.7 |
| AC5 | 完整实验状态机：PENDING→RUNNING→COLLECTING→COMPLETE |

---

# 16. 架构冻结声明

## 16.1 冻结范围

以下内容已冻结，后续开发只能扩展不能破坏：

| 冻结项 | 版本 | 变更规则 |
|--------|------|---------|
| 5 层架构模型 | v1.0 | 不可增删层 |
| 7 个核心对象 | v1.0 | 字段可追加，不可删除/重命名 |
| 5 种 PlayerArchetype | v1.0 | 不可增删改 |
| 10 维 DNAFeatureVector | v1.0 | 核心字段不可删 |
| 模块依赖规则 | v1.0 | 单向依赖，不可逆 |
| CreativePrediction 输出格式 | v1.0 | JSON Schema 向后兼容 |
| mutation_hash 生成算法 | v1.0 | SHA256 确定性 |
| E9.6 → E9.7 → E9.8 接口 | v1.0 | 通过 JSON 文件解耦 |

## 16.2 冻结原则

1. **上层调用下层，不可逆**
2. **跨层数据流通过 JSON 文件，非直接 import**
3. **所有新增能力必须挂载在现有 5 层架构上**
4. **新模块必须先定义 Schema，再实现代码**
5. **所有 API 接口必须向后兼容**

---

## 附录：文档索引

| 文档 | 内容 | 路径 |
|------|------|------|
| 架构白皮书 (本文档) | 系统全貌、流程、对象模型、依赖规则 | `specs/AI_GAME_GROWTH_ENGINE_ARCHITECTURE.md` |
| 架构规范 | 4层模型、冻结范围、E9.8入口 | `specs/E9_ARCHITECTURE_V1.md` |
| 模块契约 | 每个模块的接口签名、冻结等级 | `specs/E9_MODULE_CONTRACTS.md` |
| 数据流规范 | 完整数据流、Schema示例、数据量 | `specs/E9_DATA_FLOW.md` |
| 路线图 | 版本演进、已完成/规划中、技术债务 | `specs/E9_ROADMAP.md`