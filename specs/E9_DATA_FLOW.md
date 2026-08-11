# AI Creative Growth OS v1.0 — Data Flow Specification

**Version**: 1.0  
**Date**: 2026-07-20  
**Status**: FROZEN  
**Depends on**: [E9_ARCHITECTURE_V1.md](./E9_ARCHITECTURE_V1.md), [E9_MODULE_CONTRACTS.md](./E9_MODULE_CONTRACTS.md)

---

# 1. 数据流全景

## 1.1 完整闭环

```
                          Data Asset Layer
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
    Creative Assets      Player Events         Campaign Data
    (Video/Image)        (Firebase/Adjust)     (Facebook Ads)
          │                     │                     │
          ▼                     ▼                     │
    Creative DNA           PlayerDNA                  │
    (E9.4)                 (E9.4)                     │
          │                     │                     │
          │                     ▼                     │
          │              BehaviorFeatures             │
          │              (E9.5)                       │
          │                     │                     │
          │                     ▼                     │
          │              PlayerGenome                  │
          │              (E9.5)                       │
          │                     │                     │
          │           ┌─────────┴─────────┐           │
          │           │                   │           │
          │           ▼                   ▼           │
          │    Player Archetypes    Creative-         │
          │    (5 types)           Archetype Matrix   │
          │                        (E9.5)             │
          │                           │               │
          ├───────────────────────────┘               │
          │                                           │
          ▼                                           │
    DNAFeatureVector                                  │
    (E9.6: 10 features)                              │
          │                                           │
          ▼                                           │
    ArchetypePredictor                                │
    (E9.6: Rule + Bayesian)                          │
          │                                           │
          ▼                                           │
    CreativePrediction                                │
    {arch_dist, LTV, D30, payer_rate}                │
          │                                           │
          ├───────────────────────────────────────────┘
          │
          ▼
    PredictionTracker
    (E9.7: Save snapshot)
          │
          ├──────────────────┐
          │                  │
          ▼                  ▼
    PerformanceCollector  ArchetypeReconstruction
    (Mock or Real)        (E9.5 re-run on real data)
          │                  │
          └────────┬─────────┘
                   │
                   ▼
            PredictionErrorAnalyzer
            {archetype_error, metric_error}
                   │
                   ▼
            DNAWeightOptimizer
            {weight_updates}
                   │
          ┌────────┴────────┐
          │                 │
          ▼                 ▼
    DNAWeightConfig    LearningReport
    (Feedback to E9.6) (Human review)
          │
          ▼
    ArchetypePredictor.set_weights()
    (Next prediction cycle)
```

## 1.2 数据流向规则

```
Data Asset Layer ──raw──▶ Intelligence Layer ──prediction──▶ Decision Layer
                                    ▲                            │
                                    │                            │
                                    └──── feedback ──────────────┘
                                            (E9.7)
```

---

# 2. 逐层数据流

## 2.1 Data Asset → Intelligence

### 2.1.1 Creative Assets → Creative DNA

```
源: Creative Assets (Video/Image files)
     ↓
处理: Creative DNA Engine (E9.4)
     ↓
输出: creative_dna_master.json
     ↓
格式: [{creative_id, hook, mechanism, reward, fantasy, visual_style, ...}]
```

**数据量**: 912 entries (当前)

### 2.1.2 Player Events → PlayerDNA

```
源: Firebase Events / Adjust Attribution
     ↓
处理: PlayerDNAEngine.extract_all()
     ↓
输出: {player_id: PlayerDNA}
     ↓
PlayerDNA:
  player_id: str
  creative_id: str
  progression_dna: {merge_count, level, areas, speed}
  collection_dna: {items, rare_items, collections_completed}
  payment_dna: {total_spend, purchase_count, first_purchase}
  retention_dna: {d7, d30, sessions}
```

### 2.1.3 Campaign Data → Performance

```
源: Facebook Ads API
     ↓
处理: PerformanceCollector (CSV/JSON/API)
     ↓
输出: CreativeActualPerformance
     ↓
{creative_id, installs, spend, revenue, ltv_d30, payer_rate, ...}
```

---

## 2.2 Intelligence Layer 内部

### 2.2.1 E9.5: PlayerDNA → PlayerGenome

