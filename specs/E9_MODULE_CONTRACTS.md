# AI Creative Growth OS v1.0 — Module Contracts

**Version**: 1.0  
**Date**: 2026-07-20  
**Status**: FROZEN  
**Depends on**: [E9_ARCHITECTURE_V1.md](./E9_ARCHITECTURE_V1.md)

---

# 1. 契约总则

## 1.1 契约等级

| 等级 | 含义 | 变更规则 |
|------|------|---------|
| **FROZEN** | 不可修改 | 只能新增可选字段，不能删除/重命名/改类型 |
| **STABLE** | 可扩展 | 可新增方法/字段，不能破坏现有签名 |
| **INTERNAL** | 内部实现 | 可自由修改，但需同步更新测试 |

## 1.2 命名规范

- 公有 API：`snake_case`，动词开头（`extract_all`, `classify_all`, `load_predictions`）
- 数据类：`PascalCase`，名字体现职责（`DNAFeatureVector`, `PredictionRecord`）
- 内部方法：`_` 前缀（`_compute_distribution`, `_group_errors_by_feature`）

---

# 2. Player Intelligence（E9.5）

## 2.1 PlayerDNAEngine

**等级**: STABLE  
**位置**: `player_intelligence/player_dna_engine.py`

### 契约

```python
class PlayerDNAEngine:
    def extract_all(events: list[PlayerEvent]) -> dict[str, PlayerDNA]:
        """Extract PlayerDNA for all players from events.
        
        Input:  [PlayerEvent, ...]  — raw player events
        Output: {player_id: PlayerDNA}  — per-player DNA profile
        """
```

### 输入约束

```python
class PlayerEvent:
    player_id: str       # 必填，唯一标识
    creative_id: str     # 必填，广告来源
    event_type: str      # 必填，事件类型
    timestamp: str       # 必填，ISO 格式
    event_data: dict     # 可选，事件附加数据
```

### 输出约束

```python
class PlayerDNA:
    player_id: str
    creative_id: str
    progression_dna: ProgressionDNA
    collection_dna: CollectionDNA
    payment_dna: PaymentDNA
    retention_dna: RetentionDNA
```

## 2.2 BehaviorFeatureEngine

**等级**: STABLE  
**位置**: `player_intelligence/behavior_feature_engine.py`

### 契约

```python
class BehaviorFeatureEngine:
    def extract_all(
        dna_map: dict[str, PlayerDNA],
        events_by_player: dict[str, list[PlayerEvent]] | None = None,
    ) -> dict[str, BehaviorFeatures]:
        """Extract 16 behavior features per player.
        
        Input:  {player_id: PlayerDNA}, optional {player_id: [PlayerEvent]}
        Output: {player_id: BehaviorFeatures}  — 16 features, 0-1 normalized
        """
```

### 输出约束

```python
class BehaviorFeatures:
    # Progression (4 features)
    merge_velocity: float       # 0-1
    merge_depth: float          # 0-1
    level_growth_rate: float    # 0-1
    area_unlock_speed: float    # 0-1
    
    # Collection (4 features)
    collection_rate: float      # 0-1
    rare_item_ratio: float      # 0-1
    completion_bias: float      # 0-1
    missing_item_pressure: float # 0-1
    
    # Monetization (4 features)
    purchase_intent: float      # 0-1
    purchase_frequency: float   # 0-1
    offer_conversion: float     # 0-1
    spending_level: float       # 0-1
    
    # Engagement (4 features)
    session_frequency: float    # 0-1
    daily_return: float         # 0-1
    event_participation: float  # 0-1
    retention_strength: float   # 0-1
    
    # Computed scores (5 features)
    collector_score: float      # 0-1
    progression_score: float    # 0-1
    power_score: float          # 0-1
    explorer_score: float       # 0-1
    casual_score: float         # 0-1
```

## 2.3 ArchetypeClassifier

**等级**: STABLE  
**位置**: `player_intelligence/archetype_classifier.py`

### 契约

```python
class ArchetypeClassifier:
    def classify_all(
        dna_map: dict[str, PlayerDNA],
        features_map: dict[str, BehaviorFeatures],
    ) -> list[PlayerGenome]:
        """Classify all players into PlayerGenomes.
        
        Input:  {player_id: PlayerDNA}, {player_id: BehaviorFeatures}
        Output: [PlayerGenome, ...]  — each with archetype + value_segment
        """
```

### 输出约束

