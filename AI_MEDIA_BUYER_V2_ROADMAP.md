# AI投放分析系统升级需求 V2

生成日期：2026-06-12

本文档是当前 Market Ops / 周报投放分析系统的下一阶段升级需求，目标是把系统从「AI风控投放系统」升级为「AI增长投放系统」，并同时支持成熟项目优化与新品冷启动探索，最终形成可持续迭代的「AI Media Buyer」闭环。

---

## 1. 当前系统定位

当前系统已经具备：

- ROI分析
- 回收预测
- 样本成熟度判断
- 风险识别
- 归因可信度判断
- Campaign层分析
- 素材代理层分析
- 自动生成建议动作
- 周报、管理层卡片、市场群卡片、自检和发送门禁

当前系统更偏：

> AI风控投放系统

下一阶段目标：

> AI增长投放系统

V2 采用双引擎定位：

| 引擎 | 适用对象 | 核心判断 | 主要目标 |
| --- | --- | --- | --- |
| Optimization Engine | 老品、成熟项目、扩量阶段 | ROI、回本、疲劳、放量 | 提升利润和扩量效率 |
| Discovery Engine | 新品、冷启动、无历史样本阶段 | 信号、探索、学习、预测 | 快速发现方向和增长潜力 |

核心目标：

- 不仅识别风险，还能主动发现增长机会
- 能理解素材内容，而不是只看素材财务结果
- 能预测素材疲劳和生命周期
- 能形成自动化增长策略
- 能让新品在低样本、低 ROI、高波动阶段仍然获得探索机会
- 后期可进入半自动或自动执行动作

---

## 2. 当前主要问题

### 2.1 过度保守

当前系统大量输出：

- 继续观察
- 限额验证
- 不新增预算

问题是系统更像风险控制器，而不是增长引擎。

典型场景：

- 项目已经达到历史盈利区间
- 某些 Campaign 已经形成局部 ROI 优势
- 某些素材 ROI 已过线但仍只被标记为观察候选

升级要求：

- 增加增长优先级机制
- 给出“哪里最值得加钱”的排序
- 对局部赢家允许小额扩量验证

### 2.2 过度依赖静态历史保底线

当前常见判断逻辑：

```python
if d7 < historical_floor:
    risk = "high"
```

问题是历史保底线可能过时，市场环境会变化：

- CPM
- CPI
- 广告库存
- IAA结构
- 用户质量
- 国家结构
- 素材竞争度

升级要求：

- 固定历史保底线升级为动态回本模型
- 历史线只作为参考，不作为唯一否决条件

### 2.3 项目级判断压制局部赢家

当前如果项目整体 D7 较差，即使部分 Campaign ROI > 1，系统也倾向禁止放量。

问题是可能错杀局部增长机会。

升级要求：

- 增加局部突破机制
- Campaign、国家、平台、素材组合可以独立获得“小额放量测试”权限

示例逻辑：

```python
if campaign_roi > 1.2 and spend > threshold and ctr > benchmark:
    allow_small_scale_up()
```

### 2.4 素材系统仍是财务分析

当前素材分析本质仍是：

- ROI
- 花费
- 安装
- 收入

缺少创意理解能力。系统还不知道：

- 哪种 Hook 有效
- 哪种情绪有效
- 哪种剧情有效
- 哪种节奏有效
- 哪种 UI 画面有效
- 哪种 CTA 更容易放量

升级要求：

- 从“哪个素材赢”升级到“为什么素材赢”
- 从素材 ID 分析升级到素材模式分析

### 2.5 新品不能直接套用老品 ROI 系统

当前系统主要基于：

- 历史素材
- 历史 ROI
- 历史回本
- 已验证 Campaign
- 已验证素材模式

这些逻辑适合老品和成熟项目，但新品阶段存在根本不同的问题：

