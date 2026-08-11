"""KPI → Action 显式规则手册

将优化逻辑从隐式加权评分中提取为显式 if-then 规则。
每条规则回答：哪个指标异常 → 什么原因 → 应该做什么 → 不应该做什么

设计原则：
- 每个决策必须可审计（知道为什么触发）
- 每个规则有优先级和置信度
- 规则冲突时有明确的优先级排序
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ActionType(str, Enum):
    """优化动作类型"""
    # 预算相关
    SCALE_UP = "scale_up"  # 加预算
    SCALE_DOWN = "scale_down"  # 降预算
    PAUSE = "pause"  # 暂停
    KILL = "kill"  # 彻底停掉

    # 创意相关
    CHANGE_CREATIVE = "change_creative"  # 换素材
    CHANGE_HEADLINE = "change_headline"  # 换文案
    CHANGE_CTA = "change_cta"  # 换CTA
    CHANGE_IMAGE = "change_image"  # 换图片

    # 定向相关
    CHANGE_AUDIENCE = "change_audience"  # 换受众
    CHANGE_COUNTRY = "change_country"  # 换国家
    BROADEN_TARGETING = "broaden_targeting"  # 放宽定向
    NARROW_TARGETING = "narrow_targeting"  # 收紧定向

    # 出价相关
    INCREASE_BID = "increase_bid"  # 加出价
    DECREASE_BID = "decrease_bid"  # 降出价
    SET_COST_CAP = "set_cost_cap"  # 设成本上限

    # 观察
    HOLD = "hold"  # 保持观察
    MONITOR = "monitor"  # 密切监控
    REPAIR = "repair"  # 修复投放
    DATA_BLOCKED = "data_blocked"  # 数据不足，无法决策


class KpiMetric(str, Enum):
    """监控的KPI指标"""
    CTR = "ctr"  # 点击率
    CPM = "cpm"  # 千次展示成本
    CPC = "cpc"  # 单次点击成本
    CPI = "cpi"  # 单次安装成本
    CPA = "cpa"  # 单次行动成本（购买/注册）
    ROAS = "roas"  # 广告支出回报率
    IPM = "ipm"  # 千次展示安装
    IMPRESSIONS = "impressions"  # 展示量
    CLICKS = "clicks"  # 点击量
    INSTALLS = "installs"  # 安装量
    SPEND = "spend"  # 花费
    FREQUENCY = "frequency"  # 频次


class Severity(str, Enum):
    """异常严重程度"""
    CRITICAL = "critical"  # 严重，需立即处理
    WARNING = "warning"  # 警告，需要关注
    INFO = "info"  # 信息，正常波动


# ---------------------------------------------------------------------------
# Rule Dataclass
# ---------------------------------------------------------------------------

@dataclass
class KpiRule:
    """单条KPI规则"""
    rule_id: str
    description: str  # 人类可读的规则描述
    condition: KpiMetric  # 触发指标
    threshold_operator: str  # ">" or "<"
    threshold_value: float  # 阈值
    threshold_unit: str  # "%" or "$" or "absolute"
    action: ActionType  # 推荐动作
    severity: Severity  # 严重程度
    priority: int  # 优先级（1最高）
    reason: str  # 为什么这么做
    anti_action: ActionType  # 不应该做什么（常见错误做法）
    anti_reason: str  # 为什么不应该那么做

    def matches(self, metric_value: float) -> bool:
        """检查指标值是否触发此规则"""
        if self.threshold_operator == ">":
            return metric_value > self.threshold_value
        elif self.threshold_operator == "<":
            return metric_value < self.threshold_value
        elif self.threshold_operator == ">=":
            return metric_value >= self.threshold_value
        elif self.threshold_operator == "<=":
            return metric_value <= self.threshold_value
        return False


# ---------------------------------------------------------------------------
# KPI Rulebook
# ---------------------------------------------------------------------------

class KpiActionRulebook:
    """KPI → Action 显式规则手册

    规则优先级：越靠前优先级越高，冲突时取第一个匹配的高优先级规则。
    """

    RULES: List[KpiRule] = [
        # ── CTR 相关 ──
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
        ),
        KpiRule(
            rule_id="CTR_HIGH_CPI_HIGH",
            description="CTR高但CPI高 → 落地页/商店页问题，非素材问题",
            condition=KpiMetric.CTR,
            threshold_operator=">",
            threshold_value=2.0,
            threshold_unit="%",
            action=ActionType.MONITOR,
            severity=Severity.WARNING,
            priority=2,
            reason="CTR高=素材好，CPI高=转化问题，可能是商店页/App本身问题，素材不需要换。",
            anti_action=ActionType.CHANGE_CREATIVE,
            anti_reason="CTR高时换素材反而可能降低CTR，应检查转化链路。",
        ),
        KpiRule(
            rule_id="CTR_VERY_HIGH",
            description="CTR极高但ROAS低 → 素材诱导点击，需检查相关性",
            condition=KpiMetric.CTR,
            threshold_operator=">",
            threshold_value=5.0,
            threshold_unit="%",
            action=ActionType.CHANGE_CREATIVE,
            severity=Severity.WARNING,
            priority=3,
            reason="CTR过高可能是素材诱导点击（clickbait），用户点进去发现不是预期内容就离开，ROAS差。",
            anti_action=ActionType.SCALE_UP,
            anti_reason="高CTR不等于好素材，诱导点击可能浪费预算。",
        ),

        # ── CPM 相关 ──
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
        ),
        KpiRule(
            rule_id="CPM_SPIKE",
            description="CPM 突然飙升 → 竞争对手进入，检查是否节假日/大促",
            condition=KpiMetric.CPM,
            threshold_operator=">",
            threshold_value=50.0,
            threshold_unit="$",
            action=ActionType.SCALE_DOWN,
            severity=Severity.CRITICAL,
            priority=2,
            reason="CPM突然飙升通常是外部因素（竞品大推/节假日），短期降预算避风头，等回归正常再恢复。",
            anti_action=ActionType.INCREASE_BID,
            anti_reason="加出价只会让CPM更高，与竞品竞价战只会互相伤害。",
        ),
        KpiRule(
            rule_id="CPM_LOW_CTR_LOW",
            description="CPM低但CTR低 → 展示给了不感兴趣的人，收紧定向",
            condition=KpiMetric.CPM,
            threshold_operator="<",
            threshold_value=5.0,
            threshold_unit="$",
            action=ActionType.NARROW_TARGETING,
            severity=Severity.WARNING,
            priority=3,
            reason="CPM低说明受众便宜但可能不精准，CTR低=不感兴趣，应收紧定向提高精准度。",
            anti_action=ActionType.CHANGE_CREATIVE,
            anti_reason="CPM低时CTR低更可能是定向问题而非素材问题。",
        ),

        # ── CPI 相关 ──
        KpiRule(
            rule_id="CPI_TOO_HIGH",
            description="CPI 过高 → 换素材（优化转化率），不要降预算",
            condition=KpiMetric.CPI,
            threshold_operator=">",
            threshold_value=5.0,
            threshold_unit="$",
            action=ActionType.CHANGE_CREATIVE,
            severity=Severity.CRITICAL,
            priority=1,
            reason="CPI=CPM/CTR/IPM，高CPI可能是素材转化率低，换素材最直接。低CPI时用预算压制。",
            anti_action=ActionType.SCALE_DOWN,
            anti_reason="降预算不解决CPI高的问题，只是让量更少。",
        ),
        KpiRule(
            rule_id="CPI_LOW_SCALE",
            description="CPI 低 → 加预算，用预算压制市场",
            condition=KpiMetric.CPI,
            threshold_operator="<",
            threshold_value=1.0,
            threshold_unit="$",
            action=ActionType.SCALE_UP,
            severity=Severity.INFO,
            priority=4,
            reason="CPI低于目标，说明当前素材效率高，应该加预算获取更多用户。",
            anti_action=ActionType.CHANGE_CREATIVE,
            anti_reason="CPI低时换素材可能破坏当前好状态，先加预算收割。",
        ),

        # ── ROAS 相关 ──
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
        ),
        KpiRule(
            rule_id="ROAS_DECLINING",
            description="ROAS 持续下降 → 素材疲劳，换素材",
            condition=KpiMetric.ROAS,
            threshold_operator="<",
            threshold_value=1.0,
            threshold_unit="absolute",
            action=ActionType.CHANGE_CREATIVE,
            severity=Severity.WARNING,
            priority=2,
            reason="ROAS下降但还没到临界点，说明素材疲劳，及时换素材可以止损。",
            anti_action=ActionType.SCALE_UP,
            anti_reason="ROAS下降时加预算只会加速亏损。",
        ),
        KpiRule(
            rule_id="ROAS_HIGH_SCALE",
            description="ROAS 高 → 加预算",
            condition=KpiMetric.ROAS,
            threshold_operator=">",
            threshold_value=2.0,
            threshold_unit="absolute",
            action=ActionType.SCALE_UP,
            severity=Severity.INFO,
            priority=5,
            reason="ROAS>2=盈利，应加预算扩大盈利规模。",
            anti_action=ActionType.CHANGE_CREATIVE,
            anti_reason="ROAS高时不要轻易换素材，先加预算收割。",
        ),

        # ── Frequency 相关 ──
        KpiRule(
            rule_id="FREQUENCY_TOO_HIGH",
            description="频次过高 → 素材疲劳，换素材",
            condition=KpiMetric.FREQUENCY,
            threshold_operator=">",
            threshold_value=3.0,
            threshold_unit="absolute",
            action=ActionType.CHANGE_CREATIVE,
            severity=Severity.CRITICAL,
            priority=1,
            reason="频次>3说明同一批人在反复看同一素材，审美疲劳，CTR和ROAS都会下降。",
            anti_action=ActionType.SCALE_DOWN,
            anti_reason="降预算不能解决频次问题，受众已经看腻了，需要新素材。",
        ),

        # ── Spend 相关 ──
        KpiRule(
            rule_id="SPEND_LIMITED",
            description="预算花不出去 → 放宽定向或加出价",
            condition=KpiMetric.SPEND,
            threshold_operator="<",
            threshold_value=0.5,  # 花不到预算的50%
            threshold_unit="absolute",
            action=ActionType.BROADEN_TARGETING,
            severity=Severity.WARNING,
            priority=3,
            reason="预算花不出去说明受众太窄/出价太低，放宽定向或加出价。",
            anti_action=ActionType.CHANGE_CREATIVE,
            anti_reason="预算花不出去时换素材不能解决展示量问题。",
        ),

        # ── IPM 相关 ──
        KpiRule(
            rule_id="IPM_TOO_LOW",
            description="IPM过低 → 素材不吸引安装，换素材",
            condition=KpiMetric.IPM,
            threshold_operator="<",
            threshold_value=5.0,
            threshold_unit="absolute",
            action=ActionType.CHANGE_CREATIVE,
            severity=Severity.WARNING,
            priority=2,
            reason="IPM（千次展示安装）低说明素材能吸引点击但无法驱动安装，需要换素材。",
            anti_action=ActionType.CHANGE_AUDIENCE,
            anti_reason="IPM低优先换素材，换受众可能让CPM更高。",
        ),

        # ── Impressions 相关 ──
        KpiRule(
            rule_id="IMPRESSIONS_DROPPING",
            description="展示量持续下降 → 竞争加剧或受众耗尽",
            condition=KpiMetric.IMPRESSIONS,
            threshold_operator="<",
            threshold_value=1000,
            threshold_unit="absolute",
            action=ActionType.CHANGE_AUDIENCE,
            severity=Severity.WARNING,
            priority=3,
            reason="展示量下降说明当前受众池可能耗尽或竞争加剧，需要换受众或加出价。",
            anti_action=ActionType.CHANGE_CREATIVE,
            anti_reason="展示量下降时换素材不能解决受众池问题。",
        ),
    ]

    def __init__(self, custom_thresholds: Optional[Dict[str, Dict]] = None):
        """初始化规则手册

        Args:
            custom_thresholds: 自定义阈值覆盖，格式 {rule_id: {"threshold_value": new_value, "threshold_operator": ">"}}
        """
        self._rules = list(self.RULES)  # copy
        if custom_thresholds:
            self._apply_custom_thresholds(custom_thresholds)

    def _apply_custom_thresholds(self, custom: Dict[str, Dict]):
        """应用自定义阈值覆盖"""
        for rule in self._rules:
            if rule.rule_id in custom:
                override = custom[rule.rule_id]
                if "threshold_value" in override:
                    rule.threshold_value = override["threshold_value"]
                if "threshold_operator" in override:
                    rule.threshold_operator = override["threshold_operator"]

    # ------------------------------------------------------------------
    # 核心评估方法
    # ------------------------------------------------------------------

    def evaluate(
        self,
        metrics: Dict[KpiMetric, float],
        min_spend: float = 0.0,
        min_impressions: int = 100,
    ) -> List[KpiRule]:
        """评估当前KPI指标，返回触发规则的Action列表

        Args:
            metrics: {KpiMetric: value} 当前指标快照
            min_spend: 最小花费阈值（低于此值不触发决策，数据不足）
            min_impressions: 最小展示量阈值

        Returns:
            触发的规则列表，按优先级排序
        """
        triggered: List[KpiRule] = []

        # 数据充足性检查
        spend = metrics.get(KpiMetric.SPEND, 0)
        impressions = metrics.get(KpiMetric.IMPRESSIONS, 0)
        if spend < min_spend or impressions < min_impressions:
            # 数据不足，返回 DATA_BLOCKED
            return [self._create_data_blocked_rule(spend, impressions)]

        for rule in self._rules:
            if rule.condition in metrics:
                value = metrics[rule.condition]
                if rule.matches(value):
                    triggered.append(rule)

        # 按优先级排序
        triggered.sort(key=lambda r: r.priority)
        return triggered

    def evaluate_with_context(
        self,
        metrics: Dict[KpiMetric, float],
        creative_age_days: int = 0,
        min_spend: float = 10.0,
        min_impressions: int = 1000,
    ) -> Dict:
        """带上下文的综合评估，返回结构化决策

        Args:
            metrics: KPI指标快照
            creative_age_days: 素材已经投放的天数
            min_spend: 最小花费
            min_impressions: 最小展示量

        Returns:
            {
                "decision": ActionType,  # 最终决策
                "triggered_rules": [str],  # 触发的规则ID列表
                "explanations": [str],  # 每个规则的详细解释
                "confidence": 0.0-1.0,  # 决策置信度
                "requires_human_review": bool,  # 是否需要人工审核
            }
        """
        triggered = self.evaluate(metrics, min_spend, min_impressions)

        if not triggered:
            return {
                "decision": ActionType.HOLD,
                "triggered_rules": [],
                "explanations": ["所有指标正常，无需操作"],
                "confidence": 0.9,
                "requires_human_review": False,
            }

        # 如果第一个是 DATA_BLOCKED
        if triggered[0].rule_id == "DATA_BLOCKED":
            return {
                "decision": ActionType.DATA_BLOCKED,
                "triggered_rules": ["DATA_BLOCKED"],
                "explanations": ["数据不足，无法做出决策"],
                "confidence": 0.3,
                "requires_human_review": True,
            }

        # 取最高优先级规则
        top_rule = triggered[0]
        explanations = [
            f"[{r.rule_id}] {r.description} → {r.reason} (置信度: {r.severity.value})"
            for r in triggered[:3]  # 最多3条
        ]

        # 素材老化加权：素材投放超过7天，更倾向于换素材
        if creative_age_days > 7 and top_rule.action != ActionType.CHANGE_CREATIVE:
            explanations.append(
                f"[CREATIVE_AGE] 素材已投放{creative_age_days}天，建议考虑换素材"
            )

        return {
            "decision": top_rule.action,
            "triggered_rules": [r.rule_id for r in triggered],
            "explanations": explanations,
            "confidence": 0.9 if top_rule.severity == Severity.CRITICAL else 0.7,
            "requires_human_review": top_rule.severity == Severity.CRITICAL,
        }

    def _create_data_blocked_rule(self, spend: float, impressions: int) -> KpiRule:
        return KpiRule(
            rule_id="DATA_BLOCKED",
            description=f"数据不足：花费=${spend}，展示={impressions}",
            condition=KpiMetric.SPEND,
            threshold_operator="<",
            threshold_value=0,
            threshold_unit="$",
            action=ActionType.DATA_BLOCKED,
            severity=Severity.INFO,
            priority=99,
            reason="花费或展示量不足，决策置信度低，建议继续观察",
            anti_action=ActionType.PAUSE,
            anti_reason="数据不足时暂停会让数据更少，无法判断。",
        )

    # ------------------------------------------------------------------
    # 规则查询方法
    # ------------------------------------------------------------------

    def get_rules_by_metric(self, metric: KpiMetric) -> List[KpiRule]:
        """获取某个指标的所有规则"""
        return [r for r in self._rules if r.condition == metric]

    def get_rules_by_action(self, action: ActionType) -> List[KpiRule]:
        """获取推荐某个动作的所有规则"""
        return [r for r in self._rules if r.action == action]

    def get_critical_rules(self) -> List[KpiRule]:
        """获取所有严重规则"""
        return [r for r in self._rules if r.severity == Severity.CRITICAL]

    def export_rules(self) -> List[Dict]:
        """导出所有规则为可读格式"""
        return [
            {
                "rule_id": r.rule_id,
                "description": r.description,
                "condition": r.condition.value,
                "threshold": f"{r.threshold_operator} {r.threshold_value}{r.threshold_unit}",
                "action": r.action.value,
                "severity": r.severity.value,
                "priority": r.priority,
                "reason": r.reason,
                "anti_action": r.anti_action.value,
                "anti_reason": r.anti_reason,
            }
            for r in self._rules
        ]