```python
class PlayerArchetype(Enum):  # FROZEN
    COLLECTOR = "collector"
    PROGRESSION = "progression"
    POWER = "power"
    EXPLORER = "explorer"
    CASUAL = "casual"

class PlayerGenome:
    player_id: str
    archetype: PlayerArchetype
    archetype_scores: dict[str, float]  # {arch: score}
    value_segment: ValueSegment          # HIGH / MEDIUM / LOW
    payment_profile: PaymentProfile
    behavior_features: BehaviorFeatures
```

---

# 3. Creative Matching（E9.6）

## 3.1 DNAFeatureEncoder

**等级**: STABLE  
**位置**: `creative_matching/dna_feature_encoder.py`

### 契约

```python
class DNAFeatureEncoder:
    def encode(dna: dict) -> DNAFeatureVector:
        """Encode Creative DNA into numeric feature vector.
        
        Input:  Creative DNA dict (hook, mechanism, reward, fantasy, etc.)
        Output: DNAFeatureVector (10 features, 0-1 normalized)
        """
```

### 输出约束

```python
class DNAFeatureVector:  # FROZEN — 字段不可删
    creative_id: str
    creative_genome_name: str
    
    # Core attraction (4 dimensions)
    collection_strength: float      # 0-1
    progression_strength: float     # 0-1
    power_expression: float         # 0-1
    exploration_strength: float     # 0-1
    
    # Creative quality (4 dimensions)
    emotion_intensity: float        # 0-1
    reward_value: float             # 0-1
    novelty_score: float            # 0-1
    urgency_signal: float           # 0-1
    
    # IAP signals (2 dimensions)
    payment_affinity: float         # 0-1
    retention_hook_strength: float  # 0-1
    
    # Source DNA (traceability)
    fantasy_drives: list[str]
    mechanism_type: str
    hook_type: str
    reward_type: str
    visual_style: str
    payment_triggers: list[str]
    retention_hooks: list[str]
```

## 3.2 ArchetypePredictor

**等级**: STABLE  
**位置**: `creative_matching/archetype_predictor.py`

### 契约

```python
class ArchetypePredictor:
    def __init__(profile_db: CreativeArchetypeProfileDB):
        """Initialize with archetype profile database."""
    
    def predict(fv: DNAFeatureVector) -> ArchetypePrediction:
        """Predict archetype distribution for a DNA feature vector.
        
        Formula: P(arch | DNA) = 0.8 × DNA_affinity + 0.2 × prior
        """
    
    def set_weights(weights: dict[str, dict[str, float]]):
        """Override DNA feature weights from E9.7 learning.
        
        Input: {archetype: {feature: weight}}
        """
```

### 输出约束

```python
class ArchetypePrediction:
    creative_id: str
    archetype_distribution: dict[str, ArchetypePredictionDetail]
    # {power: {raw_affinity, adjusted_probability, confidence}, ...}
    
    expected_metrics: dict[str, float]
    # {ltv, d30, payer_rate}
    
    overall_confidence: float  # 0-1
```

## 3.3 MatchingEngine

**等级**: STABLE  
**位置**: `creative_matching/matching_engine.py`

### 契约

```python
class MatchingEngine:
    def run() -> dict[str, Any]:
        """Run full E9.6 pipeline.
        
        Outputs:
          - creative_prediction.json (912 entries)
          - creative_archetype_rank.json (6 ranking categories)
        """
```

---

# 4. Creative Learning（E9.7）

## 4.1 PredictionTracker

**等级**: STABLE  
**位置**: `creative_learning/prediction_tracker.py`

### 契约

```python
class PredictionTracker:
    records: list[PredictionRecord]
    
    def load_predictions(path: Path) -> int:
        """Load E9.6 predictions and save as history.
        
        Input:  creative_prediction.json
        Output: number of records loaded
        """
    
    def save_history(path: Path) -> Path:
        """Save prediction snapshots to disk."""
```

### 数据约束

```python
class PredictionRecord:  # FROZEN
    creative_id: str
    creative_genome_name: str
    prediction_time: str                    # ISO format
    archetype_prediction: dict[str, float]  # {arch: probability}
    predicted_metrics: dict[str, float]     # {ltv, d30, payer_rate}
    dna_features: dict[str, Any]            # {features: {...}, source_dna: {...}}
```

## 4.2 PerformanceCollector

**等级**: STABLE  
**位置**: `creative_learning/performance_collector.py`

### 契约

