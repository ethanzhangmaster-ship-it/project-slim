# KPI Action Rulebook Spec v1.0

> **显式 KPI → Action 规则手册**。每个指标异常 → 对应动作 → 不应该做什么。
> 任何代码修改必须遵循此 Spec。

---

## §1 设计目标

将优化逻辑从隐式加权评分中提取为显式 if-then 规则，实现：
- **可审计**：每个决策知道为什么触发
- **可解释**：每条规则有 reason + anti_action + anti_reason
- **可配置**：支持自定义阈值覆盖
- **优先级排序**：规则冲突时有明确优先级

### 核心约束（强约束）

- ❌ 不允许隐式编码"CTR低就降预算"
- ❌ 不允许规则与 Bandit 决策冲突
- ✔ 每条规则必须包含 action + anti_action + reason
- ✔ 数据不足时返回 DATA_BLOCKED（不决策）
- ✔ 支持最小花费/最小展示量阈值
- ✔ 支持素材老化加权（creative_age_days）

---

## §2 数据流

```
KPI Metrics → KpiActionRulebook → List[KpiRule] → ActionType
```

输入：
- `metrics`：KPI 指标快照（CTR / CPM / CPI / ROAS / Frequency / Spend / Impressions）
- `min_spend`：最小花费阈值（低于不决策）
- `min_impressions`：最小展示量阈值
- `creative_age_days`：素材投放天数（老化加权）

输出：
- `triggered_rules`：触发规则列表（按优先级排序）
- `decision`：最终推荐动作（ActionType）
- `explanations`：规则解释列表
- `confidence`：决策置信度
- `requires_human_review`：是否需要人工审核

---

## §3 核心对象

### KpiRule

| 字段 | 类型 | 说明 |
|---|---|---|
| rule_id | str | 规则 ID（CTR_TOO_LOW / CPM_TOO_HIGH） |
| description | str | 人类可读规则描述 |
| condition | KpiMetric | 触发指标 |
| threshold_operator | str | 阈值操作符（">" / "<"） |
| threshold_value | float | 阈值 |
| threshold_unit | str | 阈值单位（"%" / "$" / "absolute"） |
| action | ActionType | 推荐动作 |
| severity | Severity | 严重程度（CRITICAL / WARNING / INFO） |
| priority | int | 优先级（1 最高） |
| reason | str | 为什么这么做 |
| anti_action | ActionType | 不应该做什么 |
| anti_reason | str | 为什么不应该那么做 |

### ActionType（枚举）

```python
class ActionType(str, Enum):
    # 预算相关
    SCALE_UP = "scale_up"        # 加预算
    SCALE_DOWN = "scale_down"    # 降预算
    PAUSE = "pause"              # 暂停
    KILL = "kill"                # 关停
    
    # 创意相关
    CHANGE_CREATIVE = "change_creative"   # 换素材
    CHANGE_HEADLINE = "change_headline"   # 换文案
    CHANGE_CTA = "change_cta"             # 换 CTA
    CHANGE_IMAGE = "change_image"         # 换图片
    
    # 定向相关
    CHANGE_AUDIENCE = "change_audience"           # 换受众
    CHANGE_COUNTRY = "change_country"             # 换国家
    BROADEN_TARGETING = "broaden_targeting"       # 放宽定向
    NARROW_TARGETING = "narrow_targeting"         # 收缩定向
    
    # 出价相关
    INCREASE_BID = "increase_bid"   # 加出价
    DECREASE_BID = "decrease_bid"   # 降出价
    SET_COST_CAP = "set_cost_cap"   # 设成本上限
    
    # 观察
    HOLD = "hold"               # 保持观察
    MONITOR = "monitor"         # 密切监控
    DATA_BLOCKED = "data_blocked"  # 数据不足
```

---

## §4 规则列表（15 条核心规则）

| 规则 ID | 条件 | 阈值 | Action | Anti-Action | Priority |
|---------|------|------|--------|-------------|----------|
| **CTR_TOO_LOW** | CTR `<` | **0.5%** | CHANGE_CREATIVE | SCALE_DOWN | 1 |
| **CTR_HIGH_CPI_HIGH** | CTR `>` | **2.0%** | MONITOR | CHANGE_CREATIVE | 2 |
| **CTR_VERY_HIGH** | CTR `>` | **5.0%** | CHANGE_CREATIVE | SCALE_UP | 3 |
| **CPM_TOO_HIGH** | CPM `>` | **$30** | CHANGE_AUDIENCE | CHANGE_CREATIVE | 1 |
| **CPM_SPIKE** | CPM `>` | **$50** | SCALE_DOWN | INCREASE_BID | 2 |
| **CPM_LOW_CTR_LOW** | CPM `<` | **$5** | NARROW_TARGETING | CHANGE_CREATIVE | 3 |
| **CPI_TOO_HIGH** | CPI `>` | **$5** | CHANGE_CREATIVE | SCALE_DOWN | 1 |
| **CPI_LOW_SCALE** | CPI `<` | **$1** | SCALE_UP | CHANGE_CREATIVE | 4 |
| **ROAS_TOO_LOW** | ROAS `<` | **0.5** | PAUSE | CHANGE_CREATIVE | 1 |
| **ROAS_DECLINING** | ROAS `<` | **1.0** | CHANGE_CREATIVE | SCALE_UP | 2 |
| **ROAS_HIGH_SCALE** | ROAS `>` | **2.0** | SCALE_UP | CHANGE_CREATIVE | 5 |
| **FREQUENCY_TOO_HIGH** | Frequency `>` | **3.0** | CHANGE_CREATIVE | SCALE_DOWN | 1 |
| **SPEND_LIMITED** | Spend `<` | **预算50%** | BROADEN_TARGETING | CHANGE_CREATIVE | 3 |
| **IPM_TOO_LOW** | IPM `<` | **5** | CHANGE_CREATIVE | CHANGE_AUDIENCE | 2 |
| **IMPRESSIONS_DROPPING** | Impressions `<` | **1000** | CHANGE_AUDIENCE | CHANGE_CREATIVE | 3 |

