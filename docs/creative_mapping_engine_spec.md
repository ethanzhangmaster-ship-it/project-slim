# Creative Mapping Engine — 规格

> **版本**: v1.8 (v1.6/v1.7/v1.8 已实现)
> **日期**: 2026-08-10
> **状态**: v1.5-v1.8 已实现
> **依赖**: spec-first 流程 (本 Spec 批准 → 实现 → 测试 → 版本递增)
> **变更**: 
> - v1.1 新增第十章 Eagle Scanner（自动生成素材索引）
> - v1.2 新增第十一章 Frame Similarity（启用 CLIP embedding，恢复阈值 0.85）
> - v1.3 新增第十二章 CLIP 性能优化（预加载、批量计算、GPU 加速、embedding 缓存）
> - v1.4 新增第十三章 Facebook Creative Ingestion（从 Facebook API 拉取创意元数据，补全 duration/resolution）
> - v1.5 新增第十四章 Delivery Bridge（映射记录 → 广告投放系统的交付桥接层）；新增第十五章 v1.6/v1.7 路线图
> - v1.6 实现第十五章 投放结构自动创建（CampaignStrategyBuilder + FacebookPublisher 集成，dispatch_with_auto_structure + deliver-auto API）
> - v1.7 实现第十六章 成效反馈环（FacebookInsightsIngester + CreativePerformance + insights/ingest API）
> - v1.8 实现第十七章 投放策略优化（DeliveryStrategyOptimizer + 自动归档 + 优先级排名 + strategy API）

---

## 一、定位与目标

### 1.1 问题

系统已有多套分散的创意素材匹配机制（Asset Binding 3 级视频匹配、Adjust 4 级匹配、A 号匹配、DNA 融合匹配），但存在三个核心问题：

1. **机制分散**：匹配逻辑分布在 `creative_asset_binding/`、`adjust_ingestion/matcher.py`、`creative_dna_fusion.py` 等多个模块，缺乏统一入口
2. **数据缺口**：`data/creatives/` 目录未实际生成，依赖的 CSV 文件缺失，运行时数据流未跑通
3. **无人工审核闭环**：未匹配或低置信度素材没有统一的审核队列和工作流

### 1.2 目标

构建统一的 **Creative Mapping Engine**，作为所有未来 Agent 协同的创意资产映射基础层：

- 统一多维度匹配入口（名称相似度、时长、分辨率、创建时间、帧相似度、hash）
- 综合置信度评分（0.0-1.0）
- 未匹配/低置信度素材进入人工审核队列
- 优先使用内部素材库（Eagle）而非 Facebook 视频下载
- 持久化映射记录到 `data/creative_mapping/`

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| **内部优先** | 优先匹配内部 Eagle 素材库，Facebook 下载仅作为回退 |
| **多维度融合** | 6 个维度独立评分，加权综合，避免单点失效 |
| **置信度门禁** | 低于阈值的匹配进入人工审核，不自动确认 |
| **幂等可重放** | 相同输入产生相同映射结果，支持重跑 |
| **统一入口** | 所有 Agent 通过 Mapping Engine 查询创意映射，不直接访问底层匹配器 |

---

## 二、核心数据模型

### 2.1 CreativeMappingRecord（映射记录）

```python
@dataclass
class CreativeMappingRecord:
    """创意映射记录 — 一个 Facebook/Meta creative 与内部素材的映射关系。"""

    mapping_id: str               # 唯一标识 (creative_id 的 hash)
    facebook_creative_id: str     # Facebook creative_id
    facebook_creative_name: str   # Facebook creative 名称
    facebook_account_id: str      # 广告账户 ID

    # 映射目标 (以下至少一项非空)
    eagle_filename: str = ""      # Eagle 素材文件名
    eagle_path: str = ""          # Eagle 素材完整路径
    local_path: str = ""          # 本地素材路径 (非 Eagle)

    # 多维度匹配评分 (0.0-1.0)
    scores: MappingScores = field(default_factory=MappingScores)

    # 综合结果
    confidence: float = 0.0       # 综合置信度
    match_method: str = ""        # 主匹配方法 (name/duration/resolution/creation_time/frame_hash/file_hash)
    status: MappingStatus = MappingStatus.PENDING  # 映射状态

    # 元数据
    created_at: str = ""          # 创建时间
    updated_at: str = ""          # 更新时间
    reviewed_by: str = ""         # 人工审核者 (如有)
    review_note: str = ""         # 审核备注

    def to_dict(self) -> dict: ...
```

### 2.2 MappingScores（多维度评分）

```python
@dataclass
class MappingScores:
    """6 维度独立评分，每个维度 0.0-1.0。"""

    name_similarity: float = 0.0       # 名称相似度 (字符串编辑距离/序列号匹配)
    duration_match: float = 0.0        # 时长匹配 (差值在容差范围内)
    resolution_match: float = 0.0      # 分辨率匹配 (完全匹配/宽高比匹配)
    creation_time_match: float = 0.0   # 创建时间匹配 (时间窗口内)
    frame_similarity: float = 0.0      # 帧相似度 (视觉 Hash/CLIP cosine)
    file_hash_match: float = 0.0       # 文件哈希匹配 (精确匹配=1.0)

    def weighted_total(self, weights: dict[str, float]) -> float:
        """加权综合评分。"""
        ...
```

### 2.3 MappingStatus（映射状态）

```python
class MappingStatus(str, Enum):
    PENDING = "pending"           # 待匹配
    MATCHED = "matched"           # 自动匹配成功 (confidence >= threshold)
    NEEDS_REVIEW = "needs_review" # 低置信度，需人工审核
    REVIEW_APPROVED = "approved"  # 人工审核通过
    REVIEW_REJECTED = "rejected"  # 人工审核驳回
    NO_MATCH = "no_match"         # 无任何匹配候选
    ARCHIVED = "archived"         # 已归档
```

### 2.4 ReviewTask（人工审核任务）

```python
@dataclass
class ReviewTask:
    """人工审核任务。"""

    task_id: str                  # 任务 ID
    mapping_id: str               # 关联的映射记录 ID
    facebook_creative_id: str     # Facebook creative_id
    candidates: list[dict]        # 候选匹配列表 (含各维度评分)
    created_at: str               # 创建时间
    status: str = "open"          # open / approved / rejected / expired
    assigned_to: str = ""         # 分配给谁
    resolution: str = ""          # 审核结论
    resolved_at: str = ""         # 审核时间
```

---

## 三、多维度匹配算法

### 3.1 匹配维度与权重

| 维度 | 权重 | 算法 | 说明 |
|------|------|------|------|
| name_similarity | 0.25 | 序列号提取 + Levenshtein 编辑距离 | 提取 6 位序列号精确匹配=1.0；否则编辑距离归一化 |
| duration_match | 0.15 | 绝对差值容差 | 差值 ≤ 0.5s = 1.0；≤ 2s = 0.7；> 2s = 0.0 |
| resolution_match | 0.10 | 完全匹配 / 宽高比匹配 | 完全匹配=1.0；宽高比匹配=0.7；不匹配=0.0 |
| creation_time_match | 0.10 | 时间窗口 | 差值 ≤ 1天=1.0；≤ 7天=0.7；> 7天=0.3 |
| frame_similarity | 0.25 | CLIP embedding cosine / 视觉 Hash 汉明距离 | cosine ≥ 0.95=1.0；≥ 0.85=0.85；< 0.85=0.0 |
| file_hash_match | 0.15 | MD5/SHA256 精确匹配 | 完全匹配=1.0；不匹配=0.0 |

### 3.2 综合置信度

```python
confidence = sum(weight[i] * score[i] for i in dimensions)
```

### 3.3 置信度门禁

| 阈值 | 行为 |
|------|------|
| confidence ≥ 0.85 | 自动确认 (status=MATCHED) |
| 0.50 ≤ confidence < 0.85 | 人工审核 (status=NEEDS_REVIEW) |
| confidence < 0.50 | 标记无匹配 (status=NO_MATCH) |

> 注：v1.2 启用 CLIP embedding 帧相似度计算后，6 维度全部可计算，
> 阈值从 0.75 恢复到 0.85。

### 3.4 匹配流程

```
输入: Facebook creative (id, name, thumbnail, video_url, ...)
  │
  ├── 1. 加载 Eagle 素材索引
  │
  ├── 2. 对每个 Eagle 素材计算 6 维度评分
  │      ├── name_similarity: 序列号提取 + 编辑距离
  │      ├── duration_match: 时长差值容差
  │      ├── resolution_match: 分辨率/宽高比
  │      ├── creation_time_match: 时间窗口
  │      ├── frame_similarity: 视觉 Hash (可选, 需加载缩略图)
  │      └── file_hash_match: 文件哈希
  │
  ├── 3. 加权综合 → confidence
  │
  ├── 4. 选择最高 confidence 的候选
  │
  ├── 5. 置信度门禁判定
  │      ├── ≥ 0.85 → MATCHED (自动确认)
  │      ├── ≥ 0.50 → NEEDS_REVIEW (入审核队列)
  │      └── < 0.50 → NO_MATCH
  │
  └── 6. 持久化映射记录到 data/creative_mapping/records.jsonl
```

