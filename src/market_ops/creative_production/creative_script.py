"""Creative Script - 广告脚本引擎

自动生成 15/20/30 秒广告脚本。
包含:
- Opening
- Gameplay
- Conflict
- Reward
- CTA
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScriptSegment:
    """脚本段落"""
    segment_type: str         # opening / gameplay / conflict / reward / cta / ending
    start_time: float         # 开始时间（秒）
    end_time: float           # 结束时间（秒）
    duration: float           # 时长
    text: str                 # 脚本内容
    action: str               # 动作描述
    visual: str               # 画面描述

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_type": self.segment_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "text": self.text,
            "action": self.action,
            "visual": self.visual,
        }


@dataclass
class CreativeScript:
    """广告脚本"""
    script_id: str
    variant_id: str
    total_duration: float
    segments: list[ScriptSegment] = field(default_factory=list)
    strategy_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "script_id": self.script_id,
            "variant_id": self.variant_id,
            "total_duration": self.total_duration,
            "segments": [s.to_dict() for s in self.segments],
            "strategy_id": self.strategy_id,
            "metadata": self.metadata,
        }


class CreativeScriptEngine:
    """广告脚本引擎
    
    根据 CreativeStrategy 自动生成结构化脚本。
    """
    
    # Hook 类型的脚本模板
    SCRIPT_TEMPLATES: dict[str, list[dict[str, Any]]] = {
        "collection": [
            {"type": "opening", "pct": 0.13, "action": "发现稀有物品，惊喜表情"},
            {"type": "gameplay", "pct": 0.40, "action": "展示收集玩法，多样物品"},
            {"type": "conflict", "pct": 0.07, "action": "遇到挑战/选择"},
            {"type": "reward", "pct": 0.20, "action": "收集完成，金币爆发"},
            {"type": "cta", "pct": 0.13, "action": "邀请下载，明确 CTA"},
            {"type": "ending", "pct": 0.07, "action": "品牌 logo 结尾"},
        ],
        "reward": [
            {"type": "opening", "pct": 0.07, "action": "金币爆发开场，强视觉"},
            {"type": "gameplay", "pct": 0.27, "action": "奖励机制展示"},
            {"type": "conflict", "pct": 0.13, "action": "困难/挑战"},
            {"type": "reward", "pct": 0.27, "action": "大奖展示，超级奖励"},
            {"type": "cta", "pct": 0.20, "action": "立即领取，CTA 强化"},
            {"type": "ending", "pct": 0.06, "action": "品牌结尾"},
        ],
        "merge": [
            {"type": "opening", "pct": 0.13, "action": "合成预览，物品发光"},
            {"type": "gameplay", "pct": 0.40, "action": "拖拽合成玩法"},
            {"type": "conflict", "pct": 0.07, "action": "错误选择"},
            {"type": "reward", "pct": 0.20, "action": "完美合成，新物品"},
            {"type": "cta", "pct": 0.13, "action": "开始合成"},
            {"type": "ending", "pct": 0.07, "action": "品牌结尾"},
        ],
        "transformation": [
            {"type": "opening", "pct": 0.13, "action": "变身前普通状态"},
            {"type": "gameplay", "pct": 0.20, "action": "收集资源/触发条件"},
            {"type": "conflict", "pct": 0.13, "action": "关键时刻，决定"},
            {"type": "reward", "pct": 0.27, "action": "史诗变身动画"},
            {"type": "cta", "pct": 0.20, "action": "开始你的旅程"},
            {"type": "ending", "pct": 0.07, "action": "品牌结尾"},
        ],
        "fail": [
            {"type": "opening", "pct": 0.13, "action": "错误选择瞬间"},
            {"type": "gameplay", "pct": 0.27, "action": "尝试过程"},
            {"type": "conflict", "pct": 0.20, "action": "失败/挑战"},
            {"type": "reward", "pct": 0.20, "action": "再试一次成功"},
            {"type": "cta", "pct": 0.13, "action": "你能做得更好吗"},
            {"type": "ending", "pct": 0.07, "action": "品牌结尾"},
        ],
        "emotion": [
            {"type": "opening", "pct": 0.13, "action": "情感瞬间特写"},
            {"type": "gameplay", "pct": 0.33, "action": "情感关系建立"},
            {"type": "conflict", "pct": 0.13, "action": "情感波折"},
            {"type": "reward", "pct": 0.20, "action": "情感高潮/解决"},
            {"type": "cta", "pct": 0.13, "action": "加入故事"},
            {"type": "ending", "pct": 0.08, "action": "温暖结尾"},
        ],
    }

    # 段落类型中文
    SEGMENT_TYPE_ZH: dict[str, str] = {
        "opening": "开场",
        "gameplay": "玩法",
        "conflict": "冲突/挑战",
        "reward": "奖励",
        "cta": "行动号召",
        "ending": "结尾",
    }

    def __init__(self):
        self._templates = dict(self.SCRIPT_TEMPLATES)
        self._seg_zh = dict(self.SEGMENT_TYPE_ZH)

    # ------------------------------------------------------------------
    # 核心生成
    # ------------------------------------------------------------------
    def generate(
        self,
        strategy: Any,  # CreativeStrategy
        variant: dict[str, Any],
    ) -> CreativeScript:
        """根据 CreativeStrategy 生成脚本

        Args:
            strategy: CreativeStrategy
            variant: Decision Variant

        Returns:
            CreativeScript
        """
        variant_id = strategy.variant_id
        duration = strategy.duration
        hook_type = strategy.hook
        dna = variant.get("dna", {})

        # 获取模板
        template = self._templates.get(hook_type, self._templates["collection"])

        # 提取元素
        character = dna.get("character", {}).get("type", "witch")
        creatures = dna.get("creatures", [{}])
        creature_type = creatures[0].get("type", "dragon") if creatures else "dragon"
        env = dna.get("environment", {}).get("type", "magic_forest")

        # 构建段落
        segments = []
        current_time = 0.0
        for tmpl in template:
            seg_duration = round(duration * tmpl["pct"], 1)
            seg_type = tmpl["type"]
            seg_zh = self._seg_zh.get(seg_type, seg_type)
            action = tmpl["action"]

            # 构建脚本内容
            text = self._build_segment_text(
                seg_type, character, creature_type, env, strategy
            )
            visual = self._build_segment_visual(
                seg_type, character, creature_type, env
            )

            segment = ScriptSegment(
                segment_type=seg_type,
                start_time=round(current_time, 1),
                end_time=round(current_time + seg_duration, 1),
                duration=seg_duration,
                text=text,
                action=action,
                visual=visual,
            )
            segments.append(segment)
            current_time += seg_duration

        # 调整最后一个段落使总时长精确
        if segments and abs(current_time - duration) > 0.1:
            diff = duration - current_time
            segments[-1].duration = round(segments[-1].duration + diff, 1)
            segments[-1].end_time = duration

        return CreativeScript(
            script_id=f"script_{variant_id}",
            variant_id=variant_id,
            total_duration=duration,
            segments=segments,
            strategy_id=variant_id,
            metadata={
                "hook_type": hook_type,
                "emotion": strategy.emotion,
                "objective": strategy.objective,
            },
        )

    def _build_segment_text(
        self,
        seg_type: str,
        character: str,
        creature: str,
        env: str,
        strategy: Any,
    ) -> str:
        """构建段落脚本内容"""
        texts = {
            "opening": f"在{env}中，{character}意外发现了一个会发光的{creature}...",
            "gameplay": f"{character}开始收集各种稀有物品，体验{strategy.gameplay}玩法",
            "conflict": f"遇到了挑战，{character}需要做出选择",
            "reward": f"成功！{strategy.reward_style}，{character}收获满满",
            "cta": strategy.cta_message,
            "ending": f"加入{character}的冒险旅程，{strategy.platform}搜索下载",
        }
        return texts.get(seg_type, "")

    def _build_segment_visual(
        self,
        seg_type: str,
        character: str,
        creature: str,
        env: str,
    ) -> str:
        """构建段落画面描述"""
        visuals = {
            "opening": f"特写 {character} 惊喜表情，{creature} 出现在 {env}",
            "gameplay": f"{character} 在 {env} 中移动收集，UI 元素出现",
            "conflict": f"画面变暗，挑战元素出现，{character} 紧张表情",
            "reward": f"特效爆发，{creature} 庆祝，金币 / 物品闪光",
            "cta": f"{character} 邀请姿势，按钮区域发光，CTA 文字出现",
            "ending": f"{character} 满足微笑，{env} 全景，logo 淡入",
        }
        return visuals.get(seg_type, "")

    # ------------------------------------------------------------------
    # 批量生成
    # ------------------------------------------------------------------
    def generate_batch(
        self,
        strategies: list[Any],
        variants: list[dict[str, Any]],
    ) -> list[CreativeScript]:
        """批量生成"""
        results = []
        for strategy, variant in zip(strategies, variants):
            try:
                script = self.generate(strategy, variant)
                results.append(script)
            except Exception:
                continue
        return results

    # ------------------------------------------------------------------
    # 格式化输出
    # ------------------------------------------------------------------
    def format_as_text(self, script: CreativeScript) -> str:
        """格式化为可读文本"""
        lines = [
            f"# {script.script_id}",
            f"总时长: {script.total_duration}秒",
            f"",
        ]
        for seg in script.segments:
            seg_zh = self._seg_zh.get(seg.segment_type, seg.segment_type)
            lines.extend([
                f"## [{seg.start_time}-{seg.end_time}秒] {seg_zh}",
                f"动作: {seg.action}",
                f"画面: {seg.visual}",
                f"脚本: {seg.text}",
                f"",
            ])
        return "\n".join(lines)