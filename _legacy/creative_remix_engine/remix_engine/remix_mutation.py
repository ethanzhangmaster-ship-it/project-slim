"""Remix Mutation Engine — 剪辑策略变异

基于 Winner 结构产生变体：
1. 换 Hook：Hook D + Gameplay B + Reward C
2. 提前 Reward：Hook A + Reward C + Gameplay B
3. 加速：30s -> 20s
4. 延长某段
5. 插入 Story
6. 双 Reward
7. 去掉 Ending
"""
import copy
from typing import List, Optional
from dataclasses import dataclass

import numpy as np

from .winner_structure_miner import WinningStructure, StructureSegment


class MutationStrategy:
    """变异策略枚举"""
    SWAP_HOOK = "swap_hook"
    EARLY_REWARD = "early_reward"
    SPEED_UP = "speed_up"
    EXTEND_SEGMENT = "extend_segment"
    ADD_STORY = "add_story"
    DOUBLE_REWARD = "double_reward"
    DROP_ENDING = "drop_ending"
    SHUFFLE = "shuffle"
    SHORTEN = "shorten"

    ALL = [
        SWAP_HOOK, EARLY_REWARD, SPEED_UP, EXTEND_SEGMENT,
        ADD_STORY, DOUBLE_REWARD, DROP_ENDING, SHUFFLE, SHORTEN,
    ]


class RemixMutationEngine:
    """Remix 变异引擎"""

    def __init__(self):
        self.strategies = MutationStrategy.ALL

    def mutate(self, structure: WinningStructure,
               strategy: Optional[str] = None,
               n_variants: int = 3) -> List[WinningStructure]:
        """生成变异结构"""
        if strategy:
            return self._apply_strategy(structure, strategy, n_variants)

        # 随机应用多种策略
        variants = []
        for _ in range(n_variants):
            random_strategy = np.random.choice(self.strategies)
            result = self._apply_strategy(structure, random_strategy, 1)
            variants.extend(result)

        return variants

    def _apply_strategy(self, structure: WinningStructure,
                        strategy: str, n: int) -> List[WinningStructure]:
        """应用特定策略"""
        variants = []

        for i in range(n):
            new_struct = copy.deepcopy(structure)
            new_struct.name = f"{structure.name}_mut_{strategy}_{i+1}"
            new_struct.structure_id = f"{structure.structure_id}_mut_{strategy}_{i+1}"
            new_struct.confidence *= 0.85

            if strategy == MutationStrategy.SWAP_HOOK:
                self._mutate_swap_hook(new_struct)
            elif strategy == MutationStrategy.EARLY_REWARD:
                self._mutate_early_reward(new_struct)
            elif strategy == MutationStrategy.SPEED_UP:
                self._mutate_speed_up(new_struct)
            elif strategy == MutationStrategy.EXTEND_SEGMENT:
                self._mutate_extend_segment(new_struct)
            elif strategy == MutationStrategy.ADD_STORY:
                self._mutate_add_story(new_struct)
            elif strategy == MutationStrategy.DOUBLE_REWARD:
                self._mutate_double_reward(new_struct)
            elif strategy == MutationStrategy.DROP_ENDING:
                self._mutate_drop_ending(new_struct)
            elif strategy == MutationStrategy.SHUFFLE:
                self._mutate_shuffle(new_struct)
            elif strategy == MutationStrategy.SHORTEN:
                self._mutate_shorten(new_struct)

            # 重新计算总时长
            new_struct.total_duration = sum(s.duration for s in new_struct.segments)
            variants.append(new_struct)

        return variants

    def _mutate_swap_hook(self, struct: WinningStructure):
        """换 Hook：保持 gameplay/reward 不变，改变 hook"""
        for seg in struct.segments:
            if seg.role == "hook":
                # 随机选择一个不同的主体
                subjects = ["dragon", "witch", "warrior", "monster"]
                seg.subject = np.random.choice(subjects)
                seg.action = np.random.choice(["attack", "transform", "rescue"])
                seg.emotion = "surprise"
                break

    def _mutate_early_reward(self, struct: WinningStructure):
        """提前 Reward：调整顺序为 hook -> reward -> gameplay -> ending"""
        roles = [s.role for s in struct.segments]
        if "reward" in roles and "gameplay" in roles:
            reward_idx = roles.index("reward")
            gameplay_idx = roles.index("gameplay")
            if reward_idx > gameplay_idx:
                # 交换
                struct.segments[reward_idx], struct.segments[gameplay_idx] = \
                    struct.segments[gameplay_idx], struct.segments[reward_idx]

    def _mutate_speed_up(self, struct: WinningStructure):
        """加速：总时长缩短 30%"""
        target_duration = struct.total_duration * 0.7
        scale = target_duration / struct.total_duration
        for seg in struct.segments:
            seg.duration = round(seg.duration * scale, 1)

    def _mutate_extend_segment(self, struct: WinningStructure):
        """延长某一段"""
        if struct.segments:
            idx = np.random.randint(len(struct.segments))
            struct.segments[idx].duration = round(struct.segments[idx].duration * 1.5, 1)

    def _mutate_add_story(self, struct: WinningStructure):
        """插入 Story 段"""
        story_seg = StructureSegment(
            role="story",
            duration=3.0,
            subject="character",
            action="explore",
            emotion="curiosity",
            camera="pan",
        )
        # 插入在 hook 之后
        if struct.segments and struct.segments[0].role == "hook":
            struct.segments.insert(1, story_seg)
        else:
            struct.segments.insert(0, story_seg)

    def _mutate_double_reward(self, struct: WinningStructure):
        """双 Reward"""
        reward_segs = [s for s in struct.segments if s.role == "reward"]
        if reward_segs:
            # 复制一个 reward
            new_reward = copy.deepcopy(reward_segs[0])
            new_reward.duration = round(new_reward.duration * 0.7, 1)
            # 插入到 gameplay 之后
            for i, seg in enumerate(struct.segments):
                if seg.role == "gameplay":
                    struct.segments.insert(i + 1, new_reward)
                    break

    def _mutate_drop_ending(self, struct: WinningStructure):
        """去掉 Ending"""
        struct.segments = [s for s in struct.segments if s.role != "ending"]

    def _mutate_shuffle(self, struct: WinningStructure):
        """随机打乱顺序（保持 hook 在前）"""
        if len(struct.segments) <= 2:
            return

        hook_segs = [s for s in struct.segments if s.role == "hook"]
        other_segs = [s for s in struct.segments if s.role != "hook"]

        np.random.shuffle(other_segs)
        struct.segments = hook_segs + other_segs

    def _mutate_shorten(self, struct: WinningStructure):
        """缩短总时长至 20s"""
        target = 20.0
        current = sum(s.duration for s in struct.segments)
        if current > target:
            scale = target / current
            for seg in struct.segments:
                seg.duration = max(1.0, round(seg.duration * scale, 1))

    def generate_all_mutations(self, structure: WinningStructure) -> List[WinningStructure]:
        """生成所有可能的变异"""
        all_variants = []
        for strategy in self.strategies:
            variants = self.mutate(structure, strategy=strategy, n_variants=2)
            all_variants.extend(variants)
        return all_variants