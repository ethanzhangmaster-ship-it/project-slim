# LiveOps Agent Spec（AI Game Studio OS Phase 1）

> 状态：定义中（实现前锁定）
> 优先级：P0（AI Game Studio OS Phase 1 — 补齐生命周期运营部）
> 目标：让 LiveOps Agent 能基于流失信号自动设计回流活动，接入 workspace 组织架构

---

## 1. 定位（不重新发明轮子）

LiveOps Agent **不是** 新建一套活动管理系统，而是**桥接**已有的流失检测能力 → 自动触发回流活动设计。

```
现有能力（可直接复用）:

  operation/player_monetization/
    ├─ LifecycleDetector   → 识别 LAPSED/CHURNING 用户
    ├─ PlayerSegmenter     → 识别 at_risk_churn 分群
    └─ ValuePredictor      → 预测用户价值

  reality/analyzers/
    └─ lifecycle_analyzer  → churn_risk_users 流失风险用户清单

  v9_company/product_division/
    └─ liveops_manager.py  → Mock 活动模型 (LiveEvent/EventCalendar)

缺失（需新建）:
  ❌ LiveOpsAgent 类
  ❌ churn_risk_users → 回流活动触发链路
  ❌ 活动设计 → 执行 → 效果追踪闭环
  ❌ workspace 组织架构接入
```

统一职责一句话：**新建 LiveOpsAgent 类，消费 LifecycleDetector/PlayerSegmenter 的流失信号，自动生成回流活动方案，接入 workspace AgentRegistry 和 HTTP API。**

纪律红线（继承全库 + memory 约束）：
- **禁止**新增算法层或新版本，复用 player_monetization 现有模块
- **禁止**修改 v9_company/liveops_manager.py（仅参考数据模型，不导入）
- **必须**复用 AgentRegistry 注册机制
- **必须**默认 dry_run，活动方案只生成不执行
- **禁止**硬编码活动模板，活动参数走配置

---

## 2. 方案设计

### 2.1 LiveOpsAgent 类

位置：`src/market_ops/workspace/liveops_agent.py`

```python
class LiveOpsAgent:
    """LiveOps Agent — 消费流失信号，自动设计回流活动."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir

    def analyze_churn_risk(self, game_id: str) -> ChurnAnalysis:
        """分析流失风险，返回风险用户分群和建议."""

    def design_winback_campaign(self, game_id: str, analysis: ChurnAnalysis) -> WinbackCampaign:
        """基于流失分析设计回流活动方案."""

    def evaluate_campaign(self, campaign_id: str) -> CampaignEvaluation:
        """评估活动效果（对比前后指标）."""
```

### 2.2 数据模型

```python
@dataclass
class ChurnAnalysis:
    game_id: str
    analysis_date: str
    total_players: int
    at_risk_count: int           # at_risk_churn 分群数
    lapsed_count: int            # LAPSED 阶段数
    churning_count: int          # CHURNING 阶段数
    avg_churn_risk: float        # 平均流失风险分
    segments: dict[str, int]     # 分群分布
    lifecycle_stages: dict[str, int]  # 生命周期阶段分布
    high_value_at_risk: int      # 高价值流失风险用户数

@dataclass
class WinbackCampaign:
    campaign_id: str
    game_id: str
    campaign_type: str           # login_bonus / discount / special_offer / push_re-engagement
    target_segment: str          # at_risk_churn / lapsed / churning
    target_count: int
    rewards_pool: float
    duration_days: int
    expected_participation: float
    expected_retention_uplift: float
    actions: list[CampaignAction]
    created_at: str

@dataclass
class CampaignAction:
    action_type: str             # push_notification / in_app_message / reward_grant / email
    target_count: int
    content: str
    trigger_delay_hours: int     # 延迟触发小时数

@dataclass
class CampaignEvaluation:
    campaign_id: str
    participation_rate: float
    retention_uplift: float
    revenue_uplift: float
    player_satisfaction: float
```

### 2.3 HTTP API

```
GET  /api/liveops/churn-analysis/{game_id}    — 获取流失分析
POST /api/liveops/winback-campaign             — 设计回流活动
GET  /api/liveops/campaigns                    — 活动列表
GET  /api/liveops/campaigns/{campaign_id}      — 活动详情
POST /api/liveops/campaigns/{campaign_id}/evaluate — 评估活动效果
```

