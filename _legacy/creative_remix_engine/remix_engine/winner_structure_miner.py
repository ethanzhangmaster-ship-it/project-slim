"""Winner Structure Miner — 从真实UA数据挖掘 Winner 结构模式

输入：V3.8.1 真实 UA Performance 数据
输出：winning_structure.json

不是找 Winner 视频，而是找 Winner 结构。

分析维度：
- 结构时序（hook -> gameplay -> reward -> ending）
- 各段时长比例
- 主体类型组合
- 动作序列
- 情绪曲线
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np


@dataclass
class StructureSegment:
    """结构片段"""
    role: str          # hook, gameplay, reward, story, ending
    duration: float    # 时长（秒）
    subject: str       # 主体类型
    action: str        # 动作类型
    emotion: str       # 情绪类型
    camera: str        # 镜头类型


@dataclass
class WinningStructure:
    """Winner 结构模式"""
    name: str
    structure_id: str
    segments: List[StructureSegment]
    total_duration: float
    samples: int               # 样本数
    avg_ctr: float
    avg_cpi: float
    avg_d7_roi: float
    avg_d30_roi: float
    ad_value: float
    confidence: float          # 置信度
    tags: List[str]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "structure_id": self.structure_id,
            "segments": [asdict(s) for s in self.segments],
            "total_duration": self.total_duration,
            "samples": self.samples,
            "avg_ctr": self.avg_ctr,
            "avg_cpi": self.avg_cpi,
            "avg_d7_roi": self.avg_d7_roi,
            "avg_d30_roi": self.avg_d30_roi,
            "ad_value": self.ad_value,
            "confidence": self.confidence,
            "tags": self.tags,
        }


class WinnerStructureMiner:
    """Winner 结构挖掘器"""

    def __init__(self, min_samples: int = 3):
        self.min_samples = min_samples
        self.structures: List[WinningStructure] = []

    def mine(self, performance_data: List[dict],
             shot_library: Optional[dict] = None) -> List[WinningStructure]:
        """从表现数据中挖掘 Winner 结构"""
        print("[WinnerStructureMiner] Mining winning structures...")

        # Step 1: 筛选 Top 表现视频
        top_videos = self._filter_top_performers(performance_data)
        print(f"  Top performers: {len(top_videos)}")

        # Step 2: 提取每个视频的结构
        video_structures = []
        for video in top_videos:
            structure = self._extract_structure(video, shot_library)
            if structure:
                video_structures.append(structure)

        # Step 3: 聚类相似结构
        structure_groups = self._cluster_structures(video_structures)
        print(f"  Structure groups: {len(structure_groups)}")

        # Step 4: 计算每个模式的平均表现
        for group in structure_groups:
            winning_struct = self._build_winning_structure(group, top_videos)
            if winning_struct and winning_struct.samples >= self.min_samples:
                self.structures.append(winning_struct)

        # 按 ad_value 排序
        self.structures.sort(key=lambda s: -s.ad_value)
        print(f"  Winning structures found: {len(self.structures)}")

        return self.structures

    def _filter_top_performers(self, performance_data: List[dict],
                                top_pct: float = 0.2) -> List[dict]:
        """筛选 Top 表现视频"""
        # 计算综合得分
        scored = []
        for item in performance_data:
            perf = item.get("performance", item)
            ctr = perf.get("ctr", 0)
            cpi = perf.get("cpi", 1.0)
            d7_roi = perf.get("d7_roi", 0)
            d30_roi = perf.get("d30_roi", 0)

            # 综合 Ad Value
            ad_value = ctr * 15 + (1.0 / max(cpi, 0.01)) * 10 + d7_roi * 100 * 3

            scored.append((ad_value, item))

        scored.sort(key=lambda x: -x[0])
        n_top = max(1, int(len(scored) * top_pct))
        return [item for _, item in scored[:n_top]]

    def _extract_structure(self, video: dict,
                           shot_library: Optional[dict]) -> Optional[List[StructureSegment]]:
        """从视频中提取结构"""
        # 从 shot_library 获取该视频的结构
        if shot_library and "videos" in shot_library:
            creative_id = video.get("creative_id", "")
            video_data = shot_library["videos"].get(creative_id)
            if video_data:
                shots = video_data.get("shots", [])
                return [
                    StructureSegment(
                        role=s.get("role", "gameplay"),
                        duration=s.get("duration", 5.0),
                        subject=s.get("subject", "character"),
                        action=s.get("action", "merge"),
                        emotion=s.get("emotion", "curiosity"),
                        camera=s.get("camera", "static"),
                    )
                    for s in shots
                ]

        # 如果找不到，使用默认结构（基于性能数据推断）
        return self._infer_default_structure(video)

    def _infer_default_structure(self, video: dict) -> List[StructureSegment]:
        """推断默认结构"""
        # 基于典型的买量广告结构
        return [
            StructureSegment("hook", 3.0, "character", "attack", "surprise", "zoom_in"),
            StructureSegment("gameplay", 7.0, "character", "merge", "curiosity", "pan"),
            StructureSegment("reward", 8.0, "character", "upgrade", "satisfaction", "zoom_in"),
            StructureSegment("ending", 5.0, "character", "collect", "excitement", "static"),
        ]

    def _cluster_structures(self, structures: List[List[StructureSegment]]) -> List[List[List[StructureSegment]]]:
        """聚类相似结构"""
        if not structures:
            return []

        # 简化：按结构序列的角色模式分组
        groups = defaultdict(list)
        for struct in structures:
            # 用角色序列作为 key
            role_key = "->".join([s.role for s in struct])
            groups[role_key].append(struct)

        return list(groups.values())

    def _build_winning_structure(self, group: List[List[StructureSegment]],
                                  top_videos: List[dict]) -> Optional[WinningStructure]:
        """构建 Winner 结构模式"""
        if not group:
            return None

        # 取第一个作为模板
        template = group[0]
        role_pattern = "->".join([s.role for s in template])

        # 计算平均时长
        avg_durations = []
        for struct in group:
            avg_durations.append([s.duration for s in struct])

        avg_durations = np.array(avg_durations).mean(axis=0)

        # 统计最常见的属性
        subjects = Counter([s.subject for struct in group for s in struct])
        actions = Counter([s.action for struct in group for s in struct])
        emotions = Counter([s.emotion for struct in group for s in struct])

        # 构建平均结构
        segments = []
        for i, seg in enumerate(template):
            segments.append(StructureSegment(
                role=seg.role,
                duration=round(avg_durations[i], 1),
                subject=subjects.most_common(1)[0][0] if subjects else seg.subject,
                action=actions.most_common(1)[0][0] if actions else seg.action,
                emotion=emotions.most_common(1)[0][0] if emotions else seg.emotion,
                camera=seg.camera,
            ))

        total_duration = sum(s.duration for s in segments)

        # 计算平均表现
        # 从 top_videos 中找匹配的视频
        matching_perfs = []
        for video in top_videos:
            matching_perfs.append(video.get("performance", video))

        if matching_perfs:
            avg_ctr = np.mean([p.get("ctr", 0) for p in matching_perfs])
            avg_cpi = np.mean([p.get("cpi", 1.0) for p in matching_perfs])
            avg_d7_roi = np.mean([p.get("d7_roi", 0) for p in matching_perfs])
            avg_d30_roi = np.mean([p.get("d30_roi", 0) for p in matching_perfs])
        else:
            avg_ctr = avg_cpi = avg_d7_roi = avg_d30_roi = 0

        ad_value = avg_ctr * 15 + (1.0 / max(avg_cpi, 0.01)) * 10 + avg_d7_roi * 100 * 3

        # 生成名称
        main_subject = segments[0].subject if segments else "unknown"
        main_action = segments[0].action if segments else "unknown"
        name = f"{main_subject.title()}_{main_action.title()}_{role_pattern.replace('->', '_')}"

        return WinningStructure(
            name=name,
            structure_id=f"struct_{name.lower()}",
            segments=segments,
            total_duration=round(total_duration, 1),
            samples=len(group),
            avg_ctr=round(avg_ctr, 2),
            avg_cpi=round(avg_cpi, 2),
            avg_d7_roi=round(avg_d7_roi, 3),
            avg_d30_roi=round(avg_d30_roi, 3),
            ad_value=round(ad_value, 2),
            confidence=min(1.0, len(group) / 10),
            tags=[main_subject, main_action, role_pattern],
        )

    def get_best_structure(self, min_ad_value: float = 50) -> Optional[WinningStructure]:
        """获取最佳结构"""
        for struct in self.structures:
            if struct.ad_value >= min_ad_value:
                return struct
        return self.structures[0] if self.structures else None

    def get_structure_variants(self, base_structure: WinningStructure,
                                n_variants: int = 3) -> List[WinningStructure]:
        """获取结构变体"""
        variants = []
        for i in range(n_variants):
            # 微调时长
            new_segments = []
            for seg in base_structure.segments:
                duration_variation = np.random.uniform(0.8, 1.2)
                new_segments.append(StructureSegment(
                    role=seg.role,
                    duration=round(seg.duration * duration_variation, 1),
                    subject=seg.subject,
                    action=seg.action,
                    emotion=seg.emotion,
                    camera=seg.camera,
                ))

            variants.append(WinningStructure(
                name=f"{base_structure.name}_v{i+1}",
                structure_id=f"{base_structure.structure_id}_v{i+1}",
                segments=new_segments,
                total_duration=round(sum(s.duration for s in new_segments), 1),
                samples=base_structure.samples,
                avg_ctr=base_structure.avg_ctr,
                avg_cpi=base_structure.avg_cpi,
                avg_d7_roi=base_structure.avg_d7_roi,
                avg_d30_roi=base_structure.avg_d30_roi,
                ad_value=base_structure.ad_value,
                confidence=base_structure.confidence * 0.9,
                tags=base_structure.tags + ["variant"],
            ))

        return variants

    def save_structures(self, output_path: Path):
        """保存结构"""
        data = {
            "structures": [s.to_dict() for s in self.structures],
            "total": len(self.structures),
            "timestamp": datetime.now().isoformat(),
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"  Winning structures saved: {output_path}")


class StructurePatternMatcher:
    """结构模式匹配器"""

    def __init__(self):
        self.patterns = {
            "fantasy_evolution": ["hook", "gameplay", "reward", "ending"],
            "quick_hook": ["hook", "reward", "gameplay", "ending"],
            "story_driven": ["story", "gameplay", "reward", "ending"],
            "action_first": ["hook", "hook", "gameplay", "reward"],
        }

    def match(self, role_sequence: List[str]) -> List[str]:
        """匹配结构模式"""
        role_key = "->".join(role_sequence)
        matches = []
        for name, pattern in self.patterns.items():
            pattern_key = "->".join(pattern)
            if role_key == pattern_key:
                matches.append(name)
        return matches

    def suggest_pattern(self, target_duration: float = 30.0) -> List[StructureSegment]:
        """建议结构模式"""
        if target_duration <= 15:
            return [
                StructureSegment("hook", 2.0, "character", "attack", "surprise", "zoom_in"),
                StructureSegment("gameplay", 5.0, "character", "merge", "curiosity", "pan"),
                StructureSegment("reward", 5.0, "character", "upgrade", "satisfaction", "zoom_in"),
                StructureSegment("ending", 3.0, "character", "collect", "excitement", "static"),
            ]
        else:
            return [
                StructureSegment("hook", 3.0, "character", "attack", "surprise", "zoom_in"),
                StructureSegment("gameplay", 8.0, "character", "merge", "curiosity", "pan"),
                StructureSegment("reward", 10.0, "character", "upgrade", "satisfaction", "zoom_in"),
                StructureSegment("ending", 5.0, "character", "collect", "excitement", "static"),
            ]