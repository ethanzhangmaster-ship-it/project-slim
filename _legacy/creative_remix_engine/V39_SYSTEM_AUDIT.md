# V3.9 Creative Remix Evolution Engine — 系统审计报告

**审计日期**: 2026-07-13
**审计范围**: creative_remix_engine/ 全部模块
**审计方法**: 源码审查 + 运行验证 + 输出检查

---

## 一、目录结构总览

| 模块 | 文件数 | 代码行数 | 状态 |
|------|--------|----------|------|
| shot_intelligence/ | 6 | ~800 | 框架完成 |
| remix_engine/ | 5 | ~1200 | 框架完成 |
| ua_connector/ | 4 | ~500 | 已完成 |
| ua_feedback/ | 4 | ~400 | 已完成 |
| performance_learning/ | 7 | ~1000 | 已完成 |
| experiments/ | 6 | ~600 | 框架完成 |
| **总计** | **32** | **~4500** | **框架完整** |

---

## 二、Phase-by-Phase 审计

### Phase 1: Shot Intelligence Layer

#### 1.1 Shot Extractor (`shot_extractor.py`)

| 检查项 | PRD要求 | 实际状态 | 结论 |
|--------|---------|----------|------|
| 视频格式支持 | mp4/mov/avi | 有扩展名检测逻辑 | ✅ |
| ffmpeg 调用 | 真实拆视频 | ffprobe只获取duration | ⚠️ |
| Shot时间段输出 | 真实start/end | 启发式生成 | ❌ |

**关键代码**:
```python
# 实际：只获取duration，边界是启发式生成的
cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", ...]
duration = float(result.stdout.strip())
boundaries = self._detect_with_heuristics(duration)  # ← 不是真实检测
```

#### 1.2 Shot Detector (`shot_detector.py`)

| 检查项 | PRD要求 | 实际状态 | 结论 |
|--------|---------|----------|------|
| Scene Change检测 | 真实检测场景变化 | 未实现 | ❌ |
| 镜头切换检测 | 真实检测镜头切换 | 未实现 | ❌ |
| 画面变化检测 | 真实检测画面变化 | 未实现 | ❌ |
| 输出精度 | 精确到帧 | 固定时间区间 | ❌ |

**关键代码**:
```python
def _detect_with_heuristics(self, duration: float) -> List[ShotBoundary]:
    # 典型的买量广告结构（固定切分！）
    typical_structure = [
        (0.0, 3.0, "hook"),      # 固定0-3秒
        (3.0, 10.0, "gameplay"), # 固定3-10秒
        (10.0, 20.0, "reward"),  # 固定10-20秒
        (20.0, duration, "ending"), # 固定20-结束
    ]
```

**结论**: 不是 Shot Boundary Detection。是固定时间分片。

#### 1.3 Shot Analyzer (`shot_analyzer.py`)

| DNA维度 | PRD要求 | 实际状态 | 结论 |
|---------|---------|----------|------|
| Subject识别 | CV识别画面内容 | 文件名keyword匹配 | ❌ |
| Action识别 | 理解merge/drag/upgrade | 文件名keyword匹配 | ❌ |
| Emotion识别 | 画面情绪分析 | 基于role推断 | ❌ |
| Camera识别 | 镜头语言分析 | 基于duration推断 | ❌ |
| Visual Score | 视觉质量评估 | 基于role+random | ❌ |

**关键代码**:
```python
def _infer_subject(self, video_name: str) -> str:
    name_lower = video_name.lower()
    for subject, keywords in self.subject_keywords.items():
        for kw in keywords:
            if kw in name_lower:
                return subject
    return "character"  # 默认
```

**结论**: 全部基于文件名keyword推断。没有CV分析。

#### 1.4 Shot Database (`shot_database.py`)

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 存储结构 | ✅ | JSON格式正确 |
| 多维度索引 | ✅ | role/subject/action/emotion/camera |
| 查询接口 | ✅ | query/get/query_by_role |
| 持久化 | ✅ | save/load 正确 |

#### 1.5 Shot Embedding (`shot_embedding.py`)

| 检查项 | PRD要求 | 实际状态 | 结论 |
|--------|---------|----------|------|
| CLIP embedding | 优先使用 | 未实现 | ❌ |
| Fallback视觉特征 | 视觉特征向量 | One-Hot编码 | ⚠️ |
| 相似度搜索 | 余弦相似度 | 已实现 | ✅ |
| 聚类 | K-Means | 简化实现 | ⚠️ |