```
Step 1: PlayerDNAEngine.extract_all(events)
  Input:  [PlayerEvent] (raw events from Firebase/Adjust)
  Output: {player_id: PlayerDNA}

Step 2: BehaviorFeatureEngine.extract_all(dna_map, events_by_player)
  Input:  {player_id: PlayerDNA}, {player_id: [PlayerEvent]}
  Output: {player_id: BehaviorFeatures}
  Features: 16 dimensions, 0-1 normalized

Step 3: ArchetypeClassifier.classify_all(dna_map, features_map)
  Input:  {player_id: PlayerDNA}, {player_id: BehaviorFeatures}
  Output: [PlayerGenome]
  Each: {player_id, archetype, value_segment, payment_profile}

Step 4: Creative-Archetype Matrix
  Input:  [PlayerGenome] grouped by creative_id
  Output: creative_archetype_matrix.json
  Format: {creative_id: {archetype: count}}
```

### 2.2.2 E9.6: Creative DNA → Prediction

```
Step 1: DNAFeatureEncoder.encode(creative_dna)
  Input:  {hook, mechanism, reward, fantasy, visual_style, ...}
  Output: DNAFeatureVector
  Features: 10 numeric dimensions (0-1)

Step 2: CreativeArchetypeProfileDB.load()
  Input:  creative_archetype_matrix.json
  Output: priors, archetype_metrics, baseline_ltv

Step 3: ArchetypePredictor.predict(feature_vector)
  Input:  DNAFeatureVector + priors
  Formula: P(arch | DNA) = 0.8 × DNA_affinity + 0.2 × prior
  Output: ArchetypePrediction

Step 4: MatchingEngine.rank()
  Input:  [ArchetypePrediction]
  Output: creative_prediction.json + creative_archetype_rank.json
```

### 2.2.3 E9.7: Prediction → Feedback

```
Step 1: PredictionTracker.load_predictions()
  Input:  creative_prediction.json (from E9.6)
  Output: [PredictionRecord] (frozen snapshot)
  File:   prediction_history.json

Step 2: PerformanceCollector / MockPerformanceGenerator
  Input:  creative_prediction.json (for mock: 9 bias types)
  Output: [CreativeActualPerformance]
  File:   actual_performance.json

Step 3: ArchetypeReconstructionEngine.reconstruct_from_performances()
  Input:  {creative_id: CreativeActualPerformance}
  Output: {creative_id: {archetype: proportion}}
  Note:   In mock mode, extracts from pre-computed distributions.
          In real mode, re-runs full E9.5 pipeline on player events.

Step 4: PredictionErrorAnalyzer.compare()
  Input:  predictions + actuals
  Output: {creative_id: PredictionError}
  Each:   archetype_errors + metric_errors + mae + ltv_error
  File:   prediction_error_report.json

Step 5: DNAWeightOptimizer.optimize()
  Input:  errors + predictions + actuals
  Process: Group errors by DNA feature → adjust weights
  Output: DNAWeightConfig (31 weight updates)
  Formula: new_weight = old_weight + 0.25 × mean_error
  File:   dna_weight_config.json

Step 6: LearningEngine.build_learning_report()
  Input:  errors + weight_config + re_predictions
  Output: LearningReport
  File:   learning_report.json
```

---

## 2.3 Feedback Loop: E9.7 → E9.6

```
DNAWeightConfig.weights
    ↓
ArchetypePredictor.set_weights(weights)
    ↓
Next prediction uses updated weights
    ↓
Prediction error decreases (measured in LearningReport)
```

---

# 3. 关键数据 Schema

## 3.1 Creative Prediction (E9.6 → E9.7)

```json
{
  "creative_id": "787567970297102",
  "creative_genome_name": "merge_challenge_power_001",
  "prediction": {
    "power": {
      "raw_affinity": 0.52,
      "adjusted_probability": 0.45,
      "confidence": 0.72
    },
    "collector": {
      "raw_affinity": 0.18,
      "adjusted_probability": 0.15,
      "confidence": 0.65
    },
    "explorer": {
      "raw_affinity": 0.30,
      "adjusted_probability": 0.28,
      "confidence": 0.68
    },
    "progression": {
      "raw_affinity": 0.12,
      "adjusted_probability": 0.10,
      "confidence": 0.60
    },
    "casual": {
      "raw_affinity": 0.02,
      "adjusted_probability": 0.02,
      "confidence": 0.55
    }
  },
  "expected": {
    "ltv": 18.5,
    "d30": 0.42,
    "payer_rate": 0.31
  },
  "confidence": 0.72,
  "dna_features": {
    "features": {
      "collection_strength": 0.15,
      "progression_strength": 0.22,
      "power_expression": 0.45,
      "exploration_strength": 0.28
    },
    "source_dna": {
      "hook": "challenge",
      "mechanism": "merge",
      "reward": "dragon",
      "fantasy": "become_powerful",
      "visual_style": "2d_flat"
    }
  }
}
```