| 老品 | 新品 |
| --- | --- |
| 已有历史数据 | 无历史数据 |
| 已知素材模式 | 未知素材方向 |
| 已知用户质量 | 未知目标用户 |
| 已知回本周期 | 未知 LTV 曲线 |
| 可直接 ROI 优化 | 必须先探索 |

如果新品直接进入老品 ROI 判断，系统会过早停测、错杀新品、无法探索方向，最终导致新品永远跑不出可复制模式。

升级要求：

- 新品阶段禁止直接以 ROI 作为核心判断
- 新品优先使用 Signal Score、学习速度和测试假设质量
- 只有进入 Scaling 阶段后，才接入 ROI、回本、疲劳和扩量逻辑

---

## 3. 推荐新系统架构

```text
数据层
↓
归因清洗层
↓
阶段识别层
↓
Discovery Engine（新品）
信号评分 / 探索预算 / 早期预测 / 假设生成
↓
Validation Gate
↓
Optimization Engine（老品/成熟项目）
用户质量 / 素材DNA / 素材聚类 / 疲劳检测 / ROI预测
↓
增长策略引擎
↓
自动动作层
```

现有代码建议承接关系：

| 新层级 | 当前可复用模块 | 说明 |
| --- | --- | --- |
| 数据层 | `pipeline.py`, `sheet_sync.py`, `clients/` | 已有 Feishu / Adjust / TecDo / CSV 输入 |
| 归因清洗层 | `creative_attribution_audit.py`, `google_creative_resolver.py`, `creative_source_readiness.py` | 已具备代理素材层分析基础 |
| 阶段识别层 | 新增 | 自动识别 Discovery / Validation / Scaling，不让新品误入老品 ROI 规则 |
| Discovery Engine | 新增 | 用信号、探索、学习和预测驱动新品冷启动 |
| 用户质量层 | 新增 | 接入留存、Session、广告观看、付费率等指标 |
| 素材DNA识别层 | 新增 | 需要素材内容标签、人工标注或多模态模型 |
| 素材聚类层 | 新增 | 按 DNA + 表现做模式聚类 |
| 生命周期/疲劳检测层 | 新增 | 需要日级趋势、频次、CTR、CPM、留存趋势 |
| ROI预测层 | `forecast_validation.py`, `payback_targets.py` | 从静态线升级为动态预测 |
| 增长策略引擎 | `executive_report.py`, `management_action_list.py`, `digest.py` | 从风险建议升级为增长排序 |
| 自动动作层 | 新增 | 后期接 Meta / Google 写操作，默认先只生成 action plan |

---

## 4. 模块优先级

| 优先级 | 模块 | 目标 |
| --- | --- | --- |
| P0 | Discovery Engine MVP | 让新品先按信号和学习速度探索，不被老品 ROI 规则错杀 |
| P0 | 素材DNA识别系统 | 让系统理解素材为什么赢 |
| P0 | 增长优先级系统 | 输出最值得加钱、复制、修复、降权的对象 |
| P1 | 素材聚类系统 | 从素材 ID 分析升级到素材模式分析 |
| P1 | 素材疲劳检测系统 | 用趋势指标判断疲劳，不只口头提示 |
| P1 | 动态回本模型 | 用当前市场变量替代固定历史保底线 |
| P2 | 用户质量分析层 | 防止只看短期 ROAS 误判高质量流量 |
| P2 | 预测系统升级 | 多维预测 D30/D60/D90/D180 ROI |
| P3 | 自动动作系统 | 从建议升级到半自动执行 |

---

## 5. 模块需求

### 5.1 模块1：素材DNA识别系统

目标：

> 让系统理解“为什么素材赢”，而不是只知道“哪个素材赢”。

需要自动识别的维度：