---

## 四、数据持久化

### 4.1 文件结构

```
data/creative_mapping/
  ├── records.jsonl          # 映射记录 (append-only)
  ├── review_queue.jsonl     # 人工审核队列 (append-only)
  └── stats.json             # 统计摘要 (每次操作后覆盖)
```

### 4.2 records.jsonl 格式

每行一个 CreativeMappingRecord 的 JSON：

```json
{
  "mapping_id": "fb_c536_abc123",
  "facebook_creative_id": "536123456789",
  "facebook_creative_name": "MW_VIDEO_260721_000123",
  "facebook_account_id": "act_123456",
  "eagle_filename": "MW_VIDEO_260721_000123.mp4",
  "eagle_path": "D:/eagle/MW_VIDEO_260721_000123.mp4",
  "scores": {
    "name_similarity": 1.0,
    "duration_match": 1.0,
    "resolution_match": 1.0,
    "creation_time_match": 0.7,
    "frame_similarity": 0.0,
    "file_hash_match": 0.0
  },
  "confidence": 0.745,
  "match_method": "name_similarity",
  "status": "needs_review",
  "created_at": "2026-08-10T12:00:00Z",
  "updated_at": "2026-08-10T12:00:00Z",
  "reviewed_by": "",
  "review_note": ""
}
```

### 4.3 幂等性

- 相同 `facebook_creative_id` 的重复映射请求返回已有记录
- 已有 `MATCHED` 状态的记录不会被低置信度结果覆盖
- `REVIEW_APPROVED` 状态的记录不会被自动匹配覆盖

---

## 五、API 端点

### 5.1 映射操作

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/creative-mapping/match` | 执行单条创意映射 (输入 Facebook creative 信息) |
| POST | `/api/creative-mapping/batch-match` | 批量映射 (输入多条 creative) |
| GET | `/api/creative-mapping/records` | 查询映射记录列表 (支持 status/game_id 筛选) |
| GET | `/api/creative-mapping/records/{mapping_id}` | 查询单条映射记录详情 |
| GET | `/api/creative-mapping/records/by-facebook/{fb_creative_id}` | 按 Facebook creative_id 查询映射 |

### 5.2 人工审核

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/creative-mapping/review/queue` | 获取待审核队列 |
| POST | `/api/creative-mapping/review/{task_id}/approve` | 审核通过 (指定 eagle_filename) |
| POST | `/api/creative-mapping/review/{task_id}/reject` | 审核驳回 (附理由) |

### 5.3 统计

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/creative-mapping/stats` | 映射统计 (总数/各状态分布/平均置信度) |

### 5.4 匹配请求体示例

```json
{
  "facebook_creative_id": "536123456789",
  "facebook_creative_name": "MW_VIDEO_260721_000123",
  "facebook_account_id": "act_123456",
  "thumbnail_url": "https://...",
  "video_url": "https://...",
  "duration": 32.5,
  "resolution": "1080x1920",
  "game_id": "merge_witches"
}
```

### 5.5 匹配响应体示例

```json
{
  "mapping_id": "fb_536123456789_a1b2c3",
  "facebook_creative_id": "536123456789",
  "status": "matched",
  "confidence": 0.92,
  "match_method": "name_similarity",
  "eagle_filename": "MW_VIDEO_260721_000123.mp4",
  "eagle_path": "D:/eagle/MW_VIDEO_260721_000123.mp4",
  "scores": {
    "name_similarity": 1.0,
    "duration_match": 1.0,
    "resolution_match": 1.0,
    "creation_time_match": 0.7,
    "frame_similarity": 0.85,
    "file_hash_match": 0.0
  },
  "candidates_evaluated": 5
}
```

---

## 六、与现有系统的集成

### 6.1 复用现有匹配器

Creative Mapping Engine **不重新实现**已有匹配逻辑，而是编排现有匹配器：

| 现有模块 | 复用方式 |
|---------|---------|
| `creative_asset_binding/video_matcher.py` | 3 级视频匹配 → name_similarity + frame_similarity 维度 |
| `creative_asset_binding/a_number_matcher.py` | A 号匹配 → name_similarity 维度 |
| `creative_asset_binding/eagle_indexer.py` | Eagle 素材索引加载 |
| `creative_asset_binding/models.py` | EagleAsset 数据结构 |

### 6.2 不修改的部分

- 现有 `creative_asset_binding/` 模块保持不变
- 现有 `creative_repository/` 数据模型保持不变
- 现有 API 签名保持不变

### 6.3 新增的部分

- `src/market_ops/creative_mapping_engine/` — 新模块
- `data/creative_mapping/` — 新数据目录
- `app.py` 中新增 API 端点

---

## 七、模块结构

```
src/market_ops/creative_mapping_engine/
  ├── __init__.py
  ├── engine.py              # CreativeMappingEngine 核心编排
  ├── scorers.py             # 6 维度评分器
  ├── review_queue.py        # 人工审核队列管理
  ├── store.py               # 持久化层 (records.jsonl + review_queue.jsonl)
  └── models.py              # 数据模型 (CreativeMappingRecord, MappingScores, etc.)
```

### 7.1 核心类

```python
class CreativeMappingEngine:
    """创意映射引擎 — 统一多维度匹配入口。"""

    def __init__(
        self,
        data_dir: str = "data/creative_mapping",
        eagle_index_path: str = "data/eagle_scan_index.json",
        confidence_threshold: float = 0.85,
        review_threshold: float = 0.50,
    ): ...

    def match(self, facebook_creative: dict) -> CreativeMappingRecord:
        """执行单条创意映射。"""
        ...

    def batch_match(self, creatives: list[dict]) -> list[CreativeMappingRecord]:
        """批量映射。"""
        ...

    def get_record(self, mapping_id: str) -> CreativeMappingRecord | None: ...
    def list_records(self, status: str = "", limit: int = 50) -> list[CreativeMappingRecord]: ...
    def get_stats(self) -> dict: ...
```

### 7.2 评分器

```python
class MappingScorer:
    """6 维度评分器。"""

    def score_name_similarity(self, fb_name: str, eagle_filename: str) -> float: ...
    def score_duration_match(self, fb_duration: float, eagle_duration: float) -> float: ...
    def score_resolution_match(self, fb_res: str, eagle_res: str) -> float: ...
    def score_creation_time_match(self, fb_time: str, eagle_time: str) -> float: ...
    def score_frame_similarity(self, fb_thumbnail: str, eagle_path: str) -> float: ...
    def score_file_hash_match(self, fb_hash: str, eagle_hash: str) -> float: ...

    def weighted_total(self, scores: MappingScores) -> float: ...
```

### 7.3 审核队列

```python
class ReviewQueue:
    """人工审核队列管理。"""

    def enqueue(self, mapping_id: str, candidates: list[dict]) -> ReviewTask: ...
    def dequeue(self, limit: int = 10) -> list[ReviewTask]: ...
    def approve(self, task_id: str, eagle_filename: str, reviewer: str = "") -> ReviewTask: ...
    def reject(self, task_id: str, reason: str, reviewer: str = "") -> ReviewTask: ...
    def list_open(self, limit: int = 50) -> list[ReviewTask]: ...
