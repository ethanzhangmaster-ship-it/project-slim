"""E17.2 记忆测试（Test6）：历史成功 → 相似机会 confidence 提升。"""
from src.ceo_intelligence.opportunity_engine.memory import (
    OpportunityMemory,
    OpportunityMemoryRecord,
)
from src.ceo_intelligence.opportunity_engine.models import GameSignals
from src.ceo_intelligence.opportunity_engine.rules import evaluate
from src.ceo_intelligence.opportunity_engine.models import OpportunityType


def _creative_opp():
    sig = GameSignals(ctr_growth=-0.25, frequency_growth=0.5, fatigue_score=0.5)
    return evaluate(sig, game_id="merge_witch", segment="US")[0]


def test_boost_zero_with_insufficient_samples(tmp_path):
    mem = OpportunityMemory(path=str(tmp_path / "om.jsonl"))
    assert mem.confidence_boost(OpportunityType.CREATIVE_REFRESH.value, "US") == 0.0
    mem.add(OpportunityMemoryRecord("g", "creative_refresh", "US", "gen_creative", 0.18))
    # 仅 1 样本 → 仍 0
    assert mem.confidence_boost("creative_refresh", "US") == 0.0


def test_confidence_boost_on_historical_success(tmp_path):
    mem = OpportunityMemory(path=str(tmp_path / "om.jsonl"))
    # 3 条成功历史（Merge/US/Creative Refresh 平均 +18%）
    for imp in (0.18, 0.20, 0.15):
        mem.add(OpportunityMemoryRecord("merge_x", "creative_refresh", "US", "gen_creative", imp))

    base = _creative_opp()  # 无记忆基线
    assert base.confidence == _creative_opp().confidence  # 确定性
    boosted = _creative_opp()
    mem.apply_boost(boosted, segment="US")
    assert boosted.confidence > base.confidence
    # 成功率 1.0 → 加成 = min(0.20, 1.0*0.15) = 0.15
    assert abs(boosted.confidence - min(0.99, base.confidence + 0.15)) < 1e-9
