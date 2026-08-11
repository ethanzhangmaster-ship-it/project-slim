# Decision Boundary Spec v1.0

> **AI / 规则 决策边界配置**。显式声明哪些决策由 AI 决定，哪些由规则决定。
> 任何代码修改必须遵循此 Spec。

---

## §1 设计目标

让每个决策域可独立调优、可审计：
- **AI 域**：创意内容（图片/文案/视频）由 AI/Bandit/生成式 AI 决定
- **规则域**：投放控制（预算/暂停/关停/扩缩）由显式规则决定
- **混合域**：策略选择（受众/国家/赢家识别）由 AI 建议 + 规则审核

### 核心约束（强约束）

- ❌ 不允许 AI 直接决定 PAUSE / KILL
- ❌ 不允许规则直接决定 IMAGE_STYLE / HEADLINE
- ❌ 不允许两个域互相干扰
- ✔ 每个决策类别必须明确归属一个域
- ✔ 每个决策必须可审计（audit_decision）
- ✔ 混合域必须有 override_conditions 声明

---

## §2 决策域定义

```python
class DecisionDomain(str, Enum):
    AI = "ai"       # AI 决策：模型/Bandit/生成式AI
    RULE = "rule"   # 规则决策：显式 if-then 规则
    HYBRID = "hybrid"  # 混合：AI 建议 + 规则审核
```

---

## §3 决策类别枚举

```python
class DecisionCategory(str, Enum):
    # 创意类（AI 域）
    IMAGE_STYLE = "image_style"           # 图片风格
    IMAGE_COMPOSITION = "image_composition"  # 图片构图
    IMAGE_COLOR = "image_color"           # 图片配色
    PROMPT_GENERATION = "prompt_generation"  # Prompt 生成
    HEADLINE = "headline"                 # 文案 Headline
    PRIMARY_TEXT = "primary_text"         # 文案 Primary Text
    DESCRIPTION = "description"           # 文案 Description
    CTA = "cta"                           # 行动号召
    VIDEO_STYLE = "video_style"           # 视频风格
    
    # 投放类（规则域）
    BUDGET_ALLOCATION = "budget_allocation"  # 预算分配
    BUDGET_CAP = "budget_cap"              # 预算上限
    BID_AMOUNT = "bid_amount"              # 出价金额
    PAUSE_DECISION = "pause_decision"      # 暂停决策
    KILL_DECISION = "kill_decision"        # 关停决策
    SCALE_UP = "scale_up"                  # 扩大投放
    SCALE_DOWN = "scale_down"              # 缩减投放
    DUPLICATE = "duplicate"                # 复制广告
    
    # 定向类（混合域）
    AUDIENCE_SELECTION = "audience_selection"  # 受众选择
    COUNTRY_SELECTION = "country_selection"    # 国家选择
    PLACEMENT = "placement"                    # 版位选择
    TARGETING_EXPANSION = "targeting_expansion"  # 定向扩展
    
    # 策略类（混合域）
    CAMPAIGN_STRUCTURE = "campaign_structure"  # ABO/CBO/ASC 选择
    OPTIMIZATION_GOAL = "optimization_goal"    # 优化目标
    ATTRIBUTION_WINDOW = "attribution_window"  # 归因窗口
    
    # 学习类（AI 域）
    WINNER_IDENTIFICATION = "winner_identification"  # 赢家识别
    LOSER_IDENTIFICATION = "loser_identification"    # 输家识别
    PATTERN_DISCOVERY = "pattern_discovery"          # 模式发现
    KNOWLEDGE_UPDATE = "knowledge_update"            # 知识库更新
```

---

## §4 边界映射表

### AI 域（9 个类别）

| Category | 负责模块 | 理由 |
|----------|---------|------|
| IMAGE_STYLE | creative_strategy_matrix | 图片风格是创意决策，AI 通过 Bandit 反馈学习最佳风格 |
| IMAGE_COMPOSITION | creative_strategy_matrix | 构图是创意决策，AI 通过 DNA 分析学习 |
| IMAGE_COLOR | creative_strategy_matrix | 配色是创意决策，不同国家/受众偏好不同，AI 学习 |
| PROMPT_GENERATION | prompt_builder | Prompt 生成是纯创意任务，AI 根据基因+变异生成 |
| HEADLINE | copy_generator | 文案是创意内容，AI 根据 Hook/Emotion/Reward 生成 |
| PRIMARY_TEXT | copy_generator | Primary Text 是创意内容，AI 根据游戏类型/受众生成 |
| DESCRIPTION | copy_generator | Description 是创意内容，AI 根据游戏类型生成 |
| CTA | copy_generator | CTA 文案是创意内容，AI 可根据变体策略选择 |
| VIDEO_STYLE | video_generator | 视频风格是创意决策（待实现） |

**Override Conditions**：
- 合规要求（如某些国家禁止特定内容）
- Facebook 平台限制（某些 CTA 类型需审批）

### 规则域（8 个类别）

