# AI Creative Growth Operating System v1.0

## E9 Architecture Specification

**Version**: 1.0  
**Date**: 2026-07-20  
**Status**: FROZEN — 基线架构，后续开发仅可在本框架内扩展  
**Scope**: E9.4 ~ E9.7 完整闭环 + E9.8+ Evolution Layer 入口

---

# 1. 系统定位

## 1.1 定义

> 一个基于 Creative DNA、Player Archetype、Performance Feedback 的自主广告创意进化系统。

## 1.2 核心能力环

```
Understand → Predict → Execute → Learn → Evolve
    │           │          │         │         │
    │           │          │         │         │
  E9.5        E9.6       (E9.8+)    E9.7     (E9.8+)
 理解玩家     预测玩家    自动执行    学习反馈    自动进化
```

## 1.3 与普通分析工具的本质区别

| 维度 | 普通分析工具 | AI Creative Growth OS |
|------|------------|----------------------|
| 输入 | 上传广告 | 历史广告数据库 |
| 过程 | 分析报告 | 学习DNA → 理解玩家 → 预测 → 投放反馈 → 自动修正 |
| 输出 | 静态报告 | 持续进化的预测模型 |
| 反馈 | 无 | 闭环自修正 |
| 性质 | 工具 | Agent |

---

# 2. 总体架构

## 2.1 四层模型

```
                     AI Creative Growth OS v1.0


┌─────────────────────────────────────────────────────────┐
│                  Evolution Layer                        │
│                                                         │
│  Creative Mutation Engine    (E9.8)                     │
│  Experiment Engine           (E9.8)                     │
│  Winner Evolution            (E9.8)                     │
│  Autonomous Optimization     (E9.9)                     │
│                                                         │
│  回答: 如何自动创造下一代更好的广告？                        │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ 进化指令
                          │
┌─────────────────────────────────────────────────────────┐
│                  Decision Layer                         │
│                                                         │
│  Creative Ranking             (E9.6)                    │
│  Audience Matching            (E9.6)                    │
│  Budget Allocation           (E9.8+)                   │
│  UA Decision Engine          (E9.8+)                   │
│                                                         │
│  回答: 哪个素材值得投？投给谁？投多少？                       │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ 决策依据
                          │
┌─────────────────────────────────────────────────────────┐
│                 Intelligence Layer                      │
│                                                         │
│  Creative DNA Engine           (E9.4)                   │
│  Player Intelligence           (E9.5)                   │
│  Archetype Prediction          (E9.6)                   │
│  LTV Prediction                (E9.6)                   │
│  Feedback Learning             (E9.7)                   │
│                                                         │
│  回答: 这个广告吸引谁？值多少钱？预测错了怎么修正？            │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ 原始数据
                          │
┌─────────────────────────────────────────────────────────┐
│                   Data Asset Layer                      │
│                                                         │
│  Facebook Ads Data                                       │
│  Adjust / AppsFlyer Attribution                          │
│  Firebase / Game Events                                 │
│  Google Play / App Store                                │
│  Creative Assets (Video / Image)                        │
│  Revenue / IAP Data                                     │
│                                                         │
│  回答: 系统中有什么数据可用？                                │
└─────────────────────────────────────────────────────────┘
```

## 2.2 层级依赖规则

```
上层可以调用下层
下层不能调用上层
同层模块通过 EventBus 通信
跨层数据流必须通过标准化 Schema
```

---

# 3. Data Asset Layer（数据资产层）

## 3.1 职责

> 提供所有 AI 学习所需的原始数据资产。

**只做**：Collect → Normalize → Store  
**不做**：Prediction / Decision / Optimization

## 3.2 数据源

| 数据源 | 提供内容 | 接入方式 |
|--------|---------|---------|
| Facebook Ads API | 广告表现、花费、展示、点击 | Meta Ads API |
| Adjust / AppsFlyer | 归因数据、安装来源 | Attribution API |
| Firebase / Game Backend | 玩家行为、关卡进度、付费事件 | Event Export |
| Google Play / App Store | 市场数据、评分、排名 | Store API |
| Creative Assets | 视频、图片素材文件 | 内部素材库 |
| IAP Data | 付费金额、付费时间、商品ID | Game Backend |

## 3.3 标准化实体

```python
# 统一数据实体
CreativeEntity    # 创意素材统一模型
PlayerEntity      # 玩家统一模型
PerformanceEntity # 广告表现统一模型
MarketEntity      # 市场数据统一模型
```

---