```

---

## 八、验收标准

### 8.1 功能验收

- [ ] 单条创意映射：输入 Facebook creative → 输出映射记录 + 置信度
- [ ] 批量映射：支持 ≥ 50 条 creative 批量处理
- [ ] 6 维度评分：每个维度独立计算，加权综合
- [ ] 置信度门禁：≥ 0.85 自动确认；0.50-0.85 人工审核；< 0.50 无匹配
- [ ] 人工审核：审核队列 + 通过/驳回工作流
- [ ] 幂等性：相同输入返回相同结果
- [ ] 持久化：记录写入 `data/creative_mapping/records.jsonl`
- [ ] API 端点：8 个端点全部可用

### 8.2 测试验收

- [ ] 核心模块单元测试 ≥ 30 个
- [ ] API 集成测试 ≥ 15 个
- [ ] 全量回归测试无新增失败
- [ ] 覆盖场景：精确匹配、模糊匹配、无匹配、低置信度审核、幂等重跑

---

## 九、不在本阶段范围

以下内容明确排除在本 Spec 之外：

- DNA/Genome 匹配（已有 `creative_dna_fusion.py`，不在本引擎内重复）
- Creative 生成（已有 `creative_factory.py`）
- Facebook 素材下载（本引擎仅消费已有素材索引，不负责下载）
- 视觉 Hash 计算的实际实现（本引擎预留接口，实际 CLIP/Hash 计算委托给现有 `video_matcher.py`）
- 前端 UI（后端 API 优先）
- 投放成效回流与素材排序优化（v1.7 范围，见第十五章预告）
- 投放结构自动创建（Campaign/AdSet 生成，v1.6 范围，见第十五章预告）

---

## 十、Eagle Scanner — 素材库自动索引

### 10.1 问题

Creative Mapping Engine 依赖 `data/eagle_scan_index.json` 提供候选素材列表，但该索引文件目前需要手动维护或依赖外部 `creative_asset_binding/EagleScanner` 生成。存在以下问题：

1. **索引缺失**：`data/eagle_scan_index.json` 不存在时，所有映射返回 NO_MATCH
2. **元数据缺口**：现有扫描器不提取 `duration`、`resolution`、`created_at`，导致 3 个维度无法评分
3. **无 API 触发**：没有 API 端点触发扫描，必须手动运行脚本
4. **无引擎集成**：扫描后无法自动刷新 Creative Mapping Engine 的内存缓存

### 10.2 目标

在 `creative_mapping_engine` 模块内实现 `EagleScanner`，提供：

- 全量扫描指定目录，递归收集视频/图片文件
- 提取元数据：filename, path, creative_asset_id, file_hash, file_size, created_at
- 可选提取 duration/resolution（通过 ffprobe，不可用时降级为空值）
- 持久化索引到 `data/eagle_scan_index.json`
- 增量扫描：检测新增/变更/删除文件
- 扫描后自动刷新 CreativeMappingEngine 缓存
- API 端点触发扫描和查询索引

### 10.3 数据结构

索引文件 `data/eagle_scan_index.json` 格式：

```json
{
  "scanned_at": "2026-08-10T12:00:00Z",
  "root_dir": "D:/eagle/library",
  "total": 150,
  "video_count": 120,
  "image_count": 30,
  "assets": [
    {
      "filename": "MW_VIDEO_260721_000123.mp4",
      "path": "D:/eagle/library/MW_VIDEO_260721_000123.mp4",
      "creative_asset_id": "MW_VIDEO_260721_000123",
      "duration": 32.5,
      "resolution": "1080x1920",
      "file_hash": "abc123def456",
      "file_size": 5242880,
      "created_at": "2026-07-24T10:30:00Z"
    }
  ]
}
```

### 10.4 扫描算法

```
输入: eagle_root (目录路径)
  │
  ├── 1. 递归遍历目录，收集视频/图片文件
  │      ├── 视频扩展名: .mp4, .mov, .avi, .webm, .mkv
  │      └── 图片扩展名: .png, .jpg, .jpeg, .gif, .webp, .bmp
  │
  ├── 2. 对每个文件提取元数据
  │      ├── filename: 文件名
  │      ├── path: 绝对路径
  │      ├── creative_asset_id: 从文件名提取 MW_类型_日期_序列号
  │      ├── file_hash: MD5 采样哈希（前1KB + 中1KB + 后1KB）
  │      ├── file_size: 文件大小（bytes）
  │      ├── created_at: 文件创建时间（ISO 格式）
  │      ├── duration: 视频时长（ffprobe，可选）
  │      └── resolution: 视频分辨率（ffprobe，可选）
  │
  ├── 3. 持久化到 data/eagle_scan_index.json
  │
  └── 4. 刷新 CreativeMappingEngine 缓存
```

### 10.5 增量扫描

增量扫描对比上次索引，检测变更：

| 变更类型 | 检测方法 |
|---------|---------|
| 新增 | 当前索引中存在，上次索引中不存在（按 path 对比） |
| 变更 | path 相同但 file_hash 不同 |
| 删除 | 上次索引中存在，当前索引中不存在 |

### 10.6 ffprobe 降级策略

| 条件 | 行为 |
|------|------|
| ffprobe 可用且为视频文件 | 提取 duration 和 resolution |
| ffprobe 不可用或非视频文件 | duration=0.0, resolution="" |

降级时记录 warning 日志，不中断扫描。

### 10.7 API 端点

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/creative-mapping/eagle/scan` | 触发全量扫描（请求体指定 eagle_root） |
| POST | `/api/creative-mapping/eagle/scan-incremental` | 触发增量扫描 |
| GET | `/api/creative-mapping/eagle/index` | 查询当前索引（含统计） |
| GET | `/api/creative-mapping/eagle/index/stats` | 查询索引统计摘要 |

### 10.8 扫描请求体

```json
{
  "eagle_root": "D:/eagle/library",
  "extract_metadata": true
}
```

- `eagle_root`: Eagle 素材库根目录（必填）
- `extract_metadata`: 是否使用 ffprobe 提取 duration/resolution（默认 true）

### 10.8 扫描响应体

```json
{
  "status": "ok",
  "scanned_at": "2026-08-10T12:00:00Z",
  "root_dir": "D:/eagle/library",
  "total": 150,
  "video_count": 120,
  "image_count": 30,
  "new_count": 5,
  "changed_count": 2,
  "removed_count": 1,
  "elapsed_seconds": 3.2
}
```

### 10.9 模块结构更新

```
src/market_ops/creative_mapping_engine/
  ├── __init__.py
  ├── engine.py              # CreativeMappingEngine 核心编排
  ├── scorers.py             # 6 维度评分器
  ├── review_queue.py        # 人工审核队列管理
  ├── store.py               # 持久化层
  ├── scanner.py             # EagleScanner 素材库扫描器 (v1.1 新增)
  └── models.py              # 数据模型
```

### 10.10 验收标准

- [x] 全量扫描：递归扫描目录，生成完整索引
- [x] 元数据提取：filename, path, creative_asset_id, file_hash, file_size, created_at
- [x] ffprobe 可选：不可用时降级为空值，不中断扫描
- [x] 增量扫描：检测新增/变更/删除
- [x] 持久化：索引写入 `data/eagle_scan_index.json`
- [x] 引擎集成：扫描后刷新 CreativeMappingEngine 缓存
- [x] API 端点：4 个端点全部可用
- [x] 单元测试 ≥ 20 个 (37 个测试通过)
- [x] 全量回归测试无新增失败

---

## 十一、Frame Similarity — CLIP embedding 帧相似度计算

### 11.1 背景

v1.0 中 `frame_similarity` 维度为预留接口（始终返回 0.0），其 0.25 权重导致 6 维全匹配时最高置信度仅 0.75，阈值被迫降至 0.75。

v1.2 启用 CLIP embedding 计算实际帧相似度，恢复 0.85 阈值。

### 11.2 目标

实现 `FrameSimilarityComputer`，提供：

- 从图片路径/URL 加载图像
- 从视频文件提取首帧（使用 ffmpeg）
- 生成 CLIP embedding（使用 openai-clip 或 transformers 库）
- 计算 cosine similarity
- 优雅降级：CLIP 不可用时回退到 pHash 感知哈希

### 11.3 数据流

```
输入: facebook_thumbnail (URL/path), eagle_video_path (视频文件路径)
  │
  ├── 1. 加载 Facebook 缩略图
  │      └── URL → 下载 → PIL.Image
  │      └── 本地路径 → PIL.Image
  │
  ├── 2. 提取 Eagle 视频首帧
  │      └── ffmpeg -i video.mp4 -vframes 1 -f image2pipe → PIL.Image
  │
  ├── 3. 生成 CLIP embedding
  │      ├── CLIP 可用 → 两向量 (512-dim)
  │      └── CLIP 不可用 → 回退到 pHash
  │
  ├── 4. 计算相似度
  │      ├── CLIP: cosine similarity ∈ [-1, 1]
  │      └── pHash: 1 - hamming_distance / 64
  │
  └── 5. 归一化评分 (0.0-1.0)
         ├── cosine ≥ 0.95 → 1.0
         ├── cosine ≥ 0.85 → 0.85
         ├── cosine ≥ 0.70 → 0.70
         └── cosine < 0.70 → 0.0
```

### 11.4 评分门禁

| 相似度 (cosine) | frame_similarity 评分 |
|----------------|----------------------|
| ≥ 0.95 | 1.0 |
| ≥ 0.85 | 0.85 |
| ≥ 0.70 | 0.70 |
| < 0.70 | 0.0 |

### 11.5 降级策略

| 条件 | 行为 |
|------|------|
| CLIP 库可用 + 图像加载成功 | 使用 CLIP embedding + cosine similarity |
| CLIP 库不可用 | 回退到 pHash (imagehash 库)，计算 1 - hamming/64 |
| 图像加载失败 (URL 不可达/文件损坏) | 返回 0.0，记录 warning 日志 |
| 视频首帧提取失败 | 回退到视频文件 hash 对比（非帧内容） |

### 11.6 缓存机制

为避免重复计算，FrameSimilarityComputer 内部维护 LRU 缓存：

- 缓存键: `(thumbnail_source, eagle_path)` 的 hash
- 缓存值: embedding 向量或相似度评分
- 缓存上限: 1000 条 (LRU 淘汰)
- 缓存命中时直接返回评分，跳过计算

### 11.7 模块结构

```
src/market_ops/creative_mapping_engine/
  ├── __init__.py
  ├── engine.py              # CreativeMappingEngine 核心编排
  ├── scorers.py             # 6 维度评分器 (v1.2 集成 FrameSimilarityComputer)
  ├── review_queue.py        # 人工审核队列管理
  ├── store.py               # 持久化层
  ├── scanner.py             # EagleScanner 素材库扫描器
  ├── frame_similarity.py    # FrameSimilarityComputer (v1.2 新增)
  └── models.py              # 数据模型
```

### 11.8 API 集成

在现有 `POST /api/creative-mapping/match` 中自动启用：
- `MappingScorer` 持有 `FrameSimilarityComputer` 实例
- 当 `fb_thumbnail` 和 `eagle_path` 均有效时计算帧相似度
- 任一为空时返回 0.0（不阻断其他维度）