```python
class PerformanceCollector:
    def load_from_csv(path: Path) -> int:
        """Load real campaign data from CSV."""
    
    def load_from_json(path: Path) -> int:
        """Load real campaign data from JSON."""
    
    def add_performance(perf: CreativeActualPerformance):
        """Add a single performance record."""

class MockPerformanceGenerator:
    def __init__(seed: int = 42):
        """Initialize with deterministic seed."""
    
    def generate(predictions: list[dict]) -> list[CreativeActualPerformance]:
        """Generate mock 'actual' performance with systematic biases.
        
        Biases embedded in DNA features:
          - challenge → power +25%
          - emotional → collector +15%
          - secret → explorer +12%
          - discovery → LTV +18%
          - unlock → LTV +12%
          - collection → collector +18%
          - progression → progression +15%
        """
```

### 数据约束

```python
class CreativeActualPerformance:  # FROZEN
    creative_id: str
    data_source: str                         # "facebook" | "adjust" | "firebase" | "mock"
    installs: int
    spend: float
    revenue: float
    total_players: int
    d30_retention: float
    payer_rate: float
    ltv_d7: float
    ltv_d30: float
    archetype_distribution: dict[str, float]  # {arch: proportion}
    raw_player_count: int
```

## 4.3 ArchetypeReconstructionEngine

**等级**: STABLE  
**位置**: `creative_learning/archetype_reconstruction.py`

### 契约

```python
class ArchetypeReconstructionEngine:
    def reconstruct_from_events(
        events_by_creative: dict[str, list[PlayerEvent]],
    ) -> dict[str, dict[str, float]]:
        """Reconstruct archetypes from raw player events (real mode).
        
        Pipeline: PlayerEvent → PlayerDNA → BehaviorFeatures → Archetype → Distribution
        """
    
    def reconstruct_from_performances(
        performances: dict[str, CreativeActualPerformance],
    ) -> dict[str, dict[str, float]]:
        """Extract distributions from pre-computed performances (mock mode)."""
    
    def reconstruct_from_dna_map(
        dna_map: dict[str, PlayerDNA],
        events_by_player: dict[str, list[PlayerEvent]] | None = None,
    ) -> dict[str, float]:
        """Reconstruct distribution from a DNA map (single creative)."""
    
    @staticmethod
    def merge_distributions(
        distributions: list[dict[str, float]],
        weights: list[float] | None = None,
    ) -> dict[str, float]:
        """Weighted average merge across multiple campaigns."""
```

## 4.4 PredictionErrorAnalyzer

**等级**: STABLE  
**位置**: `creative_learning/prediction_error_analyzer.py`

### 契约

```python
class PredictionErrorAnalyzer:
    def compare(
        predictions: dict[str, PredictionRecord],
        actuals: dict[str, CreativeActualPerformance],
    ) -> dict[str, PredictionError]:
        """Compare predicted vs actual for all creatives.
        
        Computes:
          - ArchetypeError per archetype (absolute + relative)
          - MetricError per metric (LTV, D30, payer_rate)
          - archetype_mae (mean absolute error across archetypes)
          - metric_mae (mean absolute error across metrics)
          - ltv_error (LTV prediction error)
        """
    
    def get_error_report(errors: dict[str, PredictionError]) -> dict[str, Any]:
        """Aggregate error summary across all creatives."""
```

### 数据约束

```python
class PredictionError:  # FROZEN
    creative_id: str
    creative_genome_name: str
    archetype_errors: dict[str, ArchetypeError]   # {arch: error}
    metric_errors: dict[str, MetricError]          # {metric: error}
    archetype_mae: float
    metric_mae: float
    ltv_error: float

class ArchetypeError:
    archetype: str
    predicted: float
    actual: float
    absolute_error: float
    relative_error: float  # (actual - predicted) / max(predicted, 0.01)

class MetricError:
    metric: str
    predicted: float
    actual: float
    absolute_error: float
    relative_error: float
```

## 4.5 DNAWeightOptimizer

**等级**: STABLE  
**位置**: `creative_learning/dna_weight_optimizer.py`

### 契约

```python
class DNAWeightOptimizer:
    total_updates: int
    updates: list[DNAWeightUpdate]
    
    def optimize(
        errors: dict[str, PredictionError],
        predictions: dict[str, PredictionRecord],
        actuals: dict[str, CreativeActualPerformance],
    ) -> DNAWeightConfig:
        """Learn optimal DNA feature weights.
        
        Algorithm:
          1. Group errors by DNA feature values (hook_type, reward_type, etc.)
          2. For each feature+archetype pair with |mean_error| > threshold:
             new_weight = old_weight + learning_rate × mean_error
          3. Clip weights to viable range
          4. Skip empty/unknown/none feature values
        
        Config:
          learning_rate = 0.25
          error_threshold = 0.01
        """
    
    def save_weights(path: str):
        """Save learned weights to JSON."""
```

