# P04 Winners → Creative Factory 升级方案

## 一、核心发现：真正的 DNA 不是「紫色女巫」

P04 赢家素材成功的底层驱动，并不是简单的颜色或角色，而是三个核心心理机制：

* Collection（收集）
* Progress（成长）
* Mystery（未知）

因此，Visual DNA 不应该停留在视觉元素：

```python
紫色
女巫
粒子
```

而应该升级为：

```python
Collection
Progress
Mystery
Reward
Cute
Magic
```

视觉只是表现层，心理驱动才是核心层。

---

# 二、Hook 结构优化

当前赢家几乎全部属于 Collection。

建议预算分布：

### Collection（80%）

示例：

```text
200+ Creatures
Discover All Dragons
```

### Progress（10%）

示例：

```text
Lv1 → Lv10 → Lv100
Can You Reach The End?
```

### Curiosity（10%）

示例：

```text
What's Inside?
???
Secret Dragon
```

这样能够避免创意衰减，提高长期稳定性。

---

# 三、赢家2真正成功的是 Progress

吸引用户的并不是城堡，而是成长路径：

```text
小屋
↓
房子
↓
豪宅
↓
城堡
↓
？？？
```

因此扩量时不应局限于城堡。

可裂变：

### 龙链

```text
蛋
↓
小龙
↓
飞龙
↓
神龙
↓
？？？
```

### 花链

```text
种子
↓
花苞
↓
生命树
↓
神树
↓
？？？
```

### 女巫链

```text
学徒
↓
魔法师
↓
大魔女
↓
女王
↓
？？？
```

核心：

Progress > 具体物体。

---

# 四、预算结构调整

原方案：

* 80% 微创新
* 10% Hook测试
* 10% 创意组合

建议升级：

### 70%

Winner Mutation

（同风格裂变）

### 20%

New Hook

（Progress / Mystery）

### 10%

Explore

（全新方向）

这样可以对抗 Creative Fatigue。

---

# 五、Visual DNA 升级

旧版：

```json
{
  "hooks": {},
  "rewards": {},
  "emotions": {}
}
```

升级为：

```json
{
 "hook_type": "",
 "reward_type": "",
 "emotion_type": "",
 "progress_depth": "",
 "collection_density": "",
 "character_count": "",
 "mystery_score": "",
 "cute_score": "",
 "color_theme": "",
 "camera_distance": "",
 "composition": "",
 "particle_strength": ""
}
```

示例：

```json
{
 "hook_type":"collection",
 "reward_type":"dragon",
 "progress_depth":1,
 "collection_density":9,
 "mystery_score":6,
 "cute_score":9,
 "color_theme":"purple",
 "composition":"hero_center"
}
```

这样 AI 才能学习真正的成功基因。

---

# 六、Mutation Engine

目标不是生成16张图，而是建立遗传循环。

```
Seed
↓
Mutation
↓
Meta
↓
Winner Engine
↓
Visual DNA
↓
Mutation
↓
……
```

流程：

### Seed

4张赢家

↓

### Mutation

每张25个变体

共100张

↓

Meta投放

↓

Winner Engine

筛选Top20

↓

Visual DNA

提取共同基因

↓

生成下一代100张

形成持续进化。

---

# 七、Anti Collapse

不建议使用：

```python
CLIP > 0.95
```

推荐：

```python
0.85+
重复

0.75~0.85
轻度重复

0.65~0.75
最佳

<0.6
风格偏离
```

最佳相似度区间：

0.65~0.75

既继承爆款，又保持新鲜感。

---

# 八、第一批创意生产建议

不要16张。

直接生成24张。

## Collection

8张

* 龙
* 独角兽
* 狐狸
* 猫头鹰

---

## Progress

8张

* 花链
* 城堡链
* 女巫链
* 龙链

---

## Mystery

8张

* ???蛋
* ???龙
* ???女巫
* ???城堡

---

# 九、形成 Creative Factory

```
P04 Winners
      ↓
Visual DNA
      ↓
Mutation Engine
      ↓
24 Creatives
      ↓
Meta
      ↓
Winner Engine
      ↓
P05 Winners
      ↓
Visual DNA V2
      ↓
P06 Creatives
      ↓
……
```

最终形成一个持续进化的 Facebook Merge 游戏 Creative Factory，而不是依赖人工不断想创意。

核心目标：

让素材自动学习、自动裂变、自动淘汰、自动进化。