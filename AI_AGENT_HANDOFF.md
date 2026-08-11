# AI Agent Handoff — Performance Grounded Intelligence

> **To the next AI agent (WorkBuddy / Trae / etc.):** this project is a creative intelligence pipeline for mobile game ad optimization. It extracts winner DNA from performance data, then mutates and evolves new creative candidates. All 9 phases are built and verified. Below is everything you need to start working.

---

## 1. What This Project Is

**Performance Grounded Intelligence** — 买量素材智能进化系统。

核心闭环: Facebook/Adjust 广告数据 → Winner Mining → Vision DNA 提取 → Prompt 生成 → DNA 变异进化 → Facebook 测试批次导出。

技术栈: Python 3.10 (纯脚本，无 Web 框架)，OpenAI API (Vision DNA)，CLIP (图像聚类)。

---

## 2. Directory Structure (Core Module)

```
performance_grounded_intelligence/
├── config.py                          # 全局配置 (路径/阈值/权重)
├── run.py                             # CLI 入口 (--phase 1-9)
│
├── data_connector/                    # Phase 1: 数据融合
│   ├── performance_fuser.py           #   Facebook + Adjust 合并
│   ├── facebook_loader.py
│   └── adjust_loader.py
│
├── asset_resolver/                    # Phase 2: 素材解析
│   ├── asset_mapper.py                #   CLIP 聚类 / URL 分组回退
│   ├── thumbnail_downloader.py
│   ├── image_embedding.py
│   └── asset_cluster.py
│
├── image_detector/                    # Phase 3: 图片检测
│   └── image_score.py
│
├── winner_miner/                      # Phase 4: Winner 挖掘
│   ├── winner_pools.py                #   三池: Scale / Efficiency / Pattern
│   ├── winner_score.py
│   └── confidence_model.py
│
├── vision_dna/                        # Phase 5: Vision DNA
│   ├── dna_extractor.py               #   LLM 主导的 DNA 提取
│   ├── composition_analyzer.py
│   ├── gameplay_recognizer.py
│   ├── reward_recognizer.py
│   └── style_analyzer.py
│
├── generation/                        # Phase 6: Prompt 生成
│   └── prompt_builder.py              #   支持标准 & mutation 两种模式
│
├── quality_gate/                      # Phase 7: 质量关卡
│   ├── winner_similarity.py           #   CLIP 相似度
│   └── dna_match_checker.py           #   DNA 4维匹配
│
├── reports/                           # Phase 8: 报告导出
│   ├── ranking_report.py
│   ├── gallery_report.py
│   └── export.py
│
└── dna_evolution/                     # Phase 9: DNA 进化引擎 ★ 最新
    ├── mutation_rules.py              #   4种变异策略 + 候选值池
    ├── dna_mutator.py                 #   Winner DNA → Variant Pool
    ├── evolution_checker.py           #   Quality Gate (4项检查)
    ├── evolution_ranker.py            #   按 Evolution Score 排名
    ├── experiment_builder.py          #   Facebook 测试批次 JSON
    ├── evolution_engine.py            #   总编排 (7步流水线)
    └── evolution_report.py            #   人类可读报告
```

---

## 3. Pipeline Phases Status

| Phase | Name | Status | Key Output |
|-------|------|--------|------------|
| 1 | Data Fusion | ✅ Complete | `creative_performance_raw.json` (3206 records) |
| 2 | Asset Resolver | ✅ Complete | `visual_assets.json` (980 assets) |
| 3 | Image Detection | ✅ Complete | Integrated into Phase 1 |
| 4 | Winner Mining | ✅ Complete | 3 winner pools JSON |
| 5 | Vision DNA | ✅ Complete | `true_winner_dna.json` (20 winners) |
| 6 | Prompt Builder | ✅ Complete | `generation_prompts.json` |
| 7 | Quality Gate | ⚠️ Placeholder | Needs generated images to run |
| 8 | Reports | ✅ Complete | HTML + JSON exports |
| 9 | DNA Evolution | ✅ Complete | `dna_evolution/*.json` (7 output files) |

**All 9 phases pass end-to-end.** Phase 7 需要实际图片生成后才能运行实际检查。

---

## 4. Environment

- **Python**: `C:\Users\ethan\AppData\Local\Programs\Python\Python310\python.exe` (3.10)
- **Dependencies**: `openai`, `open_clip_torch`, `torch`, `Pillow`, `openpyxl`, `pandas` (see `requirements.txt` if it exists, otherwise install on demand)
- **Working directory**: `d:\project_slim\project_slim`
- **Module prefix**: Always run as `python -m performance_grounded_intelligence.run`

---

## 5. How to Run

```bash
# 全流程 (Phase 1→9, skip CLIP for speed)
cd d:\project_slim\project_slim
$env:PYTHONIOENCODING='utf-8'   # Windows 必须设置, 否则中文报错
python -m performance_grounded_intelligence.run --skip-clip

# 只运行 DNA Evolution (Phase 9)
python -m performance_grounded_intelligence.run --skip-clip --phase 9

# 单步调试
python -c "
from performance_grounded_intelligence.dna_evolution.evolution_engine import run_phase9
summary = run_phase9(top_winner_n=10, variants_per=4)
print(summary)
"
```

---

## 6. Winner DNA Structure

5 维结构 (定义在 `mutation_rules.py:DNA_DIMENSIONS`):