| 维度 | 示例 |
| --- | --- |
| Hook类型 | 危机 / 爽点 / 反转 / 目标展示 / 失败惩罚 |
| 情绪 | 焦虑 / 爽感 / 治愈 / 紧张 / 好奇 |
| 节奏 | 快切 / 慢铺 / 前3秒强刺激 / 中段转折 |
| UI类型 | Merge / Build / Battle / Map / Collection |
| 文案风格 | 强标题 / 弱标题 / 问句 / 命令式 / 悬念式 |
| CTA强度 | 强引导 / 弱引导 / 无CTA |
| 视频结构 | 真人 / UGC / 游戏录屏 / 混剪 / 假广告剧情 |
| 字幕风格 | 大字 / 悬疑 / 高密度 / 少字幕 |
| 首3秒信息密度 | 高 / 中 / 低 |
| 失败或冲突强度 | 高 / 中 / 低 |

建议输出结构：

```json
{
  "creative_id": "120244794613980444",
  "asset_id": "optional_asset_id",
  "project": "P04 Witch",
  "channel": "Facebook",
  "hook_type": "危机",
  "emotion": "焦虑",
  "pace": "快",
  "ui_type": "Merge",
  "copy_style": "强标题",
  "cta_strength": "强",
  "video_structure": "游戏录屏",
  "subtitle_style": "大字",
  "first_3s_density": "高",
  "conflict_strength": "高",
  "predicted_scalability": 0.78,
  "label_confidence": 0.82
}
```

验收标准：

- 每条可识别素材都有 DNA 标签
- 标签来源可追溯：人工、规则、模型、文件名解析或多模态识别
- 周报不只输出素材 ID，还能输出素材模式原因
- 低置信度标签不能进入强结论

### 5.2 模块2：素材聚类系统

目标：

> 从“素材ID分析”升级到“素材模式分析”。

示例输出：

```json
{
  "cluster_id": "witch_crisis_merge_fast_001",
  "cluster_name": "女巫危机流",
  "dominant_tags": {
    "hook_type": "危机",
    "emotion": "焦虑",
    "ui_type": "Merge",
    "pace": "快"
  },
  "creative_count": 18,
  "avg_roi": 1.82,
  "median_roi": 1.31,
  "best_channel": "Facebook",
  "best_geo": ["US"],
  "best_platform": "iOS",
  "fatigue_cycle_days": 5,
  "recommended_variants": [
    "更换前3秒冲突点",
    "保留Merge UI但替换失败惩罚",
    "保留焦虑情绪但增强结尾爽点"
  ]
}
```

作用：

- 自动发现爆款模式
- 自动生成变体方向
- 自动做素材复制策略
- 将“复制某个素材”升级为“复制某类素材模式”

### 5.3 模块3：素材疲劳检测系统

当前系统只是提示素材疲劳或流量变化，但没有真正检测。

疲劳判定建议：

```python
if ctr_drop > 0.15 or cpm_rise > 0.20 or frequency_rise > 0.30 or hold_rate_drop > 0.10:
    fatigue = True
```

建议输出：

```json
{
  "creative_id": "120244794613980444",
  "status": "fatigue",
  "severity": "medium",
  "reason": [
    "CTR下降18%",
    "CPM上涨22%"
  ],
  "suggestion": [
    "更换前3秒",
    "替换BGM",
    "增加冲突感"
  ],
  "detected_at": "2026-06-12"
}
```

需要指标：

- CTR 日趋势
- CPM 日趋势
- Frequency 日趋势
- CPI 日趋势
- CVR 日趋势
- Retention 或广告观看行为趋势
- 素材上线天数

验收标准：

- 输出疲劳素材列表
- 输出疲劳原因，而不是只给结论
- 区分“疲劳”“归因异常”“样本不足”“自然波动”

### 5.4 模块4：增长优先级系统

当前系统只会输出风险和观察，缺少“哪里最值得加钱”。

建议输出：

| 项目 | 状态 | 增长建议 |
| --- | --- | --- |
| P07 Vampire | 成长期 | +20%预算测试 |
| P04 Witch | 修复期 | 修复 iOS/Facebook 结构，同时保留局部赢家小额测试 |
| P02 Mermaid | 高波动期 | 保守验证，等待回收恢复 |

