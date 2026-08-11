# Campaign Strategy Builder Spec v1.0

> **Campaign/AdSet 自动创建策略**。预算/目标/复杂度 → ABO/CBO/ASC + Targeting + Budget + Bid。
> 任何代码修改必须遵循此 Spec。

---

## §1 设计目标

从"只能改预算"升级为"端到端创建投放结构"，实现：
- **策略自动选择**：预算<$500 → ABO，>=500 且多AdSet → CBO，Advantage+ → ASC
- **Targeting 自动构建**：国家/年龄/兴趣/自定义受众/Lookalike
- **Bid 策略自动选择**：有目标CPI → COST_CAP，默认 → LOWEST_COST
- **完整投放配置**：CampaignConfig + AdSetConfig 一键生成

### 核心约束（强约束）

- ❌ 不允许绕过三层预算保护直接创建广告
- ❌ 不允许 ABO 模式下所有国家共用一个 AdSet
- ✔ Campaign 创建必须 PAUSED 状态（安全启动）
- ✔ AdSet 预算单位为分（Facebook API 要求）
- ✔ Targeting 必须包含 `age_min >= 18`
- ✔ 支持 CBO/ASC 的 budget pooling

---

## §2 数据流

```
Project + Budget + Countries + GameCategory → CampaignStrategyBuilder → (CampaignConfig + AdSetConfig[])
```

输入：
- `project_name`：项目名称（P04）
- `daily_budget`：日预算（美元）
- `countries`：目标国家列表
- `game_category`：游戏类型
- `is_broad`：是否 Broad targeting
- `target_cpi`：目标 CPI（可选）
- `custom_audience_ids`：自定义受众 ID（可选）
- `lookalike_audience_ids`：Lookalike 受众 ID（可选）
- `use_advantage_plus`：是否使用 ASC

输出：
- `CampaignConfig`：Campaign 创建参数
- `AdSetConfig[]`：多个 AdSet 创建参数

---

## §3 核心对象

### CampaignConfig

| 字段 | 类型 | 说明 |
|---|---|---|
| name | str | Campaign 名称 |
| objective | CampaignObjective | 投放目标（APP_INSTALLS / CONVERSIONS / LINK_CLICKS） |
| buying_type | CampaignBuyingType | 购买类型（AUCTION / RESERVED） |
| status | str | 初始状态（PAUSED / ACTIVE） |
| special_ad_categories | List[str] | 特殊广告类别（NONE / HOUSING / EMPLOYMENT / CREDIT） |
| strategy | CampaignStrategy | 投放策略（ABO / CBO / ASC） |

### AdSetConfig

| 字段 | 类型 | 说明 |
|---|---|---|
| name | str | AdSet 名称 |
| campaign_id | str | 所属 Campaign ID |
| daily_budget | int | 日预算（分） |
| lifetime_budget | int | 总预算（分） |
| optimization_goal | OptimizationGoal | 优化目标（APP_INSTALLS / IMPRESSIONS / VALUE / CONVERSIONS） |
| billing_event | BillingEvent | 计费事件（IMPRESSIONS / LINK_CLICKS / APP_INSTALLS） |
| bid_strategy | BidStrategy | 出价策略（LOWEST_COST_WITHOUT_CAP / COST_CAP / LOWEST_COST_WITH_BID_CAP） |
| bid_amount | int | 出价上限（分） |
| targeting | TargetingConfig | 定向配置 |
| placements | List[str] | 版位列表（空=自动版位） |
| attribution_spec | List[Dict] | 归因配置（默认 7天点击+1天浏览） |
| status | str | 状态（PAUSED / ACTIVE） |

### TargetingConfig

| 字段 | 类型 | 说明 |
|---|---|---|
| countries | List[str] | 国家代码列表 |
| age_min | int | 最小年龄（默认 18） |
| age_max | int | 最大年龄（默认 65） |
| genders | List[int] | 性别（1=男, 2=女） |
| languages | List[str] | 语言代码列表 |
| interests | List[Dict] | 兴趣定位 |
| behaviors | List[Dict] | 行为定位 |
| custom_audiences | List[Dict] | 自定义受众 |
| lookalike_audiences | List[Dict] | Lookalike 受众 |
| excluded_custom_audiences | List[Dict] | 排除受众 |
| is_broad | bool | 是否 Broad targeting |

---

## §4 策略选择规则

### Campaign Strategy 选择

```python
def select_campaign_strategy(budget, adset_count, use_advantage_plus):
    if use_advantage_plus:
        return ASC
    if budget >= 500 and adset_count >= 3:
        return CBO
    return ABO
```

**理由**：
- ABO：预算低时每个 AdSet 独立预算，方便精细化控制
- CBO：预算高时 Facebook 自动优化分配，减少人工干预
- ASC：Advantage+ Shopping Campaign，Facebook 全自动优化