#### 1.6 Shot Role Classifier (`shot_role_classifier.py`)

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 角色分类 | ✅ | hook/gameplay/reward/story/ending |
| 置信度输出 | ✅ | Softmax概率 |
| 上下文重分类 | ✅ | 位置偏好+后处理 |

---

### Phase 2: Winner Structure Miner

| 检查项 | PRD要求 | 实际状态 | 结论 |
|--------|---------|----------|------|
| 数据来源 | 真实投放CTR/CPI/ROI | 正确，从performance_data筛选 | ✅ |
| Top筛选 | Top 20% performer | 正确，按Ad Value排序 | ✅ |
| 结构提取 | 从视频内容分析结构 | 使用固定默认结构 | ❌ |
| 聚类 | 相似结构聚类 | 按role序列分组（简化） | ⚠️ |

**关键代码**:
```python
def _extract_structure(self, video: dict, shot_library: Optional[dict]):
    # 如果找不到shot_library，使用默认结构
    return self._infer_default_structure(video)

def _infer_default_structure(self, video: dict):
    # 固定结构！不是从内容挖掘的
    return [
        StructureSegment("hook", 3.0, "character", "attack", "surprise", "zoom_in"),
        StructureSegment("gameplay", 7.0, "character", "merge", "curiosity", "pan"),
        ...
    ]
```

---

### Phase 3: Remix Planner

| 检查项 | PRD要求 | 实际状态 | 结论 |
|--------|---------|----------|------|
| 生成数量 | 100+方案 | 支持配置 | ✅ |
| Winner结构匹配 | 按结构匹配 | 已实现 | ✅ |
| Shot匹配 | DNA相似度匹配 | 字符串匹配+表现分 | ⚠️ |
| 广告结构约束 | 0-3s痛点/3-8s玩法/8-12s爽点/12-15sCTA | 只有role匹配，无结构约束 | ❌ |

**关键问题**: Planner 只按 role 匹配 shot，没有真正的"买量广告结构约束"。

---

### Phase 4: Creative Remix Composer

#### 4.1 Timeline Builder

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 时间线构建 | ✅ | 正确构建clip序列 |
| 转场 | ⚠️ | 固定fade，无变化 |
| 字幕 | ❌ | 固定模板文字("Amazing!""Play Now!") |
| 9:16 Crop | ✅ | ffmpeg crop逻辑正确 |

#### 4.2 FFmpeg Editor

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 视频切割 | ✅ | ffmpeg -ss -t 正确 |
| 视频拼接 | ✅ | ffmpeg concat 正确 |
| 字幕叠加 | ✅ | drawtext 正确 |
| BGM混合 | ✅ | amix 正确 |
| 速度调整 | ✅ | setpts/atempo 正确 |

#### 4.3 关键缺陷

```python
# v39_ab_test.py 第142行
print("[Step 7] Composing Videos (simulated)...")
# composer = CreativeRemixComposer(video_source_dir, self.output_dir / "v39_creatives")
# results = composer.compose_batch(top_remix)
```

**Composer 被注释掉了！没有真实生成视频。**

---

### Phase 5: Remix Mutation Engine

| 策略 | 状态 | 说明 |
|------|------|------|
| Swap Hook | ✅ | 替换hook段 |
| Early Reward | ✅ | 调整顺序 |
| Speed Up | ✅ | 缩短时长 |
| Extend Segment | ✅ | 延长某段 |
| Add Story | ✅ | 插入story |
| Double Reward | ✅ | 双reward |
| Drop Ending | ✅ | 去掉ending |
| Shuffle | ✅ | 打乱顺序 |
| Shorten | ✅ | 缩短至20s |

---

### Phase 6: Remix Quality Gate

| 检查项 | PRD要求 | 实际权重 | 结论 |
|--------|---------|----------|------|
| Hook | 30% | 25% | ⚠️ |
| Gameplay | 25% | 20% | ⚠️ |
| Reward | 20% | 20% | ✅ |
| Structure | 15% | 10% (Winner Similarity) | ⚠️ |
| Visual | 10% | 15% (Visual Density) | ⚠️ |
| **投放指标** | **Ad Value/CTR/CPI/ROI** | **未包含** | **❌** |