AI需要自动判断：

- 哪些值得扩量
- 哪些应该降权
- 哪些需要修复
- 哪些需要复制
- 哪些局部赢家可以突破项目级保守判断

建议对象结构：

```json
{
  "entity_type": "campaign",
  "entity_id": "P4-IOS-Purchase-T1-260501",
  "project": "P04 Witch",
  "growth_stage": "local_winner",
  "growth_priority": 0.76,
  "recommended_action": "small_scale_up",
  "budget_change": "+10%",
  "guardrails": [
    "单日预算增幅不超过10%",
    "连续2日D3代理ROI恶化超过15%则回撤",
    "素材疲劳为high时禁止扩量"
  ],
  "reason": [
    "Campaign ROI高于项目均值",
    "花费已过样本门槛",
    "CTR高于渠道基准"
  ]
}
```

### 5.5 模块5：用户质量分析层

当前系统主要是 ROI 视角，下一阶段需要加入用户行为视角。

建议接入指标：

| 指标 | 用途 |
| --- | --- |
| D1留存 | 用户质量 |
| D3留存 | 中期质量 |
| Session时长 | 沉浸度 |
| 广告观看次数 | IAA价值 |
| 首次付费率 | IAP价值 |
| 国家分布 | 长尾质量 |
| 首日广告ARPDAU | IAA早期变现 |
| 新手关卡通过率 | 前端质量 |

目标：

- 避免错杀高质量用户来源
- 避免错误判断 IAA 项目
- 避免只看短期 ROAS
- 识别低 CPI 但低质量流量
- 识别短期 ROAS 弱但留存或广告价值高的流量

### 5.6 模块6：动态回本模型

当前历史保底线固定，下一阶段要变成动态回本预测。

动态变量：

- CPM
- CPI
- CTR
- CVR
- 留存
- 广告ARPDAU
- 国家质量
- 平台差异
- IAA/IAP结构
- 素材生命周期
- 账号或渠道波动

建议输出：

```json
{
  "project": "P04 Witch",
  "channel": "Facebook",
  "platform": "iOS",
  "geo": "US",
  "dynamic_break_even_d7": 0.26,
  "static_historical_floor_d7": 0.32,
  "confidence": 0.72,
  "model_version": "dynamic_payback_v1",
  "reason": [
    "当前CPI低于历史均值12%",
    "D1留存高于近30日均值8%",
    "广告ARPDAU回升"
  ]
}
```

验收标准：

- 周报不再只写“低于历史保底线”
- 同时展示静态历史线、动态线和模型置信度
- 动态线低置信度时，必须降级为观察结论

### 5.7 模块7：自动动作系统

目标：

> 系统不只分析，还能执行。

可执行动作：

- 自动降预算
- 自动加预算
- 自动复制 Campaign
- 自动暂停低 ROI 国家
- 自动暂停疲劳素材
- 自动生成测试组

建议输出：

```json
{
  "action": "scale_budget",
  "target_type": "project",
  "target": "P07 Vampire",
  "change": "+20%",
  "mode": "approval_required",
  "rollback_rule": "D3代理ROI连续2日下降超过15%则回撤",
  "risk_level": "medium"
}
```

落地要求：

- V2 先只生成动作计划，不直接执行
- V3 再接平台写操作
- 所有动作必须带回撤条件
- 所有预算动作必须带审批状态

### 5.8 模块8：预测系统升级

当前预测偏简单曲线外推，下一阶段需要多维预测模型。

输入维度：

- CTR
- CVR
- CPI
- CPM
- 留存
- 国家
- 用户质量
- 素材类型
- 生命周期阶段
- 渠道和平台
- IAA/IAP结构

建议输出：

```json
{
  "entity_type": "campaign",
  "entity_id": "P4-IOS-Purchase-T1-260501",
  "predicted_d30_roi": 0.78,
  "predicted_d90_roi": 1.12,
  "predicted_d180_roi": 1.32,
  "confidence": 0.81,
  "risk_flags": [
    "素材疲劳中等",
    "国家结构偏集中"
  ]
}
```

