## 🧪 A/B Experiments (lifecycle: PROPOSED → APPLIED → OBSERVED → WINNER/ROLLBACK → MEMORIZED)

_Every opportunity is a formal A/B test: **A** = current state, **B** = proposed change. The expected metric is **Revenue/DAU**; the hypothesized lift is confirmed by post-apply diff-in-diff, never assumed._

**🧪 [ACTIVE] increase_bid_opportunity → MINTEGRAL_BIDDING**
   - 🎯 Expected: **revenue_per_dau lift +2.4%** (hypothesized, A/B-verified)
   - A (control): 现状(A)：MINTEGRAL_BIDDING 仅捕获其 eCPM 潜力 19% （208 曝光 @ eCPM $82.21，收入占比 5.8%）
   - B (variant): 变体(B)：提升 bidding 曝光优先级，目标捕获潜力 → ~59%，预期收入占比 → ~8.2%
   - Hypothesis: Raising auction exposure captures the network's eCPM-implied potential; the hidden_winner signal should clear without ARPDAU regression.
   - watching (0/3d min); signal still firing; user guardrail pending · ARPDAU guardrail: pending

**🧪 [ACTIVE] adjust_bid_constraint → APPLOVIN_EXCHANGE**
   - 🎯 Expected: **revenue_per_dau lift +6.6%** (hypothesized, A/B-verified)
   - A (control): 现状(A)：APPLOVIN_EXCHANGE 占 13.5% 曝光 @ 寄生 eCPM $1.41 （< 账户 blend 5718%），低价值回填
   - B (variant): 变体(B)：设 price floor $4.57–$8.58 过滤低价值填充
   - Hypothesis: Lifting the bid constraint cuts lowest-value backfill; the bid_floor signal should clear with fill-rate guarded.
   - watching (0/3d min); signal still firing; user guardrail pending · ARPDAU guardrail: pending

**🧪 [ACTIVE] disable_network → CHARTBOOST**
   - 🎯 Expected: **revenue_per_dau lift +1.7%** (hypothesized, A/B-verified)
   - A (control): 现状(A)：CHARTBOOST 消耗 17,300 请求仅产生 $0.11（僵尸）
   - B (variant): 变体(B)：禁用 → 释放瀑布槽位，请求重新分配到高 eCPM 网络（保守估计 0.5% 重分配转化为收入）
   - Hypothesis: Removing the zombie frees waterfall slots for higher-eCPM networks; the zombie_network signal clears (network exits the report).
   - watching (0/3d min); signal still firing; user guardrail pending · ARPDAU guardrail: pending

**🧪 [ACTIVE] disable_network → INMOBI**
   - 🎯 Expected: **revenue_per_dau lift +0.2%** (hypothesized, A/B-verified)
   - A (control): 现状(A)：INMOBI 消耗 1,608 请求仅产生 $0.00（僵尸）
   - B (variant): 变体(B)：禁用 → 释放瀑布槽位，请求重新分配到高 eCPM 网络（保守估计 0.5% 重分配转化为收入）
   - Hypothesis: Removing the zombie frees waterfall slots for higher-eCPM networks; the zombie_network signal clears (network exits the report).
   - watching (0/3d min); signal still firing; user guardrail pending · ARPDAU guardrail: pending

**🧪 [ACTIVE] diversify → application:Merge Monster**
   - 🎯 Expected: **revenue_per_dau lift +0.0%** (hypothesized, A/B-verified) · 🛡️ risk-hedge
   - A (control): 现状(A)：收入单点集中（application:Merge Monster），单一网络失效风险
   - B (variant): 变体(B)：引入候选网络分散收入来源，降低单点失效风险（不直接提升收入，属风险对冲）
   - Hypothesis: Introducing a candidate network reduces single-point revenue risk; this is a guardrail hedge, not a direct Revenue/DAU lift.
   - risk-hedge experiment (no revenue signal to clear): user guardrail pending — keep watching, archive when hedge goal met · ARPDAU guardrail: pending

_Apply in MAX dashboard, then anchor with: `python operation/optimizer/experiments/cli.py apply <ACCT> <exp_id>` — impact is measured automatically on the next daily run._

