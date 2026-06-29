# AI 创意闭环系统 — zcode 智谱 交接文档

> **交付日期**: 2026-06-18  
> **当前状态**: 核心闭环跑通，Lovart 出图+自评双模型可用，Meta Ads API 待接入

---

## 一、系统概述

这是一个 **Facebook 图片素材 AI 自动生成闭环系统**。核心思路：

```
创意CSV数据 → DNA分析(找赢家模式) → PromptForge(生成提示词)  
→ Lovart出图 → Lovart自评(质量门控) → 低分淘汰/重新生成 → 入库CSV → 飞书报告
```

**价值**：无需设计师、无需 OpenAI Key（全部基于 Lovart），AI 自动分析在投素材的赢家模式 → 出图 → 评分 → 入库，形成 7×24 自动出图链路。

### 三个目标项目（merge-2 手游）

| 项目 | 主题 | 主色调 |
|------|------|--------|
| P04 Witch | 女巫魔法 | 暗紫/霓虹绿/魔法金 |
| P02 Mermaid | 美人鱼海洋 | 海蓝/珊瑚粉/珍珠白 |
| P07 Vampire | 吸血鬼哥特 | 血红/午夜黑/月光银 |

---

## 二、架构总览

```
                    ┌─────────────────────────────┐
                    │   creative_closed_loop.py    │
                    │      (Orchestrator)          │
                    └──────┬──────────┬───────────┘
                           │          │
              ┌────────────▼──┐  ┌────▼──────────────┐
              │  creative_dna │  │ creative_prompt_   │
              │  (Stage 1-2)  │  │ forge (Stage 3)    │
              │  赢家模式分析 │  │ 生成出图提示词     │
              └───────────────┘  └────────────────────┘
                                          │
              ┌───────────────────────────▼────────────┐
              │         creative_image_gen             │
              │         (Stage 4: 出图)                │
              │  Lovart > DALL-E > Mock (优先级)       │
              └──────────────────┬─────────────────────┘
                                 │
              ┌──────────────────▼──────────────────────┐
              │      creative_image_scorer              │
              │      (Stage 4.5: 质量门控)              │
              │  Lovart自评 > OpenAI Vision > Mock      │
              └──────────────────┬──────────────────────┘
                                 │
                        低分 → 重新生成
                        通过 → 入库CSV
                                 │
                    ┌────────────▼───────────┐
                    │  飞书卡片报告 (可选)   │
                    └────────────────────────┘
```

### 核心模块文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `src/market_ops/creative_closed_loop.py` | 641 | **主编排器**，串联所有Stage，CLI入口 |
| `src/market_ops/creative_dna.py` | 506 | 创意DNA分析，从CSV提取赢家模式 |
| `src/market_ops/creative_prompt_forge.py` | 364 | 提示词生成器，包含项目视觉映射表+6种hook模板 |
| `src/market_ops/creative_image_gen.py` | 544 | 出图引擎，Lovart/DALL-E/Mock三后端 |
| `src/market_ops/creative_image_scorer.py` | 571 | 出图质量评分，5维度加权，Lovart自评优先 |
| `src/market_ops/clients/lovart.py` | ~502 | Lovart API客户端（出图+上传+评价） |
| `src/market_ops/models.py` | - | CreativeAssetRow 数据模型 |

---

## 三、数据流

### 输入
```
output/normalized/creative_library.csv
```
字段：`asset_id, creative_type, video_path, game, country, channel, ctr, cvr, roas, spend, status, hook_type, creative_name, campaign, adgroup, ad_id, ad_name, source_name, installs, conversions, revenue_value`

### 输出
```
output/creative_loop/
├── images/lovart_YYYYMMDD_HHMMSS/    # 生成的图片
│   ├── lovart_*.png
│   └── manifest.json                  # 图片元数据
├── prompts/prompt_batch_*.json        # 提示词清单
├── library_update_cycle_*.csv         # 可追加到创意库的CSV
└── scores_cycle_*_r0.json             # 评分报告
```

### 5 个 Stage

| Stage | 名称 | 说明 |
|-------|------|------|
| 1 | Load | 加载CSV，过滤出图片类型，按项目过滤 |
| 2 | DNA | 按 hook_type × emotion 聚合，计算 ROI/CTR/CVR 得分 |
| 3 | PromptForge | 选 top patterns 生成出图提示词 |
| 4 | ImageGen | Lovart 出图（nano banana + gpt-image-2） |
| 4.5 | Score | Lovart 自评 → 低分淘汰 → 改进 prompt 重新生成(最多N轮) |
| 5 | Library | 生成入库CSV |

---

## 四、Lovart API 集成

### 配置（.env）