### Bid Strategy 选择

```python
def select_bid_strategy(daily_budget, target_cpi, target_roas):
    if target_cpi and target_cpi > 0:
        return COST_CAP, cost_cap=target_cpi
    return LOWEST_COST_WITHOUT_CAP
```

**理由**：
- COST_CAP：有明确 CPI 目标时，Facebook 自动控制成本
- LOWEST_COST：无目标时，让 Facebook 用最低成本获取最多安装

### Placement 选择

```python
def select_placements(game_category, use_automatic_placements):
    if use_automatic_placements:
        return []  # 空列表 = 自动版位
    
    placements = [
        "facebook_feed",
        "facebook_video_feeds",
        "facebook_reels",
        "instagram_feed",
        "instagram_stories",
        "instagram_reels",
    ]
    
    if game_category in ("hyper_casual", "casual"):
        placements.extend([
            "audience_network_rewarded_video",
            "audience_network_native",
        ])
    
    return placements
```

---

## §5 Targeting 构建

### 国家 → 语言推断

```python
COUNTRY_LANGUAGE_MAP = {
    "CN": ["zh_CN"],
    "HK": ["zh_HK"],
    "TW": ["zh_TW"],
    "JP": ["ja_JP"],
    "KR": ["ko_KR"],
    "US": ["en_US"],
    "GB": ["en_GB"],
    "DE": ["de_DE"],
    "FR": ["fr_FR"],
    "ES": ["es_ES"],
    ...
}
```

### 游戏类型 → 兴趣推荐

```python
GAME_INTEREST_KEYWORDS = {
    "puzzle": ["Puzzle video game", "Brain teaser", "Logic puzzle"],
    "rpg": ["Role-playing video game", "Fantasy", "Dungeon game"],
    "casual": ["Casual game", "Mobile game", "Arcade game"],
    "strategy": ["Strategy video game", "Tower defense", "Real-time strategy"],
    "hyper_casual": ["Hyper-casual game", "Clicker game", "Idle game"],
    "match3": ["Match-3 game", "Tile-matching video game", "Candy Crush"],
    "simulation": ["Simulation video game", "Virtual world", "Life simulation game"],
    "action": ["Action game", "Fighting game", "Shooter game"],
}
```

---

## §6 接口定义

```python
class CampaignStrategyBuilder:
    def select_campaign_strategy(budget, adset_count, use_advantage_plus) -> CampaignStrategy
    def build_targeting(countries, game_category, age_min, age_max, is_broad, ...) -> TargetingConfig
    def select_bid_strategy(daily_budget, target_cpi, target_roas) -> (BidStrategy, bid_amount, cost_cap)
    def select_placements(game_category, use_automatic_placements) -> List[str]
    
    def build_campaign(name, objective, strategy, status) -> CampaignConfig
    def build_adset(name, campaign_id, daily_budget, countries, ...) -> AdSetConfig
    
    def build_full_campaign(
        project_name,
        daily_budget,
        countries,
        game_category,
        adset_count,
        is_broad,
        target_cpi,
        use_advantage_plus,
        custom_audience_ids,
        lookalike_audience_ids
    ) -> Dict[str, Any]  # {"campaign": CampaignConfig, "adsets": [AdSetConfig]}
```

---

## §7 与 FacebookPublisher 集成

```python
from campaign_strategy import CampaignStrategyBuilder
from facebook_publisher import FacebookPublisher

builder = CampaignStrategyBuilder()
full = builder.build_full_campaign("P04", 500, ["US", "JP"], "match3")

publisher = FacebookPublisher(access_token, ad_account_id)
campaign_id = publisher.create_campaign_from_config(full["campaign"])

for adset_config in full["adsets"]:
    adset_config.campaign_id = campaign_id
    adset_id = publisher.create_adset_from_config(adset_config)
```

---

## §8 输出文件

运行后生成：
- `output/campaign_strategy.json`：投放结构配置

格式：
```json
{
  "campaign": {
    "name": "P04_Auto_CBO",
    "objective": "APP_INSTALLS",
    "strategy": "CBO",
    "status": "PAUSED"
  },
  "adsets": [
    {
      "name": "P04_AllCountries_match3",
      "daily_budget": 50000,
      "countries": ["US", "JP", "CN"],
      "optimization_goal": "APP_INSTALLS",
      "bid_strategy": "LOWEST_COST_WITHOUT_CAP"
    }
  ]
}
```

---

## §9 与主流程集成

接入 `run_pipeline.py` Step 5.3：

```python
step5_3_result = step5_3_campaign_strategy(
    results,
    game_category,
    daily_budget,
    project_name
)
```

输出文件：`output/campaign_strategy.json`