新增 API 端点：

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/creative-mapping/frame-similarity` | 手动计算两个素材的帧相似度 |

请求体:
```json
{
  "thumbnail_source": "http://... 或 /path/to/image.jpg",
  "eagle_path": "/path/to/video.mp4"
}
```

响应体:
```json
{
  "score": 0.92,
  "method": "clip",  // clip | phash | none
  "cached": false
}
```

### 11.9 验收标准

- [x] CLIP 可用时：正确计算 cosine similarity 并归一化评分
- [x] CLIP 不可用时：回退到 pHash，不中断评分流程
- [x] 图像加载失败：返回 0.0，记录 warning
- [x] LRU 缓存：相同输入命中缓存
- [x] 阈值恢复：`confidence_threshold` 从 0.75 恢复到 0.85
- [x] 6 维全匹配时综合置信度 ≥ 0.85
- [x] 单元测试 ≥ 15 个 (34 个测试通过)
- [x] 全量回归测试无新增失败

---

## 十二、CLIP 性能优化 — 预加载、批量计算、GPU 加速

### 12.1 背景

v1.2 中 CLIP 模型为 lazy 加载（首次 compute 调用时加载），且每次只计算一对图片。
在批量匹配场景下存在以下性能瓶颈：

1. **首次延迟**：首次调用需下载/加载模型（~3-5 秒）
2. **单张计算**：每次只处理 1 对图片，无法利用 GPU 并行能力
3. **重复编码**：同一图片被多次 encode，浪费计算资源
4. **GPU 未利用**：transformers 后端未显式 `.to(device)`，默认在 CPU 运行

### 12.2 目标

| 优化项 | 目标 |
|--------|------|
| 预加载模型 | `__init__` 时主动加载，首次调用零延迟 |
| 批量计算 | `compute_batch()` 一次处理 N 对图片 |
| GPU 加速 | 自动检测 CUDA，`.to(device)` + `eval()` |
| Embedding 缓存 | 相同图片内容复用 embedding，避免重复编码 |
| 模型预热 | `warmup()` 方法用 dummy 输入预热推理管道 |

### 12.3 预加载机制

```python
computer = FrameSimilarityComputer(preload=True)  # 默认 True
# __init__ 立即加载 CLIP 模型
# 首次 compute() 调用零延迟

computer = FrameSimilarityComputer(preload=False)
# 保持 lazy 加载（兼容测试场景）
```

### 12.4 批量计算接口

```python
pairs = [
    ("http://thumb1.jpg", "/path/to/video1.mp4"),
    ("http://thumb2.jpg", "/path/to/video2.mp4"),
    ("http://thumb3.jpg", "/path/to/video3.mp4"),
]
results = computer.compute_batch(pairs)
# [(0.92, "clip", False), (0.85, "clip", True), (0.0, "none", False)]
```

批量计算优化策略：
- 收集所有有效图片对
- 统一加载到 GPU/CPU
- 单次 forward pass 批量编码
- 批量计算 cosine similarity

### 12.5 Embedding 缓存

基于图片内容（而非路径）的 embedding 缓存：

```
缓存键 = MD5(image_bytes)
缓存值 = embedding tensor (512-dim)
缓存上限 = 500 张图片 (LRU)
```

相同图片（即使路径不同）复用 embedding，避免重复编码。

### 12.6 GPU 加速

```python
device = "cuda" if torch.cuda.is_available() else "cpu"
model = CLIPModel.from_pretrained(...).to(device)
model.eval()

# 批量推理
with torch.no_grad():
    features = model.get_image_features(pixel_values=batch.to(device))
```

### 12.7 API 端点

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/creative-mapping/frame-similarity/batch` | 批量计算帧相似度 |

请求体:
```json
{
  "pairs": [
    {"thumbnail_source": "...", "eagle_path": "..."},
    {"thumbnail_source": "...", "eagle_path": "..."}
  ]
}
```

响应体:
```json
{
  "results": [
    {"score": 0.92, "method": "clip", "cached": false},
    {"score": 0.85, "method": "clip", "cached": true}
  ],
  "total": 2,
  "elapsed_seconds": 1.2
}
```

### 12.8 性能指标

| 场景 | v1.2 (单张) | v1.3 (优化后) |
|------|-------------|---------------|
| 首次调用 | 3-5s (加载模型) | 0s (预加载) |
| 单对计算 | 200-500ms | 200-500ms (不变) |
| 10 对批量 | 2-5s | 0.5-1s (批量编码) |
| 重复图片 | 200-500ms | 0ms (embedding 缓存) |

### 12.9 验收标准

- [x] 预加载：`preload=True` 时 `__init__` 完成模型加载
- [x] 批量计算：`compute_batch()` 返回与逐个 `compute()` 相同的结果
- [x] GPU 加速：CUDA 可用时模型自动 `.to("cuda")`
- [x] Embedding 缓存：相同图片内容命中缓存
- [x] 模型预热：`warmup()` 不抛出异常
- [x] 单元测试 ≥ 10 个 (30 个测试通过)
- [x] 全量回归测试无新增失败 (22887 passed)

---

## 十三、Facebook Creative Ingestion — 创意元数据拉取与自动映射

### 13.1 问题

Creative Mapping Engine 的 `match()` 方法期望输入包含 `duration` 和 `resolution` 字段（分别参与 `duration_match` 和 `resolution_match` 维度评分，权重 0.15 + 0.10 = 0.25）。但现有 Facebook 拉取代码存在以下缺口：

1. **duration 未拉取**：`FacebookClient.get_video()` 已定义（请求 `length,picture,source` 字段），但 `CreativeFetcher` 未调用它
2. **resolution 未拉取**：`get_video()` 的 fields 不含 `width,height`
3. **无 CME 集成**：拉取的创意数据未自动喂给 Mapping Engine 执行映射
4. **无统一入口**：CME 缺少从 Facebook API 拉取创意并自动映射的编排层

### 13.2 目标

在 `creative_mapping_engine` 模块内实现 `FacebookCreativeIngester`，提供：

- 从 Facebook Marketing API 拉取广告创意列表（复用现有 `FacebookClient`）
- 对视频类创意调用 `get_video()` 补全 `duration`（`length` 字段）和 `resolution`（`width x height`）
- 将拉取的创意数据转换为 `CreativeMappingEngine.match()` 的输入格式
- 自动触发映射，返回映射结果
- 支持 dry_run 模式（不调用真实 API，使用 mock 数据）
- 支持增量拉取（跳过已映射的 creative_id）
- API 端点触发拉取和映射

### 13.3 范围界定

| 在范围内 | 不在范围内 |
|---------|-----------|
| 拉取创意元数据（name, thumbnail_url, video_id, duration, resolution） | 下载视频文件（第九章排除） |
| 扩展 `get_video()` fields 包含 `width,height` | 修改 SafeExecutor（只读操作不经审批） |
| 新增 `FacebookCreativeEntity` 的 `duration`/`resolution` 字段 | 修改 `CreativeMappingEngine.match()` 核心逻辑 |
| 自动触发 CME 映射 | 拉取成效数据（spend/impressions，已有模块） |
| dry_run 模式用于测试 | 前端 UI |

### 13.4 数据流

```
输入: ad_account_id, lookback_days (可选)
  │
  ├── 1. FacebookClient.get_ads()
  │      └── 嵌套拉取 creative{id,name,thumbnail_url,video_id}
  │
  ├── 2. 对每个 VIDEO 类型 creative
  │      └── FacebookClient.get_video(video_id)
  │          └── 获取 length → duration
  │          └── 获取 width×height → resolution
  │
  ├── 3. 转换为 CME match() 输入格式
  │      {
  │          "facebook_creative_id": creative_id,
  │          "facebook_creative_name": name,
  │          "facebook_account_id": ad_account_id,
  │          "thumbnail_url": thumbnail_url,
  │          "duration": length,
  │          "resolution": "1080x1920",
  │          "creation_time": created_time
  │      }
  │
  ├── 4. 增量过滤：跳过已有 MATCHED/REVIEW_APPROVED 记录的 creative_id
  │
  ├── 5. 调用 CreativeMappingEngine.match() 逐条映射
  │
  └── 6. 返回映射结果汇总
```

### 13.5 FacebookClient 扩展

`get_video()` 方法的 fields 参数从 `id,title,description,length,picture,source` 扩展为 `id,title,description,length,picture,source,width,height`。

新增 `width` 和 `height` 字段从 Graph API `/{video_id}` 端点获取。

### 13.6 FacebookCreativeEntity 扩展

新增两个字段：

```python
@dataclass
class FacebookCreativeEntity:
    # ... 现有字段 ...
    duration: float = 0.0        # 视频时长（秒），IMAGE 类型为 0.0
    resolution: str = ""         # 分辨率 "WIDTHxHEIGHT"，IMAGE 类型为空
```

### 13.7 FacebookCreativeIngester 类