```env
LOVART_ACCESS_KEY=ak_4ab8ecb8e3fb486b3cf450c2a2747ba5
LOVART_SECRET_KEY=sk_d09d1ea5cb072ab213b194f3b3356cd7a384df21c99f1c01d49b22e452da1da6
LOVART_BASE_URL=https://lgw.lovart.ai
LOVART_MODELS=generate_image_nano_banana,generate_image_gpt_image_2
LOVART_MODE=fast
```

### 两个模型

| 模型 | API标识 | 费用 |
|------|---------|------|
| Nano Banana | `generate_image_nano_banana` | 免费 |
| GPT Image 2 | `generate_image_gpt_image_2` | 14 credits/张(需auto-confirm) |

### LovartClient 核心API

| 方法 | 功能 |
|------|------|
| `ensure_project()` | 创建/复用Lovart项目 |
| `generate_image(prompt)` | 提交出图 → auto-confirm → poll → 返回结果 |
| `generate_image_all_models(prompt)` | 同一prompt用所有配置模型出图 |
| `upload_file(path)` | 上传图片到Lovart CDN（用于自评） |
| `evaluate_image(path, prompt, project)` | 上传图片 + 评分prompt → 返回JSON分数 |
| `download_image(url, dest)` | 下载图片（SSL fallback） |

### 5维度评分权重

```python
WEIGHTS = {
    "visual_quality":    0.25,  # 视觉质量
    "brand_alignment":   0.25,  # 品牌一致性
    "hook_clarity":      0.20,  # Hook清晰度
    "ad_suitability":    0.20,  # 广告适用性
    "originality":       0.10,  # 原创性
}
```

### 评分后端优先级

```
Lovart自评(默认) → OpenAI Vision(gpt-4o) → Mock启发式
```

目前 Lovart 自评已实测可用，评分反馈质量高，无需 OpenAI Key。

---

## 五、CLI 使用

```bash
# 单项目运行
python -m market_ops.creative_closed_loop \
    --game "P04 Witch" \
    --max-prompts 6 \
    --score-threshold 6.0 \
    --max-regen 2 \
    --output-dir output/creative_loop

# 多项目批量
python -m market_ops.creative_closed_loop \
    --multi "P04 Witch" "P02 Mermaid" "P07 Vampire" \
    --max-prompts 4

# 禁用Lovart（回退DALL-E/mock）
python -m market_ops.creative_closed_loop --game "P04 Witch" --no-lovart

# Dry-run（跳过出图，仅测试前面阶段）
python -m market_ops.creative_closed_loop --game "P04 Witch" --dry-run
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--game` | P04 Witch | 目标项目 |
| `--max-prompts` | 6 | 每轮生成提示词数量 |
| `--score-threshold` | 6.0 | 评分通过阈值(1-10) |
| `--max-regen` | 2 | 低分图片最大重新生成轮次 |
| `--lovart`/`--no-lovart` | True | Lovart开关 |
| `--multi` | - | 多项目批量运行 |
| `--dry-run` | - | 跳过实际出图 |

---

## 六、当前状态

### ✅ 已完成（核心闭环完整跑通）

- [x] **Lovart 出图** — 双模型(nano banana + gpt-image-2)，HMAC签名认证，auto-confirm付费操作，SSL容错
- [x] **Lovart 自评** — 上传图片到CDN → AI评分 → 解析JSON分数，实测6.85/10，反馈精准
- [x] **质量门控** — 低分淘汰 → 改进prompt → 重新生成 → 最多N轮
- [x] **全流程编排** — CreativeDNA(赢家模式分析) → PromptForge(提示词) → ImageGen(出图) → Scorer(评分) → Library(入库CSV)
- [x] **飞书报告** — 评分结果通过飞书卡片发送
- [x] **P04 Witch 真实验证** — 加载208条素材 → DNA分析 → 2图生成 → 评分8.18(Mock)/6.85(Lovart自评) → 入库

### ⚠️ 架构方向修正

**出图策略应从"猜 hook"转为"裂变赢家"**：
```
现在(有问题)：CSV分类hook_type → PromptForge生成 → 指望撞到赢家
应该(正确)：  Facebook跑赢的图 → 提取视觉DNA → 裂变生成变体 → 投放验证
```
当前 PromptForge 的 6 种 hook 模板(crisis/reward/twist等)只是过渡方案，长期应废弃，换成赢家图裂变引擎。

### ❌ 待完成

- [ ] **Facebook 赢家图裂变引擎**（核心任务）  
  从 creative_library.csv 中按 ROAS/spend 找 TOP 素材 → 提取元数据指纹 → 裂变变体  
  Meta API 就绪后升级为：拉赢家图 URL → 视觉DNA → remix生成
