# 执行每日报告（Execution Daily Report · 2026-07-30）

- 执行 **12** ｜ 成功 **9** ｜ 失败 **1** ｜ 回滚 **1** ｜ 拦截 **1**
- 健康等级：**YELLOW**

## Provider 分布

| Provider | 执行数 |
|---|---|
| max | 8 |
| meta | 3 |
| unknown | 1 |

## Warnings

- ⚠️ [WARNING] ROLLBACK_RATE_HIGH: 回滚率 8.3% 超过阈值 5%
- ⚠️ [WARNING] ACTION_LOOP: 动作 update_waterfall 对 merge_witch 在 2026-07-30 重复 6 次（> 3）
- ⚠️ [ALERT] EXECUTION_DRIFT: 执行漂移：请求 update_waterfall ≠ 实际 pause_campaign（execution_id=exe_d7b6d4a12eb9）
- ⚠️ [ALERT] EXECUTION_DRIFT: 执行漂移：请求 update_waterfall ≠ 实际 pause_campaign（execution_id=exe_719c12485151）
- ⚠️ [ALERT] EXECUTION_DRIFT: 执行漂移：请求 update_waterfall ≠ 实际 pause_campaign（execution_id=exe_ca9bf49e1b86）

## Learning（回流记忆）

- 🧠 动作 update_waterfall：真实执行成功率 75%（n=8）
- 🧠 动作 pause_campaign：真实执行成功率 100%（n=3）
