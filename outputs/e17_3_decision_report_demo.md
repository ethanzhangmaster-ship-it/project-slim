# 增长决策报告（Growth Decision Engine · CEO Brain）

- 决策总数：**3**
- 出口分布：自动执行 1 / 待审批 1 / 仅观察 1 / 拒绝 0
- 组合预期收益提升：**+50.0%**

## CEO 优先级清单（Top）

1. **puzzle_island** — 优化商店页（puzzle_island）  | 预期 +30.0% | 置信 70% | 出口 observe
2. **merge_witch** — 恢复收入（merge_witch）  | 预期 +30.0% | 置信 90% | 出口 approve
3. **merge_witch** — 刷新创意素材（merge_witch）  | 预期 +20.0% | 置信 95% | 出口 execute

---

> 场景：3 款游戏。merge_witch 历史 creative_refresh 成功 3 次 → 本次 CREATIVE_REFRESH 置信度获记忆加成；其 REVENUE_RECOVERY 因风险中等(0.45)→ 进入人工审批队列。
> 复用：EP0 AuditTrail（每条决策不可变落盘）、E16.1.1 JsonlApprovalQueue（人工审批信箱）、E16.1 JsonlRevenueExperienceStore（Decision Memory 闭环）。
> 三道门：Gate1 置信<0.8→OBSERVE / Gate2 高风险→APPROVE / Gate3 执行权限(RELEASE可自动·PAYMENT必人工)。