```python
class FacebookCreativeIngester:
    """从 Facebook API 拉取创意元数据并自动映射到 Eagle 素材。"""

    def __init__(
        self,
        engine: CreativeMappingEngine,
        facebook_client: FacebookClient | None = None,
        dry_run: bool = False,
    ): ...

    def ingest(
        self,
        ad_account_id: str = "",
        lookback_days: int = 7,
        auto_map: bool = True,
    ) -> IngestionResult:
        """拉取创意并自动映射。"""
        ...

    def ingest_creatives(
        self,
        creatives: list[dict],
        auto_map: bool = True,
    ) -> IngestionResult:
        """直接使用提供的创意数据（跳过 API 调用，用于测试/dry_run）。"""
        ...

    def _fetch_and_enrich(
        self,
        ad_account_id: str,
        lookback_days: int,
    ) -> list[dict]:
        """拉取创意并补全 duration/resolution。"""
        ...

    def _enrich_video_metadata(
        self,
        creative: dict,
    ) -> dict:
        """对视频类创意调用 get_video() 补全 duration/resolution。"""
        ...
```

### 13.8 IngestionResult 数据结构

```python
@dataclass
class IngestionResult:
    """拉取与映射结果汇总。"""
    total_fetched: int           # 拉取的创意总数
    total_mapped: int            # 触发映射的创意数
    total_skipped: int           # 跳过的创意数（已有映射记录）
    total_errors: int            # 错误数
    mappings: list[dict]         # 映射结果列表（CreativeMappingRecord.to_dict()）
    elapsed_seconds: float       # 总耗时
    dry_run: bool                # 是否为 dry_run 模式
```

### 13.9 增量策略

| 条件 | 行为 |
|------|------|
| creative_id 已有 MATCHED 记录 | 跳过，计入 `total_skipped` |
| creative_id 已有 REVIEW_APPROVED 记录 | 跳过，计入 `total_skipped` |
| creative_id 有 NEEDS_REVIEW/NO_MATCH/PENDING 记录 | 重新映射（可能 Eagle 索引已更新） |
| creative_id 无记录 | 新映射 |

### 13.10 dry_run 模式

dry_run=True 时不调用真实 Facebook API，使用调用方提供的 mock 创意数据（通过 `ingest_creatives()` 方法）。用于测试和演示。

### 13.11 API 端点

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/creative-mapping/facebook/ingest` | 拉取 Facebook 创意并自动映射 |
| POST | `/api/creative-mapping/facebook/ingest-dry-run` | dry_run 模式（使用提供的创意数据） |

#### 请求体 (ingest)

```json
{
  "ad_account_id": "act_123456",
  "lookback_days": 7,
  "auto_map": true
}
```

#### 请求体 (ingest-dry-run)

```json
{
  "creatives": [
    {
      "facebook_creative_id": "536123456789",
      "facebook_creative_name": "MW_VIDEO_260721_000123",
      "thumbnail_url": "https://...",
      "video_id": "123456",
      "duration": 32.5,
      "resolution": "1080x1920",
      "creation_time": "2026-07-24"
    }
  ],
  "auto_map": true
}
```

#### 响应体

```json
{
  "total_fetched": 10,
  "total_mapped": 8,
  "total_skipped": 2,
  "total_errors": 0,
  "mappings": [
    {
      "mapping_id": "fb_536123456789_a1b2c3",
      "facebook_creative_id": "536123456789",
      "status": "matched",
      "confidence": 0.92,
      "match_method": "name_similarity",
      "eagle_filename": "MW_VIDEO_260721_000123.mp4"
    }
  ],
  "elapsed_seconds": 5.3,
  "dry_run": false
}
```

### 13.12 错误处理

| 错误场景 | 行为 |
|---------|------|
| Facebook API 不可达 | 返回 `total_fetched=0, total_errors=1`，记录 error 日志 |
| `get_video()` 失败 | duration=0.0, resolution=""，继续映射（降级为 2 维缺失） |
| `match()` 抛出异常 | 计入 `total_errors`，继续处理下一条 |
| Eagle 索引未加载 | 返回所有 creative 为 NO_MATCH |

### 13.13 模块结构更新

```
src/market_ops/creative_mapping_engine/
  ├── __init__.py
  ├── engine.py              # CreativeMappingEngine 核心编排
  ├── scorers.py             # 6 维度评分器
  ├── review_queue.py        # 人工审核队列管理
  ├── store.py               # 持久化层
  ├── scanner.py             # EagleScanner 素材库扫描器 (v1.1)
  ├── frame_similarity.py    # FrameSimilarityComputer (v1.2)
  ├── facebook_ingester.py   # FacebookCreativeIngester (v1.4 新增)
  └── models.py              # 数据模型
```

### 13.14 验收标准

- [x] `FacebookClient.get_video()` fields 包含 `width,height`
- [x] `FacebookCreativeEntity` 新增 `duration` 和 `resolution` 字段
- [x] `FacebookCreativeIngester.ingest()` 拉取创意并自动映射
- [x] `FacebookCreativeIngester.ingest_creatives()` 支持 dry_run 模式
- [x] 增量策略：跳过已有 MATCHED/REVIEW_APPROVED 的 creative_id
- [x] duration/resolution 补全：VIDEO 类型调用 `get_video()` 获取
- [x] 错误处理：API 失败不中断，降级处理
- [x] API 端点：2 个端点（ingest + ingest-dry-run）
- [x] 单元测试 ≥ 20 个 (38 个测试通过)
- [x] 全量回归测试无新增失败 (全量 exit code 0)

---

## 十四、Delivery Bridge — 映射记录到广告投放的交付桥接层 (v1.5)

### 14.1 问题

v1.1–v1.4 完成了 **映射侧闭环**（Eagle 扫描 → Facebook 拉取 → 6 维匹配 → 人工审核 → 持久化），
但映射记录中的 `eagle_path` / `eagle_filename` 字段 **没有任何下游广告投放流程消费**：

1. **数据流断开**：CME 的 `records.jsonl` 与广告投放系统之间无桥接，映射完成后无人读取
2. **投放系统独立**：现有 3 个 Publisher（`facebook_publisher.py`、`14_publish/facebook_publisher.py`、
   `ad_publishing_layer.py`）均接收手动指定的 `image_paths`，完全不查询 CME
3. **creative_id 概念错位**：CME 的 `facebook_creative_id` 是 Facebook 已存在 creative 的 ID
   （拉取自 `get_ads()`），Publisher 需要的是本地素材文件路径 → 上传后生成新的 `image_hash` / `video_id`
4. **无投递状态追踪**：映射记录无 `delivery_status` 字段，无法区分"已匹配待投递"与"已投递上线"
5. **无投递 API**：`workspace/app.py` 中 0 个 `/api/creative-mapping/deliver*` 端点

### 14.2 目标

在 CME 和现有 Publisher 之间新增 **DeliveryBridge** 交付桥接层，实现：

- 从 CME 查询 `status=MATCHED` 或 `REVIEW_APPROVED` 且 `delivery_status=UNDISPATCHED` 的记录
- 将映射记录的 `eagle_path` 解析为 Publisher 可用的素材路径
- 调用 `AdPublishingLayer.publish_to_meta()` 执行真实投递（dry_run 默认）
- 将投递结果（`publish_id` / `ad_id` / `ad_creative_id`）回写到 `CreativeMappingRecord`
- 更新 `delivery_status`，支持失败重试
- 暴露 5 个 HTTP API 端点供 Agent / 人工触发

**非目标**（v1.5 明确排除）：

- ❌ 投放结构自动创建（Campaign/AdSet 生成 → v1.6）
- ❌ 投放成效回流（impressions/clicks/CTR 回写 → v1.7）
- ❌ 基于成效的素材排序优化（→ v1.8）
- ❌ 修改现有 Publisher 的核心投递逻辑（仅新增桥接调用）

### 14.3 数据模型扩展

#### 14.3.1 新增 `MappingDeliveryStatus` 枚举

```python
class MappingDeliveryStatus(str, Enum):
    """映射记录的投递状态（与 MappingStatus 正交：前者描述"映射是否完成"，
    后者描述"是否已推送到投放系统"）。"""
    UNDISPATCHED = "undispatched"   # 未投递（默认）
    DISPATCHED = "dispatched"       # 已投递到 Publisher，等待 Facebook 确认
    PUBLISHED = "published"         # 已上线（拿到 ad_id）
    FAILED = "failed"               # 投递失败（见 delivery_error）
    ARCHIVED = "archived"           # 已归档（不再投递）
```

**设计决策**：`delivery_status` 与 `MappingStatus` 正交。一条记录可以是 `MATCHED`（映射完成）
+ `UNDISPATCHED`（未投递），也可以是 `REVIEW_APPROVED` + `PUBLISHED`（审核通过且已上线）。
两个字段独立演化，避免状态机爆炸。

#### 14.3.2 `CreativeMappingRecord` 字段扩展

在现有字段（§2.1）基础上新增以下字段：

```python
@dataclass
class CreativeMappingRecord:
    # ... 现有字段保持不变 ...

    # ── v1.5 Delivery Bridge 新增字段 ──
    delivery_status: MappingDeliveryStatus = MappingDeliveryStatus.UNDISPATCHED
    publish_id: str = ""              # 关联 AdPublishRecord.publish_id
    ad_id: str = ""                   # Facebook ad_id（投递成功后回填）
    ad_creative_id: str = ""          # Facebook ad_creative_id（投递后回填）
    delivered_at: str = ""            # 投递时间 (ISO 8601)
    delivery_error: str = ""          # 失败原因（FAILED 时填充）
    delivery_attempts: int = 0        # 投递尝试次数（失败重试递增）
