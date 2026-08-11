"""DNA Mutation Strategy — Phase 2 变异维度定义。

定义可变异的 DNA 维度。变异引擎（dna_mutator.py）与评分模块都依赖此枚举，
保证维度命名全局一致。
"""
from __future__ import annotations

from enum import Enum


class MutationDimension(str, Enum):
    """Winner DNA 可变异维度。

    每个维度对应赢家创意的一个成功因素切面；变异引擎在保留核心维度
    （character / color / hook）的同时，针对其他维度做有策略的变化。
    """

    CHARACTER = "character"
    BACKGROUND = "background"
    GAMEPLAY = "gameplay"
    REWARD = "reward"
    COMPOSITION = "composition"
    COLOR = "color"
    HOOK = "hook"

    @classmethod
    def all(cls) -> list[str]:
        return [d.value for d in cls]

    @classmethod
    def preserved(cls) -> list[str]:
        """默认应保留（不轻易变异）的核心维度——决定“像不像 Winner”。"""
        return [cls.CHARACTER.value, cls.COLOR.value, cls.HOOK.value]

    @classmethod
    def mutable(cls) -> list[str]:
        """默认可积极变异的维度——制造创意方向与多样性。"""
        return [
            cls.BACKGROUND.value,
            cls.GAMEPLAY.value,
            cls.REWARD.value,
            cls.COMPOSITION.value,
        ]
