# FinalBandit 上线 Checklist

## 前置条件

- [ ] 有网络环境可访问 `graph.facebook.com`
- [ ] `.env` 中 `META_ACCESS_TOKEN` 有效（当前已配置但需验证过期时间）
- [ ] `.env` 中 `META_AD_ACCOUNT_ID` 已配置（当前缺失，需补充）
- [ ] Lovart API 凭证有效（`LOVART_ACCESS_KEY` + `LOVART_SECRET_KEY`）
- [ ] DuckDB 数据库可读写

---

## Phase 1: 拉取最新数据

```bash
# 拉取最近 30 天 Facebook 数据
python3 scripts/fetch_facebook_data.py

# 如果 Facebook API 不可用，导入本地数据
python3 scripts/import_creative_library.py
python3 scripts/build_feature_variants.py
```

**验证**:
- [ ] `creative_performance` 表有新日期数据
- [ ] 至少 2 个不同日期

---

## Phase 2: 运行 Pipeline

```bash
# P04 专属 (当前重点)
python3 scripts/run_pipeline.py --project P04 --days 7

# 输出文件:
#   output/pipeline_strategy.md   → 投放策略报告
#   output/pipeline_prompts.md    → AI 裂变 prompt
#   output/monitor/current_state.json → Dashboard 数据
```

**验证**:
- [ ] Winner 识别率 ≥ 50%
- [ ] 策略报告中有明确的 "多投/少投" 建议
- [ ] `output/pipeline_prompts.md` 包含 5 个 prompt

---

## Phase 3: AI 生成图片

```bash
# 用 Lovart 生成图片 (需要配置)
python3 scripts/gen_p04_round1.py
```

**验证**:
- [ ] 生成 10-15 张图片
- [ ] 图片符合 winner 特征 (warm 色调 + left_right 布局)

---

## Phase 4: 人工审核

- [ ] 剔除有明显问题的图片（模糊、文字错误、品牌不符）
- [ ] 确认图片与 prompt 描述一致
- [ ] 最终保留 5-10 张

---

## Phase 5: 上传 Facebook 投放

```python
# 在 Python 中执行:
from market_ops.creative_intelligence.experiment_engine import ExperimentEngine

engine = ExperimentEngine()

# 生成实验 (FinalBandit 自动选 variant)
exps = engine.generate_experiments(project="P04", count=3)

# 发布
result = engine.publish_experiments(
    experiments=exps,
    adset_id="<YOUR_ADSET_ID>",      # 需替换
    image_dir_map={"exp_xxx": "/path/to/images"},  # 需替换
)
```

**验证**:
- [ ] Facebook Ads Manager 中可见新 campaign
- [ ] 状态为 "In Review" 或 "Active"
- [ ] 每日 budget $20-50

---

## Phase 6: 每日 Cron

```bash
# 每天运行一次 (建议凌晨 2:00)
0 2 * * * cd /path/to/project && python3 scripts/run_pipeline.py --project P04 --days 7

# 或手动:
python3 scripts/run_pipeline.py --project P04 --days 7
```

**验证**:
- [ ] Monitor Dashboard 显示每日更新的 theta/sigma
- [ ] entropy 不崩塌
- [ ] 去重计数正常（duplicate_reject 不异常增长）

---

## Phase 7: 7 天后评估

```bash
# 查看 Monitor Dashboard
cd output/monitor && python3 -m http.server 8080
# 浏览器打开 http://localhost:8080/dashboard.html
```

**判定标准**:

| 指标 | PASS 条件 |
|------|-----------|
| theta 排序 | 与真实 ROAS 排序一致 |
| sigma 下降 | decline_ratio < 0.9 |
| entropy | 不崩塌 (> early × 0.3) |
| flip_rate | < 0.3 |
| 去重 | duplicate_reject 稳定 |

**如果全部 PASS** → 扩大维度，加入更多 gene_type
**如果有 FAIL** → 检查数据质量，考虑调参

---

## 环境变量检查清单

```bash
# 必需
META_ACCESS_TOKEN=        # Facebook API token
META_AD_ACCOUNT_ID=       # 广告账户 ID (当前缺失!)
META_API_VERSION=v19.0

# Lovart (图片生成)
LOVART_ACCESS_KEY=
LOVART_SECRET_KEY=
LOVART_BASE_URL=https://lgw.lovart.ai

# 可选
DEFAULT_GAME_NAME=P04 Witch
```

---

## 快速验证命令

```bash
# 一键检查所有模块是否正常
python3 scripts/test_experiment_engine.py   # Engine 集成测试
python3 scripts/final_self_check.py         # FinalBandit 8 维度自检
python3 scripts/verify_iap_observation.py   # IAP Observation 8 问
python3 scripts/verify_monitor.py           # Monitor 7 问
python3 scripts/run_pipeline.py --project P04 --days 7  # 完整 Pipeline
```

---

## 风险提示

| 风险 | 缓解 |
|------|------|
| Token 过期 | 提前 7 天检查 token 有效期 |
| API rate limit | 每天只跑 1 次 backfill |
| Budget 超支 | campaign 设 daily budget cap |
| 图片审核不通过 | 人工预审 + 避免敏感内容 |
| 数据延迟回流 | rolling 7 天窗口覆盖 T+7 |
