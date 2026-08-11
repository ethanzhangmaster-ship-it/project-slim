# V3.9 缺失能力分析 & V3.9.1 修复路线

**基于 V39_SYSTEM_AUDIT.md 审查结果**

---

## 一、已完成（✅）

| 能力 | 说明 |
|------|------|
| ✅ 视频拆Shot框架 | ShotExtractor + ShotDetector 类结构完整 |
| ✅ Shot数据库 | JSON存储、多维度索引、查询接口 |
| ✅ Shot角色分类 | 5种角色分类 + 置信度 |
| ✅ Winner结构挖掘框架 | 从CTR/CPI/ROI筛选Top performer |
| ✅ Remix Planner框架 | 按role匹配shot、生成方案 |
| ✅ 9种Mutation策略 | Hook替换/Early Reward/Speed Up等 |
| ✅ FFmpeg命令集 | cut/concat/crop/subtitle/bgm/speed |
| ✅ Quality Gate框架 | 6维度评分 + 等级划分 |
| ✅ UA Feedback闭环 | Facebook/TikTok/Google数据导入 |
| ✅ A/B Test框架 | 报告生成器完整 |

---

## 二、部分完成（⚠️）

| 能力 | 已有 | 缺失 |
|------|------|------|
| ⚠️ Shot边界检测 | 启发式时间切分 | 帧差/直方图/光流/深度学习SBD |
| ⚠️ Shot Embedding | One-Hot编码 | CLIP/视觉特征向量 |
| ⚠️ Winner结构 | 固定默认结构 | 从视频内容真实挖掘 |
| ⚠️ Shot匹配 | 字符串匹配 | 语义相似度+表现分加权 |
| ⚠️ Composer | FFmpeg命令完整 | 未真实运行 |
| ⚠️ Quality评分 | 内容质量分 | 投放指标（CTR/CPI/ROI） |

---

## 三、未完成（❌）

### ❌ 核心缺失（P0）

| 缺失模块 | 影响 | 优先级 |
|----------|------|--------|
| **Real Shot Boundary Detection** | 无法真实拆视频 | P0 |
| **Real Shot DNA Recognition** | DNA是猜的，不是识别的 | P0 |
| **Real Video Composition** | 没有输出MP4 | P0 |

### ❌ 投放效果缺失（P1）

| 缺失模块 | 影响 | 优先级 |
|----------|------|--------|
| **Ad Structure Engine** | 视频不像广告 | P1 |
| **Hook Optimization Engine** | 0-3秒不吸引人 | P1 |
| **Gameplay Clarity Engine** | 玩法看不懂 | P1 |
| **Creative Pacing Engine** | 节奏像PPT | P1 |
| **CTA Optimization** | 没有下载冲动 | P1 |
| **Retention Prediction** | 不知道看完率 | P1 |

---

## 四、V3.9.1 修复路线

### 目标

不是增加模块。

是让生成视频从：**素材拼接视频** → **真实买量Creative**

### 修复优先级

```
P0: Real Shot Intelligence
     ↓
P0: Real Video Composition
     ↓
P1: Ad Structure Engine
     ↓
P1: Hook Optimization
     ↓
P1: Creative Pacing
     ↓
P1: CTA Optimization
     ↓
P2: Performance Prediction Integration
```

### Phase 1: Real Shot Intelligence (P0)

**目标**: 让 Shot DNA 真实反映画面内容

| 修复项 | 当前 | 修复后 | 工作量 |
|--------|------|--------|--------|
| Shot Boundary Detection | 固定时间切分 | 帧差+直方图+光流 | 2天 |
| Shot DNA - Subject | 文件名keyword | OpenCV目标检测 | 2天 |
| Shot DNA - Action | 文件名keyword | 动作识别模型 | 3天 |
| Shot DNA - Emotion | 基于role推断 | 画面情绪分析 | 2天 |
| Shot DNA - Camera | 基于duration推断 | 镜头运动检测 | 1天 |
| Shot Embedding | One-Hot | CLIP/ResNet特征 | 1天 |

### Phase 2: Real Video Composition (P0)

**目标**: 真实生成可播放的MP4

| 修复项 | 当前 | 修复后 | 工作量 |
|--------|------|--------|--------|
| Composer执行 | 被注释掉 | 真实运行ffmpeg | 1天 |
| 错误处理 | 无 | 失败重试+日志 | 1天 |
| 输出验证 | 无 | 检查MP4完整性 | 0.5天 |

### Phase 3: Ad Structure Engine (P1)

**目标**: 视频结构符合买量广告规律