# 4. Intelligence Layer（智能层）

> 整个系统的大脑。负责理解、预测、学习。

## 4.1 Creative DNA Engine（E9.4）

**回答**：这个广告的基因是什么？

**输入**：
- Video/Image 素材
- 元数据（时长、分辨率、文件名）
- 历史表现数据

**输出**：
```
Creative DNA:
  hook: challenge              # 钩子类型
  mechanism: merge             # 核心机制
  reward: dragon               # 奖励类型
  fantasy: become_powerful     # 幻想驱动
  psychology: competition      # 心理驱动
  visual_style: 2d_flat        # 视觉风格
  payment_triggers: [...]      # 付费触发点
  retention_hooks: [...]       # 留存钩子
```

**代码位置**：`src/market_ops/creative_analysis/`

## 4.2 Player Intelligence（E9.5）

**回答**：这个玩家是什么类型？为什么喜欢这个广告？

**Pipeline**：
```
PlayerEvent (raw)
    ↓
PlayerDNAEngine.extract_all()
    ↓
{player_id: PlayerDNA}
    ↓
BehaviorFeatureEngine.extract_all()
    ↓
{player_id: BehaviorFeatures}  (16 features, 0-1 normalized)
    ↓
ArchetypeClassifier.classify_all()
    ↓
[PlayerGenome]  (5 archetypes)
```

**5 种玩家原型**：

| Archetype | 特征 | 付费驱动 |
|-----------|------|---------|
| Power | 高等级、稀有物品、升级 | 强度提升 |
| Collector | 高收集率、完成度、稀有物品 | 收藏完成 |
| Explorer | 区域解锁、活动参与、剧情 | 新内容解锁 |
| Progression | 快速升级、合并深度、关卡推进 | 进度加速 |
| Casual | 低参与度、随机模式 | 便利性 |

**代码位置**：`src/market_ops/player_intelligence/`

## 4.3 Creative Matching & Prediction（E9.6）

**回答**：一个新广告上线前，会吸引什么玩家？预期 LTV 是多少？

**Pipeline**：
```
Creative DNA
    ↓
DNAFeatureEncoder.encode()
    ↓
DNAFeatureVector (10 features, 0-1 normalized)
    ↓
ArchetypePredictor.predict()
    ↓
CreativePrediction:
  - archetype_distribution: {power: 0.35, explorer: 0.28, ...}
  - expected_ltv: $18.5
  - expected_d30: 0.42
  - expected_payer_rate: 0.31
  - confidence: 0.72
```

**预测公式**：
```
P(arch | DNA) = 0.8 × DNA_affinity + 0.2 × prior
```
（贝叶斯混合：DNA 特征亲和力 + 市场先验分布）

**代码位置**：`src/market_ops/creative_matching/`

## 4.4 Feedback Learning（E9.7）

**回答**：如果预测错了，系统怎么自己修正？

**Pipeline**：
```
E9.6 Prediction
    ↓
PredictionTracker (保存预测快照)
    ↓
PerformanceCollector (收集真实表现)
    ↓
ArchetypeReconstructionEngine (重新运行E9.5分类器)
    ↓
PredictionErrorAnalyzer (计算预测误差)
    ↓
DNAWeightOptimizer (学习权重调整)
    ↓
LearningReport (学习报告)
    ↓
更新 ArchetypePredictor 权重
```

**学习公式**：
```
new_weight = old_weight + learning_rate × error
```

**代码位置**：`src/market_ops/creative_learning/`

---

# 5. Decision Layer（决策层）

> 根据 Intelligence 层输出，做业务决策。

## 5.1 Creative Ranking（E9.6）

**回答**：哪个素材值得测试？

**6 个排名维度**：
1. Archetype Match Score — 与目标玩家类型匹配度
2. LTV Score — 预期生命周期价值
3. Payer Rate Score — 预期付费率
4. Novelty Score — 新颖度
5. Diversity Score — 与现有素材差异度
6. Composite Score — 综合得分

**输出**：`creative_archetype_rank.json`

## 5.2 Audience Matching（E9.6）

**回答**：这个素材应该投给谁？

```
Creative A:
  → Target: Power Users (45% match)
  → Secondary: Explorer Users (28% match)
```

## 5.3 UA Decision（E9.8+）

**未来**：连接 Facebook API / Google Ads API，自动执行：
- Budget Increase / Decrease / Stop
- Creative Scaling
- Audience Expansion

---

# 6. Evolution Layer（进化层）

> E9.8+ — 从"预测"升级到"创造"。