### 2.4 Agent 注册

1. `AgentRole` 枚举新增 `LIVEOPS = "liveops"`
2. `agent_message.py` 新增 `create_liveops_agent_identity()` 工厂
3. `create_default_organization()` 注册 LiveOpsAgent
4. `real_provider.py` 的 `_ROLE_TO_DEPARTMENT` 新增 `"liveops": "LiveOps"`

---

## 3. 实现范围

### 3.1 新建文件

- `src/market_ops/workspace/liveops_agent.py` — LiveOpsAgent 类 + 数据模型
- `tests/test_liveops_agent.py` — 单元测试

### 3.2 修改文件

- `src/market_ops/creative_vision_runtime/growth_runtime/agent/communication/agent_message.py` — 新增 LIVEOPS 角色和工厂
- `src/market_ops/creative_vision_runtime/growth_runtime/agent/communication/agent_registry.py` — create_default_organization 注册 LiveOps
- `src/market_ops/workspace/real_provider.py` — _ROLE_TO_DEPARTMENT 新增 liveops 映射
- `src/market_ops/workspace/app.py` — 新增 LiveOps API 端点
- `workspace/src/lib/api.ts` — 新增 LiveOps API 方法
- `workspace/src/app/page.tsx` — Dashboard 新增 LiveOps 区域

### 3.3 不在本次范围

- ❌ 不实现真实 Push 通知发送（仅生成动作方案）
- ❌ 不实现真实邮件发送
- ❌ 不接入 ThinkingData SQL API（用 player_monetization 的规则引擎）
- ❌ 不实现 A/B 实验框架
- ❌ 不修改 v9_company 代码

---

## 4. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| §4.1 | LiveOpsAgent.analyze_churn_risk 返回完整 ChurnAnalysis | 单元测试 |
| §4.2 | LiveOpsAgent.design_winback_campaign 返回 WinbackCampaign | 单元测试 |
| §4.3 | 回流活动方案基于流失分群自动选择类型 | 单元测试验证不同分群产生不同方案 |
| §4.4 | AgentRegistry 能注册和发现 liveops 角色 | 单元测试 |
| §4.5 | workspace /api/agents 返回 LiveOps Agent | API 测试 |
| §4.6 | GET /api/liveops/churn-analysis/{game_id} 返回 200 | API 测试 |
| §4.7 | POST /api/liveops/winback-campaign 返回 200 + 活动方案 | API 测试 |
| §4.8 | 前端 Dashboard 展示流失分析和活动方案 | UI 验证 |
| §4.9 | 单元测试覆盖（≥15 个用例） | pytest 验证 |
| §4.10 | 现有测试无回归 | 全量测试验证 |

---

## 5. 依赖扫描（已逐项核对）

- [operation/player_monetization/user_profile/lifecycle.py](file:///d:/project_slim/project_slim/operation/player_monetization/user_profile/lifecycle.py) `LifecycleDetector.stage()`
- [operation/player_monetization/user_profile/player_segment.py](file:///d:/project_slim/project_slim/operation/player_monetization/user_profile/player_segment.py) `PlayerSegmenter.classify()`
- [operation/player_monetization/events/collector.py](file:///d:/project_slim/project_slim/operation/player_monetization/events/collector.py) `EventCollector.collect()`
- [operation/player_monetization/models.py](file:///d:/project_slim/project_slim/operation/player_monetization/models.py) `PlayerProfile/PlayerSegment`
- [src/market_ops/creative_vision_runtime/growth_runtime/agent/communication/agent_message.py](file:///d:/project_slim/project_slim/src/market_ops/creative_vision_runtime/growth_runtime/agent/communication/agent_message.py) `AgentRole/create_agent_identity`
- [src/market_ops/creative_vision_runtime/growth_runtime/agent/communication/agent_registry.py](file:///d:/project_slim/project_slim/src/market_ops/creative_vision_runtime/growth_runtime/agent/communication/agent_registry.py) `create_default_organization`
- [src/market_ops/workspace/real_provider.py](file:///d:/project_slim/project_slim/src/market_ops/workspace/real_provider.py) `_ROLE_TO_DEPARTMENT`
- [src/market_ops/workspace/app.py](file:///d:/project_slim/project_slim/src/market_ops/workspace/app.py) 现有端点模式