### 5.15 模块15：Discovery Engine（新品冷启动）

目标：

> 让 AI 具备新品自探索能力。

新品阶段的核心目标不是“快速赚钱”，而是“快速学习”：

- 快速发现方向
- 快速发现有效 Hook
- 快速发现潜在人群
- 快速发现高潜国家
- 快速验证玩法市场适配

建议新增：

- `discovery_engine.py`

核心原则：

```text
学习速度
>
方向发现
>
用户质量
>
增长势能
>
ROI
```

落地要求：

- 新品阶段禁止 ROI 强停测
- 禁止用老品历史 ROI 压制新品探索
- 允许低 ROI、高波动、小样本、多方向测试
- 输出建议和下一轮测试计划，不直接改预算、不发送飞书、不接平台写操作

### 5.16 模块16：Signal Score 系统

目标：

> 用“信号强度”替代新品阶段的 ROI 判断。

建议新增：

- `signal_score.py`

信号指标：

| 指标 | 作用 |
| --- | --- |
| CTR | 市场兴趣 |
| Hold Rate | Hook 能力 |
| IPM | 广告吸引力 |
| CPI | 市场竞争力 |
| D1 留存 | 产品潜力 |
| Session 时长 | 沉浸度 |
| FTUE 完成率 | 新手体验 |
| 广告观看率 | IAA 潜力 |
| 评论情绪 | 用户反馈 |

建议评分公式：

```python
signal_score = (
    0.25 * ctr_score
    + 0.20 * retention_score
    + 0.20 * session_score
    + 0.15 * ipm_score
    + 0.10 * hold_rate_score
    + 0.10 * cpi_score
)
```

建议输出：

```json
{
  "project": "P09 Survival",
  "signal_score": 0.78,
  "signal_level": "high",
  "recommended_action": "continue_exploration",
  "positive_signals": [
    "CTR高于品类均值",
    "D1留存优秀",
    "Session时长较高"
  ],
  "negative_signals": [
    "IPM偏低"
  ]
}
```

### 5.17 模块17：新品阶段管理系统

目标：

> AI 自动识别新品所处阶段，并决定应该接入 Discovery Engine 还是 Optimization Engine。

建议新增：

- `new_product_stage.py`

阶段划分：

| 阶段 | 时间 | 目标 | 判断主轴 |
| --- | --- | --- | --- |
| Discovery | D0-D7 | 找方向 | 信号、学习速度、测试覆盖 |
| Validation | D7-D30 | 验证模式 | 国家、素材、人群、平台对比 |
| Scaling | D30+ | ROI 优化 | 回本、疲劳、扩量、预算效率 |

阶段逻辑：

- Discovery：最大化学习速度，禁止 ROI 强停测，允许多方向测试。
- Validation：寻找可复制模式，开始对比国家、素材、人群和平台。
- Scaling：接入 Optimization Engine，进入 ROI、回本、疲劳和扩量判断。

### 5.18 模块18：探索预算系统

目标：

> 保留新品探索能力，避免所有预算都流向老品。

建议新增：

- `exploration_budget.py`

建议预算池：

| 类型 | 占比 | 用途 |
| --- | ---: | --- |
| 探索预算 | 20% | 新 Hook、新国家、新人群、新节奏测试 |
| 放量预算 | 60% | 成熟项目和已验证模式扩量 |
| 修复预算 | 20% | 修复低效组合、归因问题和素材疲劳 |

探索预算特点：

- 允许低 ROI
- 允许高波动
- 允许小样本
- 允许多实验并行

建议输出：

```json
{
  "budget_type": "exploration",
  "daily_budget": 300,
  "target": "new_hooks_test",
  "expected_learning_goal": "验证危机Hook有效性"
}
```

### 5.19 模块19：新品早期预测系统

