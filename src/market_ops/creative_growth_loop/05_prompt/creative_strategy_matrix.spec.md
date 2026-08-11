# Creative Strategy Matrix Spec v1.0

> **显式生图决策矩阵**。Game × Country × Audience → Style / Emotion / Color / Composition / Camera / Lighting。
> 任何代码修改必须遵循此 Spec。

---

## §1 设计目标

将"WHY"从隐式加权评分中提取为显式映射表，实现：
- **策略驱动生图**：每个决策可审计、可解释
- **文化适配**：27 国视觉偏好（色彩心理学）
- **游戏类型适配**：8 种游戏默认构图/镜头/风格
- **受众适配**：4 种受众复杂度调整

### 核心约束（强约束）

- ❌ 不允许 ML 黑盒决策生图风格
- ❌ 不允许隐式编码"美国偏好鲜艳"
- ✔ 每个决策必须来自显式映射表
- ✔ 每个策略必须可审计（explain_strategy）
- ✔ 支持覆盖（override_emotion）
- ✔ 支持 A/B 变体生成（get_ab_test_strategies）

---

## §2 数据流

```
Game + Country + Audience → CreativeStrategyMatrix → CreativeStrategy → PromptParams
```

输入：
- `game`：游戏类型（puzzle / rpg / casual / strategy / hyper_casual / match3 / simulation / action）
- `country`：国家代码（27 国）
- `audience`：受众类型（casual / hardcore / f2p / midcore）
- `override_emotion`：可选情绪覆盖

输出：
- `CreativeStrategy`：完整视觉参数（style / emotion / color_palette / composition / camera_angle / lighting / negative_prompt）
- `prompt_params`：可直接传给 prompt_builder 的参数字典

---

## §3 核心对象

### CreativeStrategy

| 字段 | 类型 | 说明 |
|---|---|---|
| game | str | 游戏类型 |
| country | str | 国家代码 |
| audience | str | 受众类型 |
| style | str | 视觉风格（3D cartoon / dark fantasy / anime / realistic） |
| emotion | str | 情绪基调（surprise / excited / happy / panic / wow / curious / mysterious） |
| color_palette | str | 色彩偏好（vibrant / warm / cool / dark / pastel） |
| composition | str | 构图（center focus / rule of thirds / diagonal） |
| camera_angle | str | 镜头角度（front / low angle / overhead / close-up） |
| lighting | str | 灯光风格（soft / dramatic / rim / backlit） |
| negative_prompt | str | 负向提示词 |

### PromptParams

```python
{
    "style": "3D cartoon",
    "emotion": "excited",
    "palette": "vibrant",
    "composition": "center focus",
    "camera": "front",
    "background": "bright colorful world, soft sky"
}
```

---

## §4 映射表结构

### Game Category → Style / Composition / Camera

```python
GAME_STYLE_MAP = {
    "puzzle": "3D cartoon",
    "rpg": "dark fantasy",
    "casual": "3D cartoon",
    "strategy": "realistic",
    "hyper_casual": "3D cartoon",
    "match3": "3D cartoon",
    "simulation": "realistic",
    "action": "dark fantasy",
}

GAME_COMPOSITION_MAP = {
    "puzzle": "center focus",
    "rpg": "rule of thirds",
    "casual": "center focus",
    "strategy": "diagonal",
    "hyper_casual": "center focus",
    "match3": "center focus",
    "simulation": "rule of thirds",
    "action": "diagonal",
}

GAME_CAMERA_MAP = {
    "puzzle": "front",
    "rpg": "low angle",
    "casual": "front",
    "strategy": "overhead",
    "hyper_casual": "close-up",
    "match3": "front",
    "simulation": "overhead",
    "action": "low angle",
}
```

### Country → Color / Emotion / Lighting（文化色彩心理学）

基于跨文化研究：