### 数据约束

```python
class DNAWeightConfig:  # FROZEN
    version: str
    updated_at: str
    weights: dict[str, dict[str, float]]  # {archetype: {feature: weight}}
    updates: list[DNAWeightUpdate]

class DNAWeightUpdate:
    feature: str
    archetype: str
    old_weight: float
    new_weight: float
    delta: float       # new_weight - old_weight
    reason: str
```

## 4.6 LearningEngine

**等级**: STABLE  
**位置**: `creative_learning/learning_engine.py`

### 契约

```python
class LearningEngine:
    def run() -> dict[str, Any]:
        """Run complete feedback learning loop.
        
        Pipeline:
          1. load_predictions()      → load E9.6 predictions
          2. generate_mock_performance() → generate mock actuals
          3. reconstruct_archetypes()    → reconstruct via E9.5 pipeline
          4. calculate_errors()          → compute prediction errors
          5. optimize_weights()          → learn DNA weight adjustments
          6. re_predict()                → re-predict with new weights
          7. build_learning_report()     → build learning summary
          8. export_all()                → export 5 output files
        
        Returns:
          {status, summary, export_paths, data_loaded}
        """
```

## 4.7 LearningExporter

**等级**: STABLE  
**位置**: `creative_learning/export.py`

### 契约

```python
class LearningExporter:
    def __init__(output_dir: str | Path = "output/creative_learning"):
        """Initialize with output directory."""
    
    def export_all(
        tracker: PredictionTracker,
        performances: dict[str, CreativeActualPerformance],
        errors: dict[str, PredictionError],
        weight_config: DNAWeightConfig | None = None,
        learning_report: LearningReport | None = None,
        analyzer: PredictionErrorAnalyzer | None = None,
        optimizer: DNAWeightOptimizer | None = None,
    ) -> dict[str, str]:
        """Export all 5 output files.
        
        Returns: {file_category: full_path}
        """
    
    def get_export_summary(paths: dict[str, str]) -> dict[str, Any]:
        """Get summary of exported files with sizes."""
```

---

# 5. 跨层数据流契约

## 5.1 E9.5 → E9.6 接口

```
Player Intelligence (E9.5)
    ↓
creative_archetype_matrix.json
    ↓
Creative Matching (E9.6)
```

**契约**：`CreativeArchetypeProfileDB` 加载 `player_genomes.json` 和 `creative_archetype_matrix.json`，计算先验分布和 archetype metrics。

## 5.2 E9.6 → E9.7 接口

```
Creative Matching (E9.6)
    ↓
creative_prediction.json
    ↓
Creative Learning (E9.7)
```

**契约**：`PredictionTracker.load_predictions()` 读取 `creative_prediction.json`，格式必须符合 `PredictionRecord` schema。

## 5.3 E9.7 → E9.6 反馈接口

```
Creative Learning (E9.7)
    ↓
dna_weight_config.json
    ↓
Creative Matching (E9.6)
```

**契约**：`ArchetypePredictor.set_weights()` 接受 `DNAWeightConfig.weights` 格式。

---

# 6. 输出文件契约

| 文件 | 生产者 | 消费者 | 格式 | 字段约束 |
|------|--------|--------|------|---------|
| `creative_prediction.json` | E9.6 | E9.7 | JSON Array | 每个 entry 含 `creative_id`, `prediction`, `expected` |
| `creative_archetype_rank.json` | E9.6 | Human / Dashboard | JSON Object | 6 个 ranking 类别 |
| `prediction_history.json` | E9.7 | E9.8+ | JSON Array | 每个 entry 符合 `PredictionRecord` |
| `actual_performance.json` | E9.7 | E9.8+ | JSON Array | 每个 entry 符合 `CreativeActualPerformance` |
| `prediction_error_report.json` | E9.7 | Human / Dashboard | JSON Object | `summary` + `errors` |
| `dna_weight_config.json` | E9.7 | E9.6 feedback | JSON Object | `weights` + `updates` |
| `learning_report.json` | E9.7 | Human / Dashboard | JSON Object | 符合 `LearningReport` |