```

**向后兼容**：现有 `records.jsonl` 中无这些字段的记录，加载时默认为 `UNDISPATCHED` / 空字符串 / 0。
`from_dict()` 使用 `field(default=...)` 自动填充缺失字段。

### 14.4 模块结构

```
src/market_ops/creative_mapping_engine/
  ├── __init__.py
  ├── engine.py              # CreativeMappingEngine 核心编排
  ├── scorers.py             # 6 维度评分器
  ├── review_queue.py        # 人工审核队列管理
  ├── store.py               # 持久化层 (v1.5: 新增 update_delivery_status)
  ├── scanner.py             # EagleScanner 素材库扫描器 (v1.1)
  ├── frame_similarity.py    # FrameSimilarityComputer (v1.2)
  ├── facebook_ingester.py   # FacebookCreativeIngester (v1.4)
  ├── delivery_bridge.py     # DeliveryBridge 交付桥接层 (v1.5 新增)
  └── models.py              # 数据模型 (v1.5: 扩展 MappingDeliveryStatus + 字段)
```

### 14.5 DeliveryBridge 类设计

```python
class DeliveryBridge:
    """映射记录 → 广告投放系统的交付桥接层。

    职责：
      1. 查询可投递记录（MATCHED/REVIEW_APPROVED + UNDISPATCHED）
      2. 解析 eagle_path → Publisher 可用的素材路径
      3. 调用 AdPublishingLayer.publish_to_meta() 执行投递
      4. 回写 publish_id / ad_id / ad_creative_id 到映射记录
      5. 更新 delivery_status，支持失败重试

    安全规则（对齐 p4_contract.md）：
      - 默认 dry_run=True
      - 生产模式必须显式 dry_run=False + 通过 approval gate
      - 单次批量投递上限 MAX_DELIVERIES_PER_RUN=5
      - 连续 3 次失败触发 circuit breaker 暂停
    """

    MAX_DELIVERIES_PER_RUN = 5
    CIRCUIT_BREAKER_THRESHOLD = 3

    def __init__(
        self,
        engine: CreativeMappingEngine,
        publishing_layer: Optional[AdPublishingLayer] = None,
        data_dir: Optional[str] = None,
    ): ...

    # ── 查询 ──

    def get_dispatchable(self, limit: int = 50) -> list[CreativeMappingRecord]:
        """查询可投递记录（MATCHED/REVIEW_APPROVED + UNDISPATCHED）。

        Args:
            limit: 最多返回记录数（默认 50，上限 MAX_DELIVERIES_PER_RUN * 10）

        Returns:
            按 confidence 降序排列的可投递记录列表
        """
        ...

    def get_delivery_status(self, mapping_id: str) -> dict:
        """查询单条记录的投递状态。"""
        ...

    # ── 投递 ──

    def dispatch(
        self,
        mapping_id: str,
        ad_account_id: str,
        campaign_id: str,
        adset_id: str,
        page_id: str,
        dry_run: bool = True,
        creative_name: str = "",
        creative_body: str = "",
    ) -> DeliveryResult:
        """单条投递：将映射记录的素材投递到 Facebook Ads。

        Args:
            mapping_id: 映射记录 ID
            ad_account_id: Facebook 广告账户 ID
            campaign_id: 目标 Campaign ID
            adset_id: 目标 AdSet ID
            page_id: Facebook Page ID（adcreative 必需）
            dry_run: True=模拟投递不调用真实 API（默认）
            creative_name: adcreative 标题（空则用 facebook_creative_name）
            creative_body: adcreative 正文

        Returns:
            DeliveryResult{success, mapping_id, publish_id, ad_id, ad_creative_id,
                          delivery_status, error, elapsed_ms}

        投递流程：
          1. 加载映射记录，校验 status ∈ {MATCHED, REVIEW_APPROVED}
          2. 校验 delivery_status == UNDISPATCHED 或 FAILED（允许重试）
          3. 解析素材路径：eagle_path → 绝对路径，校验文件存在
          4. 调用 AdPublishingLayer.publish_to_meta(publish_id, image_path, ...)
          5. 回写 publish_id / ad_id / ad_creative_id / delivery_status
          6. delivery_attempts += 1
        """
        ...

    def dispatch_batch(
        self,
        ad_account_id: str,
        campaign_id: str,
        adset_id: str,
        page_id: str,
        filter_status: list[MappingStatus] | None = None,
        limit: int = MAX_DELIVERIES_PER_RUN,
        dry_run: bool = True,
    ) -> BatchDeliveryResult:
        """批量投递：自动选取可投递记录批量推送。

        Args:
            filter_status: 筛选 MappingStatus（默认 [MATCHED, REVIEW_APPROVED]）
            limit: 单次批量上限（强制 ≤ MAX_DELIVERIES_PER_RUN）
            dry_run: True=模拟投递（默认）

        Returns:
            BatchDeliveryResult{total, success_count, failed_count, skipped_count,
                               results: list[DeliveryResult], circuit_breaker_triggered}

        安全规则：
          - limit 强制 ≤ MAX_DELIVERIES_PER_RUN
          - 连续 CIRCUIT_BREAKER_THRESHOLD 次失败 → 停止后续投递
          - circuit_breaker_triggered=True 时返回剩余未投递记录数
        """
        ...

    def redeliver(
        self,
        mapping_id: str,
        ad_account_id: str,
        campaign_id: str,
        adset_id: str,
        page_id: str,
        dry_run: bool = True,
    ) -> DeliveryResult:
        """重试失败的投递（delivery_status=FAILED）。

        约束：
          - 仅 delivery_status=FAILED 的记录可重试
          - delivery_attempts < 5（超过 5 次需人工介入）
          - 重置 delivery_error，重新投递
        """
        ...
```

#### 14.5.1 `DeliveryResult` / `BatchDeliveryResult` 数据结构

```python
@dataclass
class DeliveryResult:
    """单条投递结果。"""
    success: bool
    mapping_id: str
    publish_id: str = ""           # AdPublishRecord.publish_id
    ad_id: str = ""                # Facebook ad_id（PUBLISHED 时填充）
    ad_creative_id: str = ""       # Facebook ad_creative_id
    delivery_status: MappingDeliveryStatus = MappingDeliveryStatus.UNDISPATCHED
    error: str = ""
    elapsed_ms: float = 0.0


@dataclass
class BatchDeliveryResult:
    """批量投递结果。"""
    total: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0         # 状态不符/路径缺失等跳过
    results: list[DeliveryResult] = field(default_factory=list)
    circuit_breaker_triggered: bool = False
    elapsed_ms: float = 0.0
```

### 14.6 Store 层扩展

`MappingStore` 新增方法：

```python
class MappingStore:
    # ... 现有方法保持不变 ...

    def update_delivery_status(
        self,
        mapping_id: str,
        delivery_status: MappingDeliveryStatus,
        publish_id: str = "",
        ad_id: str = "",
        ad_creative_id: str = "",
        delivery_error: str = "",
        increment_attempts: bool = False,
    ) -> bool:
        """更新映射记录的投递状态（append-only 新行）。

        Args:
            mapping_id: 映射记录 ID
            delivery_status: 新投递状态
            publish_id: AdPublishRecord.publish_id（DISPATCHED 时填充）
            ad_id: Facebook ad_id（PUBLISHED 时填充）
            ad_creative_id: Facebook ad_creative_id
            delivery_error: 失败原因（FAILED 时填充）
            increment_attempts: True 则 delivery_attempts += 1

        Returns:
            True=更新成功，False=记录不存在

        实现：加载现有记录 → 更新字段 → 追加新行到 records.jsonl（append-only 语义）
        """
        ...
```

### 14.7 与现有系统的集成契约

#### 14.7.1 与 `AdPublishingLayer` 的集成

```python
# creative_growth_loop/11_production_bridge/ad_publishing_layer.py
class AdPublishingLayer:
    # ... 现有方法保持不变 ...

    def publish_to_meta(
        self,
        publish_id: str,
        image_path: str,          # ← DeliveryBridge 传入 eagle_path 解析后的路径
        campaign_id: str,
        adset_id: str,
        page_id: str,
        creative_name: str = "",
        creative_body: str = "",
        dry_run: bool = True,
    ) -> dict:
        """现有方法签名不变，DeliveryBridge 直接调用。

        返回格式（现有契约）：
            {"success": True, "publish_id": ..., "ad_ids": [...], "image_hash": ...}
            或 {"success": False, "error": "..."}
        """
        ...