## 6.1 闭环

```
Winner Creative
      ↓
DNA Extraction       (提取胜利基因)
      ↓
Mutation             (基因变异)
      ↓
New Creative DNA     (新广告基因)
      ↓
Prediction           (E9.6 预测)
      ↓
Generation           (E9.8 生成)
      ↓
Testing              (投放测试)
      ↓
Learning             (E9.7 反馈)
      ↓
(回到 Winner Creative)
```

## 6.2 E9.8 入口：Creative Mutation Engine

**输入**：
- Winner DNA
- Prediction
- Historical Failure

**输出**：
- New Creative DNA（变异后的新基因）

**变异操作**：
- Gene Mutation（单基因替换）
- Structural Mutation（插入/删除基因）
- Cross-over（基因交叉）

---

# 7. 当前版本冻结状态

## 7.1 已完成模块

| 版本 | 模块 | 状态 | 代码位置 |
|------|------|------|---------|
| E9.4 | Creative DNA Engine | DONE | `creative_analysis/` |
| E9.4 | Player Value Attribution | DONE | `player_intelligence/` |
| E9.5 | Player Archetype Classification | DONE | `player_intelligence/` |
| E9.6 | Creative DNA → Archetype Prediction | DONE | `creative_matching/` |
| E9.7 | Prediction Feedback Learning | DONE | `creative_learning/` |

## 7.2 冻结范围

以下内容**禁止修改**（只能扩展，不能破坏兼容性）：

| 冻结项 | 版本 | 说明 |
|--------|------|------|
| PlayerArchetype 枚举 | v1.0 | 5 种类型不可增删改 |
| DNAFeatureVector 10 维度 | v1.0 | 字段不可删，可追加 |
| CreativePrediction 输出格式 | v1.0 | JSON Schema 不可变 |
| PredictionRecord 快照格式 | v1.0 | 向后兼容 |
| mutation_hash 生成算法 | v1.0 | SHA256 确定性生成 |
| PlayerDNA Schema | v1.0 | 核心字段不可变 |

---

# 8. 核心契约

## 8.1 Creative DNA Contract

任何模块不能直接修改 Creative DNA Schema，只能 extend。

## 8.2 Archetype Contract

固定 5 种原型：Power / Collector / Explorer / Progression / Casual。  
新增类型需要重新训练整个分类器。

## 8.3 Prediction Contract

统一输出格式：

```json
{
  "creative_id": "string",
  "archetype_distribution": {
    "power": 0.35,
    "collector": 0.15,
    "explorer": 0.28,
    "progression": 0.17,
    "casual": 0.05
  },
  "expected_ltv": 18.5,
  "expected_d30": 0.42,
  "expected_payer_rate": 0.31,
  "confidence": 0.72
}
```

## 8.4 Feedback Contract

误差计算必须包含：
- Archetype MAE（平均绝对误差）
- LTV Error（相对误差）
- D30 Error
- Payer Rate Error

---

# 9. E9.8 入口

## 9.1 进入 Evolution Layer

E9.8 不再新增分析模块，进入 Evolution Layer。

## 9.2 第一个模块：Creative Mutation Engine

```
输入: Winner DNA + Prediction + Historical Failure
输出: New Creative DNA (变异后的基因)
```

## 9.3 最终愿景

```
              Creative Evolution Agent
                     ▲
                     |
              Decision Layer
                     ▲
                     |
              Intelligence Layer
                     ▲
                     |
              Data Asset Layer

  一个会自我进化的 AI 创意增长系统。
```

---

# 附录 A：代码目录映射

```
src/market_ops/
├── creative_analysis/          → Data Asset Layer / Intelligence Layer
├── player_intelligence/        → Intelligence Layer (E9.4, E9.5)
├── creative_matching/          → Intelligence Layer / Decision Layer (E9.6)
├── creative_learning/          → Intelligence Layer (E9.7)
├── creative_evolution/         → Evolution Layer (E9.8+)
├── creative_decision/          → Decision Layer (E9.8+)
├── creative_brain/             → Cross-layer (v5.0 Evolution Engine)
└── game_company/               → Application Layer (Game Company OS)
```

# 附录 B：相关文档

- [E9_MODULE_CONTRACTS.md](./E9_MODULE_CONTRACTS.md) — 模块接口契约
- [E9_DATA_FLOW.md](./E9_DATA_FLOW.md) — 数据流规范
- [E9_ROADMAP.md](./E9_ROADMAP.md) — 版本路线图