```
真实买量广告结构约束：

0-3秒 (Hook):
  - 必须: 冲突/痛点/好奇/危险
  - 必须: 角色出现
  - 必须: 强视觉刺激
  - 禁止: logo/loading/UI

3-8秒 (Gameplay):
  - 必须: 核心玩法展示
  - 必须: 玩家能理解操作
  - 必须: 进度/升级可视化

8-12秒 (Reward):
  - 必须: 爽点/爆发
  - 必须: 数字增长/升级动画
  - 必须: 正向反馈

12-15秒 (CTA):
  - 必须: Download/Play Now
  - 必须: 紧迫感
  - 必须: 按钮高亮
```

### Phase 4: Hook Optimization Engine (P1)

**目标**: 0-3秒必须抓住用户

| 能力 | 说明 |
|------|------|
| Hook文案库 | "ONLY 1% CAN FINISH", "SAVE THE WITCH!", "CAN YOU MERGE?" |
| 冲突检测 | 前3秒必须有冲突/危险/意外 |
| 角色出现检测 | 前3秒必须有角色/主角 |
| 视觉刺激检测 | 高对比度/快速运动/特效 |

### Phase 5: Creative Pacing Engine (P1)

**目标**: 控制节奏感

```
节奏模板：

前3秒:  快 (0.5s/shot, 快速切换)
中段:   稳 (2-3s/shot, 稳定展示)
结尾:   爆发 (0.3s/shot, 快速冲击)

转场规则：
- Hook→Gameplay: Impact Cut (硬切+音效)
- Gameplay→Reward: Zoom In (放大聚焦)
- Reward→CTA: Flash (闪烁强调)
```

### Phase 6: CTA Optimization (P1)

**目标**: 结尾必须有行动召唤

| 能力 | 说明 |
|------|------|
| CTA文案库 | "Download Now", "Play Free", "Join Now" |
| 按钮样式 | 高对比度按钮+箭头指示 |
| 紧迫感 | "Limited Time", "First 1000 Players" |
| 位置 | 屏幕底部居中，不遮挡内容 |

### Phase 7: Performance Prediction Integration (P2)

**目标**: Quality Gate 评分基于投放指标

```
Remix Score (V3.9.1):
  Hook Strength        20%
  Gameplay Clarity     15%
  Reward Impact        15%
  Structure Match      10%
  CTR Prediction       15%  ← 新增
  CPI Prediction       10%  ← 新增
  ROI Prediction       15%  ← 新增

总分 = Ad Value Prediction Score
```

---

## 五、V3.9.1 验收标准

| 验收项 | V3.9状态 | V3.9.1目标 | 验证方法 |
|--------|----------|------------|----------|
| 599视频拆Shot | ❌ 模拟 | ✅ 真实ffmpeg | 检查shot边界是否合理 |
| Shot DNA | ❌ 文件名推断 | ✅ CV识别 | 人工抽查10个shot |
| 生成MP4 | ❌ 无 | ✅ 20条真实视频 | 播放检查 |
| 前3秒吸引力 | ❌ 无约束 | ✅ Hook Engine | 人工评分1-10 |
| 玩法展示 | ❌ 无约束 | ✅ Gameplay Engine | 人工评分1-10 |
| 节奏感 | ❌ 固定fade | ✅ Pacing Engine | 人工评分1-10 |
| CTA | ❌ 模板文字 | ✅ CTA优化 | 人工评分1-10 |
| 是否像广告 | ❌ 素材拼接 | ✅ 真实买量Creative | 人工评分1-10 |

---

## 六、工作量估算

| Phase | 内容 | 工作量 |
|-------|------|--------|
| P0 - Real Shot Intelligence | 真实检测+识别 | 10天 |
| P0 - Real Composition | 真实生成MP4 | 2天 |
| P1 - Ad Structure Engine | 结构约束 | 3天 |
| P1 - Hook Optimization | Hook引擎 | 3天 |
| P1 - Creative Pacing | 节奏引擎 | 2天 |
| P1 - CTA Optimization | CTA引擎 | 2天 |
| P2 - Performance Integration | 投放预测 | 2天 |
| **总计** | | **~24天** |

---

## 七、核心判断

### V3.9 当前状态

```
框架完成度: 90%
算法完成度: 40%
真实运行度: 30%
-------------------
综合完成度: ~55%
```

### 关键结论

1. **V3.9 是一个完整的"框架"**，所有模块的类和接口都存在
2. **但核心算法是模拟/推断的**，没有真实CV/视频分析
3. **没有生成真实MP4**，Composer被注释掉了
4. **视频结构没有买量约束**，只是按role拼接shot
5. **Quality Gate评分不基于投放指标**

### V3.9.1 目标

```
V3.9: 素材拼接框架
  ↓
V3.9.1: 真实买量Creative生产系统
  ↓
V4.0: Autonomous Creative Factory
```

**V3.9.1 不是新增模块，而是让现有模块"真实工作"。**