| Category | 负责模块 | 理由 |
|----------|---------|------|
| BUDGET_ALLOCATION | final_bandit + distribution_controller | 预算分配需要三层保护，规则保证安全 |
| BUDGET_CAP | guarded_execution | 预算上限是风控决策，必须由规则严格控制 |
| BID_AMOUNT | campaign_strategy | 出价是资金风险决策，规则根据目标 CPI 设定上限 |
| PAUSE_DECISION | kpi_action_rulebook | 暂停是高风险决策，需要明确规则触发，AI 不能随意暂停 |
| KILL_DECISION | kpi_action_rulebook + guarded_execution | 关停是最高风险决策，必须由规则触发 |
| SCALE_UP | kpi_action_rulebook | 扩量需要规则审核（ROAS>2、CPI<目标），AI 不能无限扩量 |
| SCALE_DOWN | kpi_action_rulebook | 缩量由规则触发，AI 不能随意缩量导致数据中断 |
| DUPLICATE | facebook_executor | 复制广告是工程操作，需要规则确认 |

### 混合域（7 个类别）

| Category | 负责模块 | 理由 |
|----------|---------|------|
| AUDIENCE_SELECTION | campaign_strategy + kpi_action_rulebook | 受众选择：AI 推荐 + 规则根据 CPM/ROAS 审核 |
| COUNTRY_SELECTION | campaign_strategy + growth_priorities | 国家选择：AI 根据增长优先级推荐 + 规则审核预算 |
| PLACEMENT | campaign_strategy | 版位选择：AI 根据游戏类型推荐 + 规则根据平台限制审核 |
| CAMPAIGN_STRUCTURE | campaign_strategy | ABO/CBO/ASC：AI 根据历史数据建议 + 规则根据预算审核 |
| WINNER_IDENTIFICATION | winner_engine + decision_engine | 赢家识别：AI（Bandit）根据统计显著性建议 + 规则审核最小样本量 |
| LOSER_IDENTIFICATION | loser_engine + kpi_action_rulebook | 输家识别：AI 根据表现排序建议 + 规则审核最小花费 |
| PATTERN_DISCOVERY | creative_dna + creative_clusters | 模式发现是纯 AI 任务 |

---

## §5 DomainAssignment 对象

```python
@dataclass
class DomainAssignment:
    category: DecisionCategory
    domain: DecisionDomain
    responsible_module: str
    reason: str
    override_conditions: List[str]
```

---

## §6 接口定义

```python
class DecisionBoundary:
    def get_domain(category: DecisionCategory) -> DecisionDomain
    def get_responsible_module(category: DecisionCategory) -> str
    
    def is_ai_decision(category: DecisionCategory) -> bool
    def is_rule_decision(category: DecisionCategory) -> bool
    def is_hybrid_decision(category: DecisionCategory) -> bool
    
    def get_ai_categories() -> List[DecisionCategory]
    def get_rule_categories() -> List[DecisionCategory]
    def get_hybrid_categories() -> List[DecisionCategory]
    
    def audit_decision(
        category: DecisionCategory,
        actual_domain: DecisionDomain
    ) -> Dict
    
    def get_all_assignments() -> Dict[str, DomainAssignment]
    def export_boundary_map() -> List[Dict]
```

---

## §7 审计输出

```python
boundary = DecisionBoundary()
result = boundary.audit_decision(DecisionCategory.HEADLINE, DecisionDomain.RULE)
```

输出：
```python
{
    "valid": False,
    "expected_domain": DecisionDomain.AI,
    "actual_domain": DecisionDomain.RULE,
    "message": "WARNING: headline 应在 ai 域执行，实际在 rule 域"
}
```

---

## §8 与主流程集成

接入 `run_pipeline.py` Step 6 审计层：

```python
boundary = DecisionBoundary()
budget_audit = boundary.audit_decision(
    DecisionCategory.BUDGET_ALLOCATION,
    DecisionDomain.RULE
)
creative_audit = boundary.audit_decision(
    DecisionCategory.IMAGE_STYLE,
    DecisionDomain.AI
)
print(f"BUDGET_ALLOCATION → RULE: {budget_audit['message']}")
print(f"IMAGE_STYLE → AI: {creative_audit['message']}")
```

---

## §9 统计

| 域 | 类别数 | 说明 |
|----|--------|------|
| AI 域 | 9 | 创意内容，生成式 AI + Bandit |
| 规则域 | 8 | 投放控制，风控 + 显式规则 |
| 混合域 | 7 | 策略选择，AI 建议 + 规则审核 |
| **总计** | **24** | 全部决策类别 |

---

## §10 设计原则

1. **安全优先**：资金相关决策（预算/暂停/关停）归规则域
2. **创意自由**：内容相关决策（图片/文案/视频）归 AI 域
3. **审核平衡**：策略相关决策（受众/国家/结构）归混合域
4. **可审计**：每个决策必须知道谁做的、为什么做
5. **独立调优**：AI 域和规则域可独立优化，互不干扰