```

**集成方式**：DeliveryBridge 不修改 `AdPublishingLayer`，仅作为调用方。
`eagle_path` 字段直接作为 `image_path` 参数传入（AdPublishingLayer 已支持任意文件路径）。

#### 14.7.2 与 `CreativeMappingEngine` 的集成

```python
class CreativeMappingEngine:
    # ... 现有方法保持不变 ...

    def get_dispatchable_records(
        self,
        limit: int = 50,
        filter_status: list[MappingStatus] | None = None,
    ) -> list[CreativeMappingRecord]:
        """v1.5 新增：查询可投递记录。

        筛选条件：
          - status ∈ {MATCHED, REVIEW_APPROVED}（或自定义 filter_status）
          - delivery_status ∈ {UNDISPATCHED, FAILED}
          - eagle_path 非空且文件存在

        排序：按 confidence 降序
        """
        ...
```

#### 14.7.3 不修改的部分

- `AdPublishingLayer` 核心投递逻辑保持不变
- `FacebookPublisher`（3 个实现）保持不变
- 现有 CME 匹配/审核流程保持不变
- 现有 17 个 CME API 端点签名保持不变

### 14.8 API 端点

在 `workspace/app.py` 新增 5 个端点：

| 方法 | 路径 | 功能 | 请求体/参数 |
|------|------|------|------------|
| POST | `/api/creative-mapping/deliver` | 单条投递 | `body: {mapping_id, ad_account_id, campaign_id, adset_id, page_id, dry_run?, creative_name?, creative_body?}` |
| POST | `/api/creative-mapping/deliver-batch` | 批量投递 | `body: {ad_account_id, campaign_id, adset_id, page_id, filter_status?, limit?, dry_run?}` |
| GET | `/api/creative-mapping/deliverable` | 查询可投递记录 | `query: limit?, filter_status?` |
| GET | `/api/creative-mapping/delivery/{mapping_id}` | 查询投递状态 | path param |
| POST | `/api/creative-mapping/delivery/{mapping_id}/retry` | 重试失败投递 | `body: {ad_account_id, campaign_id, adset_id, page_id, dry_run?}` |

#### 14.8.1 响应格式

**单条投递响应** (`POST /api/creative-mapping/deliver`):

```json
{
  "success": true,
  "mapping_id": "map_abc123",
  "publish_id": "pub_xyz",
  "ad_id": "123456789",
  "ad_creative_id": "987654321",
  "delivery_status": "published",
  "error": "",
  "elapsed_ms": 1234.5
}
```

**批量投递响应** (`POST /api/creative-mapping/deliver-batch`):

```json
{
  "total": 5,
  "success_count": 4,
  "failed_count": 1,
  "skipped_count": 0,
  "results": [DeliveryResult, ...],
  "circuit_breaker_triggered": false,
  "elapsed_ms": 5678.9
}
```

**可投递记录查询响应** (`GET /api/creative-mapping/deliverable`):

```json
{
  "records": [CreativeMappingRecord.to_dict(), ...],
  "count": 12
}
```

### 14.9 安全规则（对齐 p4_contract.md）

| 规则 | 说明 |
|------|------|
| **dry_run 默认** | `dispatch()` / `dispatch_batch()` / `redeliver()` 默认 `dry_run=True` |
| **显式生产模式** | `dry_run=False` 必须显式传入，API 请求体必须包含 `"dry_run": false` |
| **单次上限** | `MAX_DELIVERIES_PER_RUN=5`，`dispatch_batch()` 的 `limit` 强制截断 |
| **Circuit Breaker** | 连续 `CIRCUIT_BREAKER_THRESHOLD=3` 次失败 → 停止批量投递，`circuit_breaker_triggered=True` |
| **重试上限** | `delivery_attempts >= 5` 时 `redeliver()` 拒绝执行（需人工介入） |
| **状态校验** | 仅 `MATCHED` / `REVIEW_APPROVED` + `UNDISPATCHED` / `FAILED` 可投递 |
| **文件校验** | `eagle_path` 必须非空且文件存在，否则跳过并记录 `skipped_count` |
| **审计日志** | 每次投递（含 dry_run）写入 `data/creative_mapping/delivery_audit.jsonl` |

#### 14.9.1 投递审计日志格式

```json
{
  "timestamp": "2026-08-10T15:30:00",
  "mapping_id": "map_abc123",
  "action": "dispatch",
  "dry_run": false,
  "ad_account_id": "act_123",
  "campaign_id": "cmp_456",
  "adset_id": "set_789",
  "success": true,
  "publish_id": "pub_xyz",
  "ad_id": "123456789",
  "elapsed_ms": 1234.5,
  "error": ""
}
```

### 14.10 投放参数补充策略

CME 映射记录只含素材信息，不含投放参数（campaign_id / adset_id / page_id）。
v1.5 采用 **方案 A：调用方提供**：

- 投递 API 请求体中显式传入 `ad_account_id` / `campaign_id` / `adset_id` / `page_id`
- DeliveryBridge 仅负责"素材路径 → Publisher"桥接，不创建投放结构
- 适合"已有投放结构、补充新素材"场景

**未来演进**（见第十五章）：

- v1.6：集成 `CampaignStrategyBuilder` 自动创建 Campaign/AdSet（方案 B）
- v1.7：扩展映射记录增加 `target_campaign_id` 字段（方案 C）

### 14.11 错误处理

| 错误场景 | 处理方式 | delivery_status |
|---------|---------|----------------|
| 映射记录不存在 | 返回 `success=False, error="mapping not found"` | 不变 |
| status 不符合（PENDING/NO_MATCH 等） | 返回 `success=False, error="invalid status"` | 不变 |
| delivery_status=PUBLISHED（重复投递） | 返回 `success=False, error="already published"` | 不变 |
| eagle_path 为空 | 返回 `success=False, error="no eagle_path"` | 不变 |
| 文件不存在 | 返回 `success=False, error="file not found"` | 不变 |
| Publisher 调用失败 | 回写 `delivery_status=FAILED, delivery_error=...` | FAILED |
| Publisher 返回 ad_id | 回写 `delivery_status=PUBLISHED, ad_id=...` | PUBLISHED |
| dry_run=True | 不调用 Publisher，返回模拟成功 | 不变（仍 UNDISPATCHED） |

### 14.12 验收标准

- [ ] `MappingDeliveryStatus` 枚举定义（5 个状态）
- [ ] `CreativeMappingRecord` 新增 6 个字段，向后兼容旧记录
- [ ] `MappingStore.update_delivery_status()` 方法实现（append-only）
- [ ] `CreativeMappingEngine.get_dispatchable_records()` 方法实现
- [ ] `DeliveryBridge` 类实现（`dispatch` / `dispatch_batch` / `redeliver` / `get_dispatchable` / `get_delivery_status`）
- [ ] Circuit breaker 逻辑（连续 3 次失败停止）
- [ ] 重试上限校验（`delivery_attempts >= 5` 拒绝重试）
- [ ] 投递审计日志（`data/creative_mapping/delivery_audit.jsonl`）
- [ ] 5 个 API 端点（deliver / deliver-batch / deliverable / delivery/{id} / delivery/{id}/retry）
- [ ] dry_run 默认 True，生产模式需显式 `dry_run=False`
- [ ] 单元测试 ≥ 30 个（覆盖所有状态转换、错误场景、circuit breaker、重试上限）
- [ ] 全量回归测试无新增失败

### 14.13 测试覆盖要求

| 测试类别 | 覆盖场景 |
|---------|---------|
| **状态转换** | UNDISPATCHED→DISPATCHED→PUBLISHED / UNDISPATCHED→FAILED / FAILED→PUBLISHED（重试） |
| **查询** | get_dispatchable 筛选 status + delivery_status + eagle_path 存在性 |
| **单条投递** | 成功 / dry_run / 记录不存在 / status 不符 / 重复投递 / 路径缺失 / 文件不存在 |
| **批量投递** | 成功 / limit 截断 / 混合成功失败 / circuit breaker 触发 |
| **重试** | 成功重试 / delivery_attempts >= 5 拒绝 / 非 FAILED 状态拒绝 |
| **回写** | publish_id / ad_id / ad_creative_id 正确回写到 records.jsonl |
| **审计日志** | 每次投递（含 dry_run）写入 delivery_audit.jsonl |
| **API** | 5 个端点的成功/失败响应格式 |
| **安全** | dry_run 默认 / MAX_DELIVERIES_PER_RUN 截断 / circuit breaker |

---

## 十五、v1.6 投放结构自动创建 (Campaign/AdSet Auto-Creation)

### 15.1 问题

v1.5 DeliveryBridge 采用"方案 A：调用方提供投放参数"，要求 API 请求体显式传入
`campaign_id` / `adset_id` / `page_id`。这限制了"全新投放"场景：当没有现有
Campaign/AdSet 时，需要人工先在 Facebook Ads Manager 创建结构，再手动填入 ID。

### 15.2 目标

集成 `CampaignStrategyBuilder`（`14_publish/campaign_strategy.py`），支持"无现有
campaign"场景下的端到端投递：

- DeliveryBridge 新增 `dispatch_with_auto_structure()` 方法
- 自动创建 Campaign（ABO/CBO/ASC 策略自动选择）→ AdSet（Targeting + Budget + Bid）
- 投放参数从 `CampaignStrategyBuilder.build_full_campaign()` 生成
- 新增 API 端点 `POST /api/creative-mapping/deliver-auto`

**非目标**：
- 不修改 `CampaignStrategyBuilder` 核心策略逻辑
- 不实现基于成效的投放结构优化（→ v1.8）

### 15.3 数据模型

#### 15.3.1 `CreativeMappingRecord` 扩展

新增字段记录自动创建的投放结构：

```python
# ── v1.6 Auto-Structure 新增字段 ──
auto_campaign_id: str = ""       # 自动创建的 Campaign ID
auto_adset_id: str = ""          # 自动创建的 AdSet ID
auto_strategy: str = ""          # 使用的策略 (ABO/CBO/ASC)
```

#### 15.3.2 `AutoStructureResult` 数据结构

```python
@dataclass
class AutoStructureResult:
    """自动创建投放结构的结果。"""
    success: bool
    campaign_id: str = ""
    adset_id: str = ""
    strategy: str = ""            # ABO / CBO / ASC
    error: str = ""
    delivery_result: Optional[DeliveryResult] = None