**关键缺失**: Quality Gate 没有投放指标（CTR/CPI/ROI prediction），只有内容质量分。

---

### Phase 7: UA Feedback Integration

| 检查项 | 状态 | 说明 |
|--------|------|------|
| Facebook Connector | ✅ | 模拟数据 |
| TikTok Connector | ✅ | 模拟数据 |
| Google Ads Connector | ✅ | 模拟数据 |
| 指标计算 | ✅ | CTR/CPI/ROI/CVR |
| DNA-Performance Mapping | ✅ | 已关联 |

---

### Phase 8: V3.9 A/B Test

| 检查项 | PRD要求 | 实际状态 | 结论 |
|--------|---------|----------|------|
| 20条视频对比 | 10 baseline + 10 remix | 只有JSON数据 | ❌ |
| 真实视频输出 | creatives/001.mp4 ... | 没有MP4文件 | ❌ |
| CTR指标 | 真实对比 | 模拟数据 | ❌ |
| CPI指标 | 真实对比 | 模拟数据 | ❌ |
| 报告生成 | HTML报告 | 已生成 | ✅ |

---

## 三、完成度汇总

| 模块 | 框架 | 算法 | 真实运行 | 综合评分 |
|------|------|------|----------|----------|
| Shot Extractor | ✅ | ❌ | ❌ | 30% |
| Shot Detector | ✅ | ❌ | ❌ | 20% |
| Shot DNA | ✅ | ❌ | ❌ | 20% |
| Shot Database | ✅ | ✅ | ✅ | 90% |
| Shot Embedding | ✅ | ⚠️ | ✅ | 50% |
| Shot Role Classifier | ✅ | ✅ | ✅ | 80% |
| Winner Structure Miner | ✅ | ⚠️ | ✅ | 50% |
| Remix Planner | ✅ | ⚠️ | ✅ | 60% |
| Remix Mutation | ✅ | ✅ | ✅ | 85% |
| Remix Quality Gate | ✅ | ⚠️ | ✅ | 60% |
| Composer (FFmpeg) | ✅ | ⚠️ | ❌ | 50% |
| UA Feedback | ✅ | ✅ | ✅ | 85% |
| A/B Test | ✅ | ❌ | ❌ | 40% |
| **整体** | **90%** | **40%** | **30%** | **~55%** |

---

## 四、严重问题清单

### 🔴 P0 — 阻塞问题

1. **没有真实 Shot Boundary Detection**
   - 当前是固定时间切分（0-3s/3-10s/10-20s/20-30s）
   - 需要：帧差法/直方图差异/光流分析/深度学习SBD

2. **Shot DNA 全部基于文件名推断**
   - 没有CV分析画面内容
   - 没有真实识别subject/action/emotion

3. **没有生成真实MP4文件**
   - Composer 在A/B Test中被注释掉
   - output/v39/creatives/ 目录不存在

### 🟡 P1 — 重大问题

4. **没有买量广告结构约束**
   - Planner 只按role匹配，没有"0-3s必须痛点/冲突"等约束

5. **Hook 文案不是买量文案**
   - 字幕是"Amazing!""Play Now!"
   - 需要："ONLY 1% CAN FINISH THIS"等真实买量Hook

6. **Quality Gate 缺投放指标**
   - 没有CTR/CPI/ROI prediction
   - 评分不是Ad Value驱动的

7. **没有 Creative Pacing Engine**
   - 转场固定fade
   - 没有节奏控制（前3s快/中段稳/结尾爆发）

---

## 五、验收标准检查

| 验收项 | PRD要求 | 实际状态 | 结论 |
|--------|---------|----------|------|
| 599历史视频拆Shot | ✅ | 模拟数据 | ❌ |
| 建立Shot数据库 | ✅ | 已完成 | ✅ |
| 自动发现Winner结构 | ✅ | 部分完成 | ⚠️ |
| 自动生成100个Remix方案 | ✅ | 支持配置 | ✅ |
| 自动合成20条真实视频 | ✅ | 未执行 | ❌ |
| 无AI生成视频内容 | ✅ | 确认 | ✅ |
| FFmpeg可复现 | ✅ | 命令正确但未运行 | ⚠️ |
| A/B Test报告 | ✅ | 已生成 | ✅ |