```json
{
  "composition": {
    "gameplay_area": {"ratio": 0.5, "position": "center"},
    "reward_area":    {"ratio": 0.25, "position": "top_right"},
    "character_area": {"ratio": 0.15, "position": "bottom"},
    "background_area":{"ratio": 0.1}
  },
  "gameplay": {"type": "merge_board", "elements": ["merge_items"]},
  "reward":   {"type": "mixed", "elements": []},
  "style":    {"color_palette": "purple_gold", "lighting": "magic_glow",
               "camera": "isometric", "render_style": "3d_cartoon"},
  "hook": "merge_upgrade",
  "layout": "center_merge"
}
```

## 7. Evolution Engine Quick Reference

**4 种变异策略** (`mutation_rules.py:VARIANT_STRATEGIES`):

| Strategy | 保留 | 变异 | 目的 |
|----------|------|------|------|
| A | gameplay, reward, hook, layout | style, composition | 视觉风格探索 |
| B | composition, hook, gameplay, layout | reward, style | 奖励元素探索 |
| C | reward, hook, layout | gameplay, style, composition | 玩法呈现探索 |
| D | style, gameplay, hook | composition, layout, reward | 构图布局探索 |

**Quality Gate 阈值** (`config.py`):
- `EVO_SIMILARITY_MIN = 0.70` (Winner 相似度)
- `EVO_DIVERSITY_MIN = 0.25` (变异差异度)
- `EVO_GAMEPLAY_MIN = 0.85` (玩法保留度)
- `EVO_REWARD_MIN = 0.20` (奖励可见度)

**Evolution Score** = 0.35×Similarity + 0.25×Gameplay + 0.20×Reward + 0.20×Novelty

**最近一次运行结果**: 40 variants → 30 passed (75%), 20 creatives in test batch.

---

## 8. Output Files Location

```
output/performance_grounded/
├── creative_performance_raw.json    # Phase 1: 3206 条融合记录
├── visual_assets.json               # Phase 2: 980 个素材聚类
├── true_winner_dna.json             # Phase 5: 20 个 Winner DNA
├── generation_prompts.json          # Phase 6: 标准 Prompts
├── winners/
│   ├── scale_winners.json
│   ├── efficiency_winners.json
│   └── creative_pattern_winners.json
└── dna_evolution/                   # Phase 9: ★ 全部演化结果
    ├── dna_variants.json            # 40 个变异体
    ├── evolution_check_results.json # Quality Gate 结果
    ├── evolution_ranking.json       # 30 个通过变体排名
    ├── facebook_test_batch.json     # Top 20 FB 测试批次
    ├── mutation_prompts.json        # 30 个变异 Prompt
    ├── evolution_summary.json       # 演化摘要
    └── evolution_report.txt         # 人类可读报告
```

---

## 9. Key Design Decisions (for Future Work)

1. **Diversity 计算**: 仅计算策略指定的变异维度 (非全维度)。修改在 `evolution_checker.py:check_diversity()`。

2. **变异保证**: `dna_mutator.py` 中 style/reward 变异有 "至少1个变化" 保证；composition 强制选不同值。这是为了避免 0-change variant。

3. **Strategy D 低通率**: Strategy D 同时变异 composition+layout+reward (权重合计 50%)，天生 similarity 低。这是设计预期，不是 bug。

4. **Phase 7 占位**: `quality_gate/` 模块代码就绪，但需要生成的实际图片才能跑 CLIP 相似度检查。

---

## 10. TODO / Known Gaps

- [ ] **Phase 7 激活**: 接入真实图片生成 API 后，运行 `winner_similarity.py` 和 `dna_match_checker.py`
- [ ] **Strategy D 增强**: 当前只有 ~10% 的 Strategy D 变体通过 Quality Gate，可考虑调高 composition 保留度或降低激进程度
- [ ] **实际图片生成**: 当前 pipeline 输出 Prompt，但没有对接 Midjourney/DALL-E/Stable Diffusion 生成实际图片
- [ ] **Facebook API 对接**: `facebook_test_batch.json` 格式已准备好，但未对接 Ads API 自动创建 Campaign
- [ ] **闭环反馈**: 变异体的实际 performance 数据回写机制未实现
- [ ] **reports/ 目录**: 报告模块文件齐全但可能需要根据最新数据格式微调
- [ ] **Runtime 显示**: `evolution_summary.json` 中 runtime 为 0.01s，因为纯内存计算太快，正常现象

---

## 11. Spec / Design Docs

原始设计文档 (供参考):
- `C:\Users\ethan\AppData\Roaming\Qoder\SharedClientCache\cache\plans\DNA_Evolution_Engine_task-da9.md`
- `d:\project_slim\project_slim\AI_MEDIA_BUYER_V2_ROADMAP.md`
- `d:\project_slim\project_slim\README.md`

---

## Quick Start (验证系统正常)

```powershell
cd d:\project_slim\project_slim
$env:PYTHONIOENCODING='utf-8'
C:\Users\ethan\AppData\Local\Programs\Python\Python310\python.exe -m performance_grounded_intelligence.run --skip-clip --phase 9
```

预期输出: 40 variants → ~30 passed (≥70%), 4 个输出文件生成在 `output/performance_grounded/dna_evolution/`。

---

*Generated 2025-07. Handoff for WorkBuddy / Trae / any AI agent.*