---

## §5 规则详解（示例）

### CTR_TOO_LOW

```python
KpiRule(
    rule_id="CTR_TOO_LOW",
    description="CTR 过低 → 素材有问题，换素材，不要降预算",
    condition=KpiMetric.CTR,
    threshold_operator="<",
    threshold_value=0.5,
    threshold_unit="%",
    action=ActionType.CHANGE_CREATIVE,
    severity=Severity.CRITICAL,
    priority=1,
    reason="CTR低说明素材不吸引人，换素材而非降预算。降预算只会让数据更少，无法判断问题。",
    anti_action=ActionType.SCALE_DOWN,
    anti_reason="降预算不会解决CTR低的问题，只会让CPM上升且数据更少。",
)
```

### ROAS_TOO_LOW

```python
KpiRule(
    rule_id="ROAS_TOO_LOW",
    description="ROAS 过低 → 暂停，检查产品质量/付费设计",
    condition=KpiMetric.ROAS,
    threshold_operator="<",
    threshold_value=0.5,
    threshold_unit="absolute",
    action=ActionType.PAUSE,
    severity=Severity.CRITICAL,
    priority=1,
    reason="ROAS<0.5=严重亏损，大概率是产品问题（付费设计/用户质量），应暂停先修复产品再投。",
    anti_action=ActionType.CHANGE_CREATIVE,
    anti_reason="ROAS极低时换素材难解决问题，产品层面问题更严重。",
)
```

### CPM_TOO_HIGH

```python
KpiRule(
    rule_id="CPM_TOO_HIGH",
    description="CPM 过高 → 竞争激烈，换受众或放宽定向",
    condition=KpiMetric.CPM,
    threshold_operator=">",
    threshold_value=30.0,
    threshold_unit="$",
    action=ActionType.CHANGE_AUDIENCE,
    severity=Severity.CRITICAL,
    priority=1,
    reason="CPM高说明竞争激烈或受众太窄，需要换受众定位或放宽定向。换素材对CPM影响小。",
    anti_action=ActionType.CHANGE_CREATIVE,
    anti_reason="CPM高是受众竞争问题，换素材对CPM基本无影响。",
)
```

---

## §6 接口定义

```python
class KpiActionRulebook:
    def __init__(custom_thresholds: Dict[str, Dict] = None)
    
    def evaluate(
        metrics: Dict[KpiMetric, float],
        min_spend: float = 0.0,
        min_impressions: int = 100
    ) -> List[KpiRule]
    
    def evaluate_with_context(
        metrics: Dict[KpiMetric, float],
        creative_age_days: int = 0,
        min_spend: float = 10.0,
        min_impressions: int = 1000
    ) -> Dict
    
    def get_rules_by_metric(metric: KpiMetric) -> List[KpiRule]
    def get_rules_by_action(action: ActionType) -> List[KpiRule]
    def get_critical_rules() -> List[KpiRule]
    def export_rules() -> List[Dict]
```

---

## §7 自定义阈值

运行时可覆盖阈值：

```python
custom = {
    "CTR_TOO_LOW": {"threshold_value": 1.0},  # CTR阈值从0.5改为1.0
    "ROAS_TOO_LOW": {"threshold_value": 0.7}, # ROAS阈值从0.5改为0.7
}
rb = KpiActionRulebook(custom_thresholds=custom)
```

---

## §8 数据充足性检查

花费或展示量不足时返回 DATA_BLOCKED：

```python
if spend < min_spend or impressions < min_impressions:
    return DATA_BLOCKED
```

**理由**：数据不足时决策置信度低，建议继续观察。

---

## §9 与主流程集成

接入 `run_pipeline.py` Step 6 审计层：

```python
rb = KpiActionRulebook()
metrics = {
    KpiMetric.CTR: avg_ctr,
    KpiMetric.CPM: avg_cpm,
    KpiMetric.CPI: avg_cpi,
    KpiMetric.ROAS: avg_roas,
    KpiMetric.SPEND: global_spend,
    KpiMetric.IMPRESSIONS: global_imp,
}
kpi_result = rb.evaluate_with_context(metrics, min_spend=1.0, min_impressions=100)
```

输出：控制台审计报告