目标：

> 在 D1-D3 阶段预测长期潜力，不等待 D30/D90/D180 后才判断。

建议新增：

- `early_prediction.py`

输入指标：

| 指标 | 用途 |
| --- | --- |
| CTR | 市场兴趣 |
| D1 留存 | 产品质量 |
| Session | 沉浸度 |
| 广告观看 | IAA 潜力 |
| CPI | 市场竞争力 |
| FTUE 完成率 | 新手体验 |

建议输出：

```json
{
  "predicted_scale_potential": 0.81,
  "predicted_ltv_curve": "slow_high_tail",
  "predicted_best_platform": "Android",
  "predicted_best_geo": [
    "US",
    "BR"
  ]
}
```

### 5.20 模块20：迁移学习系统

目标：

> 用老项目经验帮助新品冷启动，但不让老品 ROI 直接否决新品。

建议新增：

- `transfer_learning.py`

系统需要自动识别新品与历史项目的相似性，例如：

- Witch
- Merge
- 女性向
- Survival
- Drama

建议输出：

```json
{
  "new_project": "P09 Survival",
  "similar_projects": [
    "P04 Witch",
    "P07 Vampire"
  ],
  "shared_features": [
    "女性向",
    "危机Hook",
    "Merge玩法"
  ],
  "recommended_creative_patterns": [
    "资源不足",
    "房屋破损",
    "女主危机"
  ]
}
```

### 5.21 模块21：Hypothesis Generator

目标：

> AI 自动生成下一轮测试方向，减少新品阶段对纯人工试错的依赖。

建议新增：

- `hypothesis_generator.py`

自动生成的测试方向：

- Hook 测试
- 国家测试
- 人群测试
- 节奏测试
- CTA 测试

建议输出：

```json
{
  "hypothesis": "危机类Hook可能提升CTR",
  "test_plan": {
    "variant_a": "平稳开场",
    "variant_b": "房屋崩塌开场"
  },
  "expected_impact": {
    "ctr": "+15%"
  }
}
```

---

## 6. 建议新增数据结构

### 6.1 `creative_dna.csv`

| 字段 | 说明 |
| --- | --- |
| date | 标签生成日期 |
| project | 项目 |
| channel | 渠道 |
| creative_id | 素材ID |
| asset_id | 资产ID，可为空 |
| creative_name | 素材名称 |
| hook_type | Hook类型 |
| emotion | 情绪 |
| pace | 节奏 |
| ui_type | UI类型 |
| copy_style | 文案风格 |
| cta_strength | CTA强度 |
| video_structure | 视频结构 |
| subtitle_style | 字幕风格 |
| first_3s_density | 首3秒信息密度 |
| conflict_strength | 冲突强度 |
| label_source | 标签来源 |
| label_confidence | 标签置信度 |

### 6.2 `creative_clusters.csv`

| 字段 | 说明 |
| --- | --- |
| cluster_id | 聚类ID |
| cluster_name | 聚类名称 |
| project | 项目 |
| dominant_tags | 主标签JSON |
| creative_count | 素材数量 |
| avg_roi | 平均ROI |
| median_roi | 中位ROI |
| best_channel | 最佳渠道 |
| best_geo | 最佳国家 |
| best_platform | 最佳平台 |
| fatigue_cycle_days | 疲劳周期 |
| recommended_variants | 建议变体JSON |

### 6.3 `creative_fatigue.csv`

| 字段 | 说明 |
| --- | --- |
| date | 检测日期 |
| creative_id | 素材ID |
| project | 项目 |
| channel | 渠道 |
| status | normal / watch / fatigue |
| severity | low / medium / high |
| ctr_change_7d | 7日CTR变化 |
| cpm_change_7d | 7日CPM变化 |
| frequency_change_7d | 7日频次变化 |
| hold_rate_change_7d | 留存或观看保持变化 |
| reason | 原因JSON |
| suggestion | 建议JSON |