| 国家 | 色彩 | 情绪 | 灯光 | 理由 |
|------|------|------|------|------|
| **US** | vibrant | excited | soft | 高饱和度、强对比、积极情绪 |
| **JP** | pastel | curious | soft | 柔和色调、可爱风格、好奇心驱动 |
| **KR** | vibrant | wow | backlit | 高饱和度、惊艳效果、背光发光 |
| **CN** | warm | excited | dramatic | 暖色调、强烈情绪、戏剧性光影 |
| **TW** | warm | happy | soft | 暖色调、轻松愉快 |
| **HK** | vibrant | wow | dramatic | 高饱和度、惊艳效果 |
| **SG** | vibrant | happy | soft | 鲜艳、愉悦 |
| **DE** | cool | curious | soft | 冷色调、理性好奇 |
| **FR** | dark | mysterious | dramatic | 暗色调、神秘感 |
| **BR** | vibrant | excited | dramatic | 极度鲜艳、热情 |
| **MX** | warm | excited | dramatic | 暖色调、热情 |
| **IN** | vibrant | excited | dramatic | 极高饱和度、强烈 |
| **RU** | dark | mysterious | dramatic | 暗色调、神秘 |
| **SA** | warm | wow | dramatic | 暖色调、奢华 |
| **AE** | warm | wow | dramatic | 暖色调、奢华 |
| **AU** | vibrant | excited | soft | 鲜艳、积极 |
| **CA** | vibrant | excited | soft | 鲜艳、积极 |
| **ES** | warm | excited | dramatic | 暖色调、热情 |
| **IT** | warm | wow | dramatic | 暖色调、惊艳 |
| **AR** | warm | excited | dramatic | 暖色调、热情 |
| **TH** | warm | happy | soft | 暖色调、愉悦 |
| **VN** | vibrant | excited | dramatic | 鲜艳、激动 |
| **PH** | vibrant | happy | soft | 鲜艳、愉悦 |
| **ID** | vibrant | happy | soft | 鲜艳、愉悦 |
| **TR** | warm | excited | dramatic | 暂色调、热情 |
| **CO** | vibrant | excited | dramatic | 鲜艳、热情 |
| **GB** | cool | curious | soft | 冷色调、克制好奇 |

### Audience → Complexity / Negative Prompt

```python
AUDIENCE_VISUAL_ADJUSTMENT = {
    "casual": {
        "complexity": "simple",
        "character_count": "single",
        "text_overlay": "yes",
        "note": "休闲玩家：简单明了、单角色、需要文字引导",
    },
    "hardcore": {
        "complexity": "complex",
        "character_count": "multiple",
        "text_overlay": "no",
        "note": "硬核玩家：复杂场景、多角色、以画面为主",
    },
    "f2p": {
        "complexity": "simple",
        "character_count": "single",
        "text_overlay": "yes",
        "note": "免费玩家：极简设计、强CTA、高诱惑力",
    },
    "midcore": {
        "complexity": "medium",
        "character_count": "single",
        "text_overlay": "optional",
        "note": "中度玩家：中等复杂度、平衡",
    },
}
```

---

## §5 接口定义

```python
class CreativeStrategyMatrix:
    def get_strategy(
        game: str,
        country: str,
        audience: str = "casual",
        override_emotion: str | None = None
    ) -> CreativeStrategy

    def get_strategies_for_countries(
        game: str,
        countries: List[str],
        audience: str = "casual"
    ) -> Dict[str, CreativeStrategy]

    def get_ab_test_strategies(
        game: str,
        country: str,
        audience: str = "casual",
        n_variants: int = 3
    ) -> List[(str, CreativeStrategy)]

    def explain_strategy(strategy: CreativeStrategy) -> str

    def get_all_supported_games() -> List[str]
    def get_all_supported_countries() -> List[str]
    def get_all_supported_audiences() -> List[str]
```

---

## §6 审计要求

每个策略必须可解释：

```python
matrix = CreativeStrategyMatrix()
strategy = matrix.get_strategy("match3", "JP", "casual")
explanation = matrix.explain_strategy(strategy)
```

输出格式：
```
## 创意策略解释：match3 × JP × casual

| 参数 | 值 | 理由 |
|------|-----|------|
| Style | 3D cartoon | 游戏类型 'match3' 的默认风格 |
| Color Palette | pastel | 日本偏好柔和色调、可爱风格 |
| Emotion | curious | 国家偏好情绪基调 |
| Composition | center focus | 游戏类型 'match3' 的默认构图 |
| Camera | front | 游戏类型 'match3' 的默认镜头角度 |
| Lighting | soft | 国家偏好光照风格 |
| Audience Adjust | casual | 休闲玩家：简单明了、单角色 |
```

---

## §7 与主流程集成

接入 `run_pipeline.py` Step 5.1：

```python
step5_1_result = step5_1_creative_strategy(
    results,           # FinalBandit 学习结果
    game_category,     # 游戏类型
    countries          # 国家列表
)
```

输出文件：`output/creative_strategy_matrix.json`