- [ ] **Meta Ads API 接入** — 拉取真实Facebook广告图片URL（META_ACCESS_TOKEN未配置）
- [ ] **生成图片自动上传 Meta Ads** — 创建ad creative + ad
- [ ] **定时自动化调度** — 每周自动跑闭环 + 飞书通知
- [ ] **人工审核流程** — 飞书预览卡片 + 按钮确认通过/淘汰

> ~~OpenAI Vision 真实评分~~ — Lovart 自评已完全替代，无需 OpenAI Key

---

## 七、已知问题 & 注意事项

### 1. Lovart SSL/TLS 握手异常 ⚠️

**现象**：Windows Python 3.10 调用 Lovart API 时出现 SSL 相关错误。

**影响范围**：
- **下载** (`a.lovart.ai` CDN)：`SSLEOFError(8)` → 需 `verify=False` fallback
- **上传** (`lgw.lovart.ai` 文件上传)：直接 `requests.post(verify=False)` 会因连接池污染报 `FileNotFoundError`

**修复方案**（已实施于 `lovart.py`）：
```python
# 下载：try正常 → except SSLError → verify=False
# 上传：始终用 requests.Session(verify=False) 避免连接池污染
session = _requests.Session()
session.verify = False
```

### 2. Lovart /chat 端点必须提供 project_id

每次 `/v1/openapi/chat` 调用必须带 `project_id` 字段，否则返回 400。`ensure_project()` 方法会在首次调用时自动创建项目。

### 3. GPT Image 2 需要 auto-confirm

该模型是付费模型(14 credits)，生成完成后需要 POST `/v1/openapi/chat/confirm` 确认。`generate_image()` 已内置自动确认逻辑。

### 4. .env 值需 strip

从 `.env` 读取的值末尾可能带换行符（`\n`），所有读取的值都需 `.strip()`。

### 5. Python 脚本需 PYTHONUTF8=1

PowerShell 中执行 Python 脚本时需设置环境变量：
```powershell
$env:PYTHONUTF8="1"; python script.py
```

### 6. PromptForge 方向修正：从"猜 hook"到"裂变赢家" ⚠️ 重要

当前 `_classify_hook()` / `_classify_emotion()` 采用简单关键词匹配，大部分素材被归为 `reward` + `satisfaction`，导致生成 prompt 缺乏多样性。更深层的问题是：**不应从 hook 分类出发猜什么会赢，而应从 Facebook 上实际跑赢的图出发做裂变。**

正确链路：
```
Facebook赢家图 → 提取视觉DNA(构图/配色/元素/文案) → 裂变生成变体 → 投放验证
```

Meta API 就绪前的过渡方案：
- 从 creative_library.csv 中按 ROAS/spend 找 TOP 素材
- 用其元数据指纹(hook_type/emotion/文案关键词)做变体
- 或人工输入已知赢家图的画面特征作为种子

---

## 八、建议开发顺序（供 zcode 参考）

### Phase 1：闭环能力加固（Meta API 未就绪时优先做）

1. **Facebook 赢家图裂变能力**（核心方向）  
   — 从 creative_library.csv 中按 ROAS/spend 找 TOP 素材  
   — 提取赢家素材的元数据指纹(hook_type/emotion/文案词/构图描述)  
   — 基于指纹做 prompt 变体裂变，而非从零猜 hook 类型  
   — Meta API 就绪后：直接拉赢家图 URL → 视觉DNA提取 → 裂变
2. **低门槛评分 → 真实淘汰测试** — 设 threshold=3.0 观察淘汰效果，逐步提高到 6.0
3. **多项目并行验证** — P02 Mermaid / P07 Vampire 也跑一轮闭环

### Phase 2：投放自动化

4. **生成图片上传 Meta Ads** — 创建ad creative + ad
5. **A/B测试管理** — 生成图 vs 原图的投放对比

### Phase 3：运营自动化

6. **定时任务** — Windows Task Scheduler 每周自动跑闭环
7. **飞书交互审核** — 卡片预览 + 人机确认流程
8. **效果回传闭环** — 投放数据回写评分模型，持续优化

---

## 九、开发约定

- 所有环境变量从 `.env` 读取，配置项在 `config.py` 的 `Settings` 类中定义
- CSV 读写使用 `encoding="utf-8-sig"`（兼容 Excel 打开）
- 数据模型使用 `@dataclass(slots=True)`
- 模块路径：`src/market_ops/`，CLI入口在 `if __name__ == "__main__"` 块
- 运行需从项目根目录执行，PYTHONPATH 需包含 `src/`
- 飞书集成使用 workspace 根目录下的 `.ps1` 脚本