### 6.4 `growth_priorities.csv`

| 字段 | 说明 |
| --- | --- |
| date | 生成日期 |
| entity_type | project / campaign / creative / cluster / geo |
| entity_id | 对象ID |
| project | 项目 |
| growth_stage | 成长期 / 修复期 / 高波动期 / 衰退期 / 局部突破 |
| growth_priority | 增长优先级 0-1 |
| risk_priority | 风险优先级 0-1 |
| recommended_action | 建议动作 |
| budget_change | 建议预算变化 |
| guardrails | 护栏JSON |
| reason | 原因JSON |
| confidence | 置信度 |

### 6.5 `dynamic_payback_targets.csv`

| 字段 | 说明 |
| --- | --- |
| date | 生成日期 |
| project | 项目 |
| channel | 渠道 |
| platform | 平台 |
| geo | 国家 |
| dynamic_break_even_d7 | 动态 D7 回本线 |
| dynamic_break_even_d30 | 动态 D30 回本线 |
| static_floor_d7 | 当前历史 D7 保底线 |
| static_floor_d30 | 当前历史 D30 保底线 |
| confidence | 置信度 |
| drivers | 驱动因素JSON |
| model_version | 模型版本 |

---

## 7. 输出文件建议

V2 建议在 `output/active/` 下新增：

- `discovery_signal_YYYYMMDD.md`
- `discovery_signal_YYYYMMDD.json`
- `new_product_stage_YYYYMMDD.md`
- `new_product_stage_YYYYMMDD.json`
- `exploration_budget_YYYYMMDD.md`
- `exploration_budget_YYYYMMDD.json`
- `early_prediction_YYYYMMDD.md`
- `early_prediction_YYYYMMDD.json`
- `hypothesis_plan_YYYYMMDD.md`
- `hypothesis_plan_YYYYMMDD.json`
- `creative_dna_YYYYMMDD.md`
- `creative_dna_YYYYMMDD.json`
- `creative_clusters_YYYYMMDD.md`
- `creative_clusters_YYYYMMDD.json`
- `creative_fatigue_YYYYMMDD.md`
- `creative_fatigue_YYYYMMDD.json`
- `growth_priorities_YYYYMMDD.md`
- `growth_priorities_YYYYMMDD.json`
- `dynamic_payback_targets_YYYYMMDD.md`
- `dynamic_payback_targets_YYYYMMDD.json`
- `ai_media_buyer_plan_YYYYMMDD.md`
- `ai_media_buyer_plan_YYYYMMDD.json`

以上是未来接口规划。本次路线图更新只记录需求，不创建 Python 模块、不生成数据文件、不改变飞书发送流程。

周报中建议新增或替换的表达：

- 新品阶段禁止直接用 ROI 强停测
- 新品先看 Signal Score、学习速度和测试假设质量
- 新品进入 Scaling 后再接入 ROI、回本、疲劳和扩量逻辑
- 从“建议限额验证”升级为“风险动作 + 增长动作并列”
- 从“优先素材 ID”升级为“优先素材模式”
- 从“低于历史保底线”升级为“静态线 / 动态线 / 置信度”
- 从“素材疲劳”口头提示升级为“疲劳检测证据”

---

## 8. 分阶段实施计划

### Phase 0：Discovery Engine MVP

目标：

- 让新品先按信号和学习速度探索
- 避免新品被老品 ROI、历史回本线和成熟素材模式提前错杀
- 先生成新品探索建议，不直接改预算、不发送飞书、不接平台写操作

建议新增：

- `discovery_engine.py`
- `signal_score.py`
- `new_product_stage.py`
- `exploration_budget.py`
- `hypothesis_generator.py`
- CLI：`python -m market_ops.cli discovery-engine --report-date latest`
- 输出：`discovery_signal_YYYYMMDD.md/json`、`new_product_stage_YYYYMMDD.md/json`、`exploration_budget_YYYYMMDD.md/json`、`hypothesis_plan_YYYYMMDD.md/json`

