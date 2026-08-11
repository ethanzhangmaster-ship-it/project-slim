# E15.1.1 — Autonomous Publishing Factory · 状态报告

_冻结日期：2026-07-24 · 全部绿灯_

## 一句话

把 E15.1 的**单游戏上架编排器**升级成**批量游戏工厂**：一个人管 10–50 款海外休闲游戏时，系统自动完成「发现该干什么 → 生成素材/文案 → 合规扫描 → 决策分级 → 生成上架计划」，物理落子仍由人执行。**结果驱动、确定性规则、不接 LLM、绝不调真实商店 API。**

## 验收结果

| 门 | 结果 |
|---|---|
| E15.1.1 pytest (`tests/e15_1_1/`) | **120 passed** (6.6s) |
| E15.1.1 验收门 (`operation/validate_e15_1_1.py`) | **128 / 0 — AUTONOMOUS PUBLISHING READY** |
| E15.1 回归门 (`operation/publishing/validate_publishing.py`) | **56 / 0 — 无回归** |

pytest 分布：Fleet 22 · Asset 20 · ASO/Localization 20 · Compliance 15 · Batch 20 · Memory 10 · Integration 15 = **120**

## 架构（`operation/publishing_factory/`，21 个源文件）

```
catalog/           产品目录 + 舰队调度
  product_profile.py    GameProduct + 状态/平台/品类/变现枚举
  game_registry.py      JSON 数组持久化的游戏注册表
  fleet_manager.py      scan() → 优先级任务队列（RESUBMIT>VERSION>METADATA/COMPLIANCE>ASO）
asset_pipeline/    素材生产线（输出结构化创意 brief，非像素）
  screenshot_generator.py  5 张：hook→proof→fantasy 序列 + 品类配色
  icon_generator.py        图标规格
  video_generator.py       ≤30s 分镜脚本
  asset_validator.py       尺寸/字数/数量规则校验
metadata_engine/   ASO + 本地化
  aso_generator.py         标题/副标/关键词包（品类词库）
  localization_engine.py   en/de/fr/ja/ko 词表本地化
  keyword_optimizer.py     100 字预算贪心打包 + 去重
compliance/        商店合规
  policy_scanner.py        Jaccard 相似度查 Apple 4.3 灌水
  privacy_checker.py       隐私政策/COPPA/年龄门/同意
  store_risk_predictor.py  Apple/Google 双概率 + 风险等级
publishing_factory.py      单游戏计划编排 + 三级审批门
batch_orchestrator.py      run_daily() 批量 + handle_rejection() 拒审修复环
memory.py                  JSONL：素材风格/关键词/拒审修复的有效性学习
```

## 七大能力（对齐用户 spec）

1. **Fleet Manager** — 注册表→按优先级排的每日任务队列，10–50 款一屏可管。
2. **自动 ASO** — 品类词库确定性生成标题/副标/关键词，按 100 字预算打包。
3. **截图工厂** — 5 张 hook→proof→fantasy 结构化创意 brief（供人/外部工具产出像素）。
4. **商店合规 Agent** — Jaccard 跨舰队查 Apple 4.3 灌水 + 隐私清单 + 双商店风险预测。
5. **批量发布编排** — 一次跑全舰队，产出每款的计划 + 决策等级。
6. **拒审反馈环** — 拒审原因→确定性修复计划（4.3→差异化创意 / 隐私→政策+年龄门 / 元数据→重写）。
7. **自主决策分级** — 三级沙箱门 SIMULATION→SHADOW→PRODUCTION，`real_api_called=False` 锁死；仅 E15.1 `PublishingAgent` 在 `unlock()`+人工审批后触达 PRODUCTION。

## 复用与边界

- **复用 E15.1**：直接 import `operation.publishing.orchestrator.agent.PublishingAgent`，工厂只做「发现+生成+决策」，真正上架仍走 E15.1 管线。
- **诚实的「还没做」**（与 E15.1 一致，均为物理层，需人执行）：
  - 真实商店 API（App Store Connect / Google Play）调用 = 0，未接凭证。
  - 无真实构建管线（`src/build.py` 仍是 Fastlane dry-run）。
  - 素材为结构化 brief，非渲染像素/视频。
  - 上架物理落子、拒审后重提交由人在后台完成。

## 下一步（未启动，待用户指令）

- Phase-8：与 Growth OS / Revenue OS 联动（上架后自动接管变现自动驾驶）。
- 接真实 App Store Connect / Google Play API + 凭证（解除唯一「物理落子靠人」约束）。
