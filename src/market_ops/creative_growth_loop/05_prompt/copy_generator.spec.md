# Copy Generator Spec v1.0

> **分层决策链生成文案**。基于 CreativeGene + 上下文（游戏/国家/受众）生成多语言广告文案。
> 任何代码修改必须遵循此 Spec。

---

## §1 设计目标

让系统从"硬编码文案"升级为"策略驱动多语言文案生成"，支持：
- 10 种 Hook 类型（secret / challenge / warning / wrong_choice / before_after / reward / curiosity / urgency / social / achievement）
- 5 语言模板（中 / 英 / 日 / 韩 / 西）
- 8 种游戏类型（puzzle / rpg / casual / strategy / hyper_casual / match3 / simulation / action）
- 4 种受众（casual / hardcore / f2p / midcore）

### 核心约束（强约束）

- ❌ 不允许硬编码 Headline（当前 `"Play Now!"` 已废弃）
- ❌ 不允许绕过 Hook 类型随机选择文案
- ✔ 每条文案必须可解释来源（Hook + Emotion + Reward + Audience）
- ✔ 支持多语言自动推断（Country → Language）
- ✔ 支持文案变体 A/B 测试（count 参数）
- ✔ Reward 占位符 `{reward}` 必须被替换为对应语言名称

---

## §2 数据流

```
CreativeGene(hook, reward, emotion) + Country + GameCategory + Audience → CopyGenerator → AdCopy
```

输入：
- `gene.hook`：Hook 类型（10 种）
- `gene.reward`：奖励类型（gold_dragon / castle / treasure / diamond / phoenix / unicorn / golden_tree / magic_item / legendary / rare / unknown）
- `gene.emotion`：情绪（surprise / excited / happy / panic / wow / curious / mysterious）
- `country`：国家代码（US / JP / CN / KR / DE / FR / BR / ...）
- `game_category`：游戏类型（puzzle / rpg / casual / strategy / hyper_casual / match3 / simulation / action）
- `audience`：受众类型（casual / hardcore / f2p / midcore）
- `cta_type`：CTA 类型（INSTALL_MOBILE_APP / PLAY_NOW / DOWNLOAD / GET_STARTED / TRY_IT）

输出：
- `AdCopy`：包含 headline / primary_text / description / cta / language / hook_type / emotion / reward

---

## §3 核心对象

### AdCopy（单条文案）

| 字段 | 类型 | 说明 |
|---|---|---|
| headline | str | 广告标题（从 Hook 模板生成） |
| primary_text | str | 广告正文（从 Emotion + Audience 生成） |
| description | str | 广告描述（从 Game Category 生成） |
| cta | str | 行动号召（从 CTA_TEMPLATES 生成） |
| language | str | 语言代码（en / zh / ja / ko / es） |
| hook_type | str | 使用的 Hook 类型 |
| emotion | str | 使用的情绪 |
| reward | str | 使用的奖励 |

### CopyVariant（文案变体）

| 字段 | 类型 | 说明 |
|---|---|---|
| variant_id | str | 变体 ID（copy_000 / copy_001） |
| copies | AdCopy | 变体文案 |

---

## §4 分层决策链

文案生成遵循固定顺序：

```
1. Game Category → 核心信息点
2. Country/Language → 选择语言模板
3. Audience Segment → 调整文案风格
4. Creative Hook Type → 匹配文案句式
5. Emotion → 调整文案语气
6. Reward Type → 植入利益点
7. CTA Type → 选择行动号召
```

每层都有显式映射表：
- `HOOK_HEADLINE_TEMPLATES`：Hook → Headline 模板
- `EMOTION_PRIMARY_TEXT`：Emotion → Primary Text 风格
- `GAME_CATEGORY_DESCRIPTION`：Game → Description
- `AUDIENCE_ADJUSTMENT`：Audience → 风格调整
- `CTA_TEMPLATES`：CTA → 多语言文案
- `REWARD_NAMES`：Reward → 多语言名称

---

## §5 核心约束

### 语言推断规则

```python
CN → zh  | HK → zh | TW → zh | SG → zh
JP → ja
KR → ko
ES → es | MX → es | AR → es | CO → es | CL → es | PE → es
默认 → en
```

### Reward 占位符替换

模板中的 `{reward}` 必须被替换为对应语言的名称：

```
gold_dragon → Golden Dragon (en) / 金龙 (zh) / ゴールデンドラゴン (ja)
castle → Castle (en) / 城堡 (zh) / 城 (ja)
treasure → Treasure (en) / 宝藏 (zh) / 宝物 (ja)
...
```

### A/B 测试变体生成

`generate_variants(count=5)` 输出 5 个变体，轮换使用不同 CTA 类型：
- INSTALL_MOBILE_APP / PLAY_NOW / DOWNLOAD / GET_STARTED / TRY_IT

---

## §6 接口定义

### CopyGenerator

```python
class CopyGenerator:
    def generate_ad_copy(
        gene,              # CreativeGene（duck typing）
        game_category,     # 游戏类型
        country,           # 国家代码
        audience,          # 受众类型
        cta_type           # CTA 类型
    ) -> AdCopy

    def generate_variants(
        gene,
        game_category,
        country,
        audience,
        count              # 变体数量
    ) -> List[CopyVariant]

    def generate_multi_language(
        gene,
        game_category,
        countries,         # 国家列表
        audience
    ) -> Dict[str, AdCopy]

    def extract_headlines(variants) -> List[str]
    def extract_primary_texts(variants) -> List[str]
    def extract_ctas(variants) -> List[str]
```

---

## §7 输出文件

运行后生成：
- `output/copy_variants.json`：文案变体集合

格式：
```json
[
  {
    "variant_id": "copy_000",
    "headline": "Something unexpected happens",
    "primary_text": "You won't believe what you're missing...",
    "description": "Fun for all ages!",
    "cta": "Install Now",
    "language": "en",
    "hook_type": "curiosity",
    "emotion": "surprise",
    "reward": "treasure"
  }
]
```

---

## §8 与主流程集成

接入 `run_pipeline.py` Step 5.2：

```python
step5_2_result = step5_2_copy_generation(
    results,              # FinalBandit 学习结果
    game_category,        # 游戏类型
    countries             # 国家列表
)
```

输出文件：`output/copy_variants.json`