验收：

- 能识别项目处于 Discovery / Validation / Scaling 哪个阶段
- Discovery 阶段输出 Signal Score、正负信号、探索预算建议和下一轮测试假设
- 新品阶段建议不使用 ROI 强停测，不覆盖现有 `growth_priorities.py`
- Scaling 阶段才把项目交给 Optimization Engine 的 ROI / 回本 / 疲劳 / 扩量逻辑

### Phase 1：增长优先级 + 局部突破

目标：

- 解决过度保守问题
- 先不依赖素材视觉理解，只用现有数据产出增长排序

建议新增：

- `growth_priorities.py`
- CLI：`python -m market_ops.cli growth-priorities --report-date latest`
- 输出：`growth_priorities_YYYYMMDD.md/json`

验收：

- 每周能输出项目、Campaign、素材候选的增长优先级
- 能识别“项目整体偏弱但 Campaign/素材局部强”的对象
- 增长建议必须带护栏和回撤条件

### Phase 2：素材DNA MVP

目标：

- 先建立素材 DNA 数据结构
- 标签来源可以先从文件名、素材名、人工表、现有创意库字段和规则解析开始
- 后续再接多模态模型

建议新增：

- `creative_dna.py`
- `creative_dna.csv` 输入或输出表
- CLI：`python -m market_ops.cli creative-dna --report-date latest`

验收：

- Top 素材能输出 Hook、情绪、节奏、UI、CTA 等标签
- 低置信度标签不进入强复制结论

### Phase 3：素材聚类 + 疲劳检测

目标：

- 将素材从 ID 层升级到模式层
- 将疲劳提示升级为证据化检测

建议新增：

- `creative_clusters.py`
- `creative_fatigue.py`
- CLI：
  - `python -m market_ops.cli creative-clusters --report-date latest`
  - `python -m market_ops.cli creative-fatigue --report-date latest`

验收：

- 输出素材模式排行
- 输出疲劳状态、原因和建议
- 周报可以写出“复制哪类素材模式”

### Phase 4：动态回本模型 + 用户质量层

目标：

- 固定历史保底线降级为参考
- 用当前市场变量和用户质量生成动态回本线

建议新增：

- `dynamic_payback.py`
- `user_quality.py`
- CLI：
  - `python -m market_ops.cli dynamic-payback --report-date latest`
  - `python -m market_ops.cli user-quality --report-date latest`

验收：

- 周报显示静态线、动态线和置信度
- 动态线可以解释为什么某些对象允许小额突破

### Phase 5：AI Media Buyer Plan

目标：

- 把风险、增长、素材、用户质量、预测合成一张行动计划
- 仍以审批制为主，不直接自动执行

建议新增：

- `ai_media_buyer_plan.py`
- CLI：`python -m market_ops.cli ai-media-buyer-plan --report-date latest`

验收：

- 输出本周“加钱 / 降权 / 修复 / 复制 / 观察”的总表
- 每个动作都有原因、置信度、护栏、回撤条件
- 可以直接进入管理层卡片或市场群详细卡片

---

## 9. 最终目标

最终目标不是：

> AI报表

而是：

> AI Media Buyer

系统应该具备：

- 理解新品阶段
- 理解素材
- 理解用户
- 理解增长
- 理解疲劳
- 自动探索方向
- 自动生成测试假设
- 自动生成策略
- 自动执行或半自动执行动作

最终形成两条闭环。

新品 Discovery Loop：

```text
新品上线
↓
AI探索方向
↓
AI发现有效Hook
↓
AI识别潜在人群
↓
AI预测长期潜力
↓
AI生成下一轮测试
↓
逐步进入Scaling阶段
```

成熟项目 Optimization Loop：

```text
跑素材
↓
AI识别赢家模式
↓
AI生成变体
↓
自动测试
↓
自动扩量
↓
自动淘汰
↓
继续生成
```