```

### 15.4 DeliveryBridge 扩展

```python
class DeliveryBridge:
    # ... v1.5 方法保持不变 ...

    def dispatch_with_auto_structure(
        self,
        mapping_id: str,
        ad_account_id: str,
        page_id: str,
        project_name: str,
        daily_budget: float,
        countries: list[str],
        game_category: str = "casual",
        adset_count: int = 1,
        is_broad: bool = False,
        target_cpi: Optional[float] = None,
        use_advantage_plus: bool = False,
        dry_run: bool = True,
        access_token: str = "",
        headlines: Optional[list[str]] = None,
        primary_texts: Optional[list[str]] = None,
    ) -> AutoStructureResult:
        """自动创建投放结构并投递 (v1.6)。

        流程:
          1. CampaignStrategyBuilder.build_full_campaign() 生成配置
          2. (dry_run=False) FacebookPublisher 创建 Campaign + AdSet
          3. 回写 auto_campaign_id / auto_adset_id 到映射记录
          4. 调用 dispatch() 用新创建的 campaign_id/adset_id 投递

        Args:
            mapping_id: 映射记录 ID
            ad_account_id: Facebook 广告账户 ID
            page_id: Facebook Page ID
            project_name: 项目名 (用于 Campaign/AdSet 命名)
            daily_budget: 日预算 (USD)
            countries: 投放国家列表
            game_category: 游戏类别 (casual/hardcore/midcore)
            adset_count: AdSet 数量
            is_broad: 是否宽泛定向
            target_cpi: 目标 CPI
            use_advantage_plus: 是否使用 ASC (Advantage+ Shopping)
            dry_run: True=模拟 (默认)
            access_token: Facebook API token
            headlines: 广告标题列表
            primary_texts: 广告正文列表

        Returns:
            AutoStructureResult
        """
        ...
```

### 15.5 API 端点

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/creative-mapping/deliver-auto` | 自动创建投放结构并投递 |

请求体:
```json
{
  "mapping_id": "map_xxx",
  "ad_account_id": "act_123",
  "page_id": "page_001",
  "project_name": "MyGame",
  "daily_budget": 50.0,
  "countries": ["US", "CA"],
  "game_category": "casual",
  "adset_count": 2,
  "dry_run": true
}
```

### 15.6 验收标准

- [ ] `AutoStructureResult` 数据结构定义
- [ ] `CreativeMappingRecord` 新增 3 个 auto-structure 字段
- [ ] `DeliveryBridge.dispatch_with_auto_structure()` 方法实现
- [ ] 集成 `CampaignStrategyBuilder.build_full_campaign()`
- [ ] dry_run 模式：生成配置但不创建真实 Campaign/AdSet
- [ ] 真实模式：创建 Campaign + AdSet → 回写 ID → dispatch()
- [ ] API 端点 `POST /api/creative-mapping/deliver-auto`
- [ ] 单元测试 ≥ 15 个
- [ ] 全量回归无新增失败

---

## 十六、v1.7 成效反馈环 (Performance Feedback Loop)

### 16.1 问题

v1.5/v1.6 完成了"正向投递"（映射记录 → Facebook Ad），但投递后的 `ad_id` 未与
Facebook insights 关联，无法形成双向闭环。`FacebookClient.get_insights()` /
`get_creative_insights()` 方法存在但无人调用。

### 16.2 目标

投递完成后，通过 `FacebookClient.get_creative_insights()` 拉取成效数据，回写到
`CreativeMappingRecord`，形成真正的双向闭环。

### 16.3 数据模型扩展

#### 16.3.1 `CreativePerformance` 新模型

```python
@dataclass
class CreativePerformance:
    """创意投放成效数据。"""
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    cpc: float = 0.0
    cpm: float = 0.0
    installs: int = 0
    last_synced_at: str = ""

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> CreativePerformance: ...
```

#### 16.3.2 `CreativeMappingRecord` 扩展

```python
# ── v1.7 Performance 新增字段 ──
performance: Optional[CreativePerformance] = None
```

### 16.4 FacebookInsightsIngester 模块

新增 `src/market_ops/creative_mapping_engine/insights_ingester.py`:

```python
class FacebookInsightsIngester:
    """拉取 Facebook insights 并回写到 CreativeMappingRecord。"""

    def __init__(
        self,
        engine: CreativeMappingEngine,
        facebook_client: Optional[FacebookClient] = None,
        data_dir: Optional[str] = None,
    ): ...

    def ingest_insights(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        dry_run: bool = True,
    ) -> InsightsIngestionResult:
        """拉取 insights 并回写。

        流程:
          1. 查询所有 delivery_status=PUBLISHED 且有 ad_id 的记录
          2. 调用 FacebookClient.get_creative_insights(start, end)
          3. 按 creative_id 匹配映射记录
          4. 解析 actions 数组提取 installs
          5. 更新 CreativeMappingRecord.performance
          6. 持久化到 records.jsonl
        """
        ...

    def get_performance(self, mapping_id: str) -> dict:
        """查询单条记录的成效数据。"""
        ...
```

### 16.5 API 端点

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/creative-mapping/insights/ingest` | 拉取并回写 insights |
| GET | `/api/creative-mapping/performance/{mapping_id}` | 查询成效 |
| GET | `/api/creative-mapping/performance` | 批量查询成效 (top N) |

### 16.6 验收标准

- [ ] `CreativePerformance` 数据模型
- [ ] `CreativeMappingRecord.performance` 字段
- [ ] `FacebookInsightsIngester` 类实现
- [ ] actions 数组解析 (app_install / mobile_app_install)
- [ ] 3 个 API 端点
- [ ] dry_run 模式
- [ ] 单元测试 ≥ 20 个
- [ ] 全量回归无新增失败

---

## 十七、v1.8 投放策略优化 (Delivery Strategy Optimization)

### 17.1 目标

基于历史 performance 自动选择投放素材（mapping confidence + performance 联合排序），
自动暂停低效素材。

### 17.2 数据模型扩展

```python
# ── v1.8 Strategy 新增字段 ──
performance_score: float = 0.0    # 归一化的成效得分 [0, 1]
delivery_priority: float = 0.0    # 联合排序优先级 (confidence * 0.4 + perf * 0.6)
auto_archived: bool = False       # 是否被自动归档
auto_archived_reason: str = ""    # 归档原因
```

### 17.3 DeliveryStrategyOptimizer 模块

新增 `src/market_ops/creative_mapping_engine/strategy_optimizer.py`:

```python
class DeliveryStrategyOptimizer:
    """基于成效的投放策略优化器。"""

    CTR_PAUSE_THRESHOLD = 0.005      # CTR < 0.5% 自动暂停
    CPI_PAUSE_THRESHOLD = 50.0       # CPI > $50 自动暂停
    MIN_DATA_POINTS = 1000           # 最少 impressions 才评估

    def compute_performance_score(self, perf: CreativePerformance) -> float:
        """计算归一化成效得分 [0, 1]。"""
        ...

    def compute_priority(self, record: CreativeMappingRecord) -> float:
        """联合排序: confidence * 0.4 + performance_score * 0.6"""
        ...

    def evaluate_and_archive(
        self, dry_run: bool = True
    ) -> ArchiveResult:
        """评估所有 PUBLISHED 记录，自动归档低效素材。"""
        ...

    def rank_dispatchable(
        self, limit: int = 50
    ) -> list[CreativeMappingRecord]:
        """按 delivery_priority 降序返回待投递记录。"""
        ...
```

### 17.4 API 端点

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/creative-mapping/strategy/evaluate` | 评估并自动归档低效素材 |
| GET | `/api/creative-mapping/strategy/ranking` | 查询素材优先级排名 |

### 17.5 验收标准

- [ ] `CreativeMappingRecord` 新增 4 个 strategy 字段
- [ ] `DeliveryStrategyOptimizer` 类实现
- [ ] `compute_performance_score()` 归一化算法
- [ ] `compute_priority()` 联合排序
- [ ] `evaluate_and_archive()` 自动归档 (CTR/CPI 阈值)
- [ ] `rank_dispatchable()` 优先级排名
- [ ] 2 个 API 端点
- [ ] 单元测试 ≥ 15 个
- [ ] 全量回归无新增失败