## 3.2 Prediction Error (E9.7 internal)

```json
{
  "creative_id": "787567970297102",
  "creative_genome_name": "merge_challenge_power_001",
  "archetype_errors": {
    "power": {
      "archetype": "power",
      "predicted": 0.45,
      "actual": 0.30,
      "absolute_error": 0.15,
      "relative_error": -0.33
    }
  },
  "metric_errors": {
    "ltv": {
      "metric": "ltv",
      "predicted": 18.5,
      "actual": 12.5,
      "absolute_error": 6.0,
      "relative_error": -0.32
    }
  },
  "archetype_mae": 0.08,
  "metric_mae": 4.2,
  "ltv_error": 6.0
}
```

## 3.3 DNA Weight Update (E9.7 → E9.6)

```json
{
  "version": "1.0",
  "updated_at": "2026-07-20T11:00:00Z",
  "weights": {
    "power": {
      "emotion_intensity": 0.48,
      "reward_value": 0.52,
      "novelty_score": 0.35
    },
    "collector": {
      "emotion_intensity": 0.62,
      "collection_strength": 0.55
    }
  },
  "updates": [
    {
      "feature": "emotion_intensity",
      "archetype": "collector",
      "old_weight": 0.58,
      "new_weight": 0.62,
      "delta": 0.037,
      "reason": "emotional hook_type: increased emotion_intensity weight by 0.037 (mean_error=0.148)"
    }
  ]
}
```

---

# 4. 数据量统计

## 4.1 当前生产数据（Mock 模式）

| 数据实体 | 数量 | 文件大小 |
|---------|------|---------|
| Creative DNA (master) | 912 | ~2.9 MB |
| Creative Predictions | 912 | ~2.9 MB |
| Prediction History | 912 | ~1.1 MB |
| Actual Performances | 912 | ~0.4 MB |
| Prediction Errors | 912 | ~1.7 MB |
| Weight Updates | 31 | ~8.8 KB |
| Learning Report | 1 | ~4.0 KB |

## 4.2 目标生产数据（Real 模式）

| 数据实体 | 目标量 |
|---------|--------|
| Player Events | 10,000+ players, 1M+ events |
| Player Genomes | 10,000+ |
| Creative DNA | 1,000+ |
| Campaign Performance | 100+ campaigns |
| Weight Updates per cycle | 10-50 |

---

# 5. 数据新鲜度

| 数据层 | 更新频率 | 延迟 |
|--------|---------|------|
| Creative Assets | On upload | 实时 |
| Facebook Ads Data | Daily pull | T+1 |
| Adjust Attribution | Real-time | < 1h |
| Firebase Events | Real-time | < 5min |
| E9.5 Player Classification | On demand | 批处理 |
| E9.6 Creative Prediction | On demand | 批处理 |
| E9.7 Feedback Learning | Weekly cycle | T+7 |

---

# 6. 数据一致性保证

1. **Creative ID** 贯穿全链路，作为唯一关联键
2. **PredictionRecord** 是时间点快照，不可变（immutable）
3. **DNAFeatureVector** 10 维度确保前后版本可比
4. **mutation_hash** 使用 SHA256 确定性生成，确保可复现
5. **correlation_id** 单次运行贯穿所有阶段，用于 traceability

---

# 7. 数据流入出口

## 7.1 入口（External → System）

```
Facebook Ads API    → PerformanceCollector
Adjust API          → PlayerEvent (attribution)
Firebase Export     → PlayerEvent (behavior)
Creative Assets     → Creative DNA Engine
Game Backend        → IAP / Revenue
```

## 7.2 出口（System → External）

```
creative_prediction.json     → Human / Dashboard
creative_archetype_rank.json → Human / Dashboard
learning_report.json         → Human / Decision Maker
dna_weight_config.json       → E9.6 Predictor (internal feedback)
prediction_error_report.json → Human / Debug
```

## 7.3 未来出口（E9.8+）

```
Creative Mutation Engine     → Lovart / AI Generation API
UA Decision Engine           → Facebook Ads API
Experiment Engine            → Facebook Ads API (A/B test)
```