"""Winner Structure Miner V2 — 真实广告结构学习引擎

对比 V3.9：
❌ 学习固定模板（CTR高 → 套模板）
✅ 真实分析：Winner视频 → 拆Shot → 分析结构

例如：
Winner A:
0-2s:   Dragon danger → hook
2-5s:   Player merge → gameplay
5-8s:   Huge evolution → reward
8-12s:  Reward → reward
12-15s: CTA → cta

生成：
{
  "structure_id": "dragon_merge_001",
  "hook": "danger",
  "gameplay": "merge",
  "reward": "evolution",
  "cta": "download"
}

核心功能：
1. 从真实 Winner 视频拆解 Shot
2. 分析每个 Shot 的角色（hook/gameplay/reward/cta）
3. 学习结构模式
4. 生成可复用的结构模板
"""
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import Counter

import numpy as np


@dataclass
class ShotStructure:
    """单个 Shot 的结构信息"""
    shot_id: str
    role: str
    start_time: float
    end_time: float
    duration: float
    subject: str
    action: str
    emotion: str
    visual_hook: bool
    hook_strength: float


@dataclass
class VideoStructure:
    """视频结构分析结果"""
    video_id: str
    total_duration: float
    shots: List[ShotStructure]
    structure_sequence: List[str]
    structure_pattern: str


@dataclass
class StructureTemplate:
    """结构模板"""
    structure_id: str
    name: str
    pattern: str
    hook_type: str
    gameplay_type: str
    reward_type: str
    cta_type: str
    shot_count: int
    avg_duration: float
    usage_count: int = 0
    avg_performance: float = 0.0


class StructureMinerV2:
    """Winner 结构学习器 V2"""

    STRUCTURE_PATTERNS = [
        "hook-gameplay-reward-cta",
        "hook-gameplay-reward-reward-cta",
        "hook-gameplay-gameplay-reward-cta",
        "hook-story-gameplay-reward-cta",
        "hook-danger-gameplay-reward-cta",
        "gameplay-reward-cta",
        "hook-reward-cta",
    ]

    def __init__(self):
        self.templates: Dict[str, StructureTemplate] = {}
        self.video_structures: Dict[str, VideoStructure] = {}
        self._load_templates()

    def mine_structure(self, video_id: str, shots_data) -> VideoStructure:
        """从 Shot 数据学习视频结构"""
        shot_structures = []
        structure_sequence = []

        for shot in shots_data:
            role = getattr(shot, 'role', 'unknown')
            subjects = getattr(shot, 'subjects', [getattr(shot, 'subject', '')])
            actions = getattr(shot, 'actions', [getattr(shot, 'action', '')])
            emotions = getattr(shot, 'emotions', [getattr(shot, 'emotion', '')])

            shot_struct = ShotStructure(
                shot_id=shot.shot_id,
                role=role,
                start_time=getattr(shot, 'start_time', 0.0),
                end_time=getattr(shot, 'end_time', 0.0),
                duration=getattr(shot, 'duration', 0.0),
                subject=subjects[0] if isinstance(subjects, list) and subjects else str(subjects),
                action=actions[0] if isinstance(actions, list) and actions else str(actions),
                emotion=emotions[0] if isinstance(emotions, list) and emotions else str(emotions),
                visual_hook=getattr(shot, 'visual_hook', False),
                hook_strength=getattr(shot, 'hook_strength', 0.0),
            )

            shot_structures.append(shot_struct)
            structure_sequence.append(role)

        total_duration = max(s.end_time for s in shot_structures) if shot_structures else 0.0
        structure_pattern = self._infer_pattern(structure_sequence)

        video_structure = VideoStructure(
            video_id=video_id,
            total_duration=total_duration,
            shots=shot_structures,
            structure_sequence=structure_sequence,
            structure_pattern=structure_pattern,
        )

        self.video_structures[video_id] = video_structure
        self._update_templates(video_structure)

        return video_structure

    def mine_from_directory(self, video_dir: Path, shot_database) -> Dict[str, VideoStructure]:
        """从目录批量学习结构"""
        results = {}

        for video_id, shots in shot_database.shots.items():
            video_shots = [s for s in shot_database.shots.values()
                          if getattr(s, 'source_video', '') == video_id.split('_shot')[0]]
            if video_shots:
                structure = self.mine_structure(video_id.split('_shot')[0], video_shots)
                results[video_id.split('_shot')[0]] = structure

        return results

    def _infer_pattern(self, sequence: List[str]) -> str:
        """推断结构模式"""
        if not sequence:
            return "unknown"

        cleaned = [r for r in sequence if r in ["hook", "gameplay", "reward", "story", "ending", "cta"]]
        if not cleaned:
            return "unknown"

        pattern = "-".join(cleaned)

        best_match = "unknown"
        best_score = 0

        for known_pattern in self.STRUCTURE_PATTERNS:
            known_roles = known_pattern.split("-")
            score = self._pattern_match_score(cleaned, known_roles)
            if score > best_score:
                best_score = score
                best_match = known_pattern

        if best_score > 0.5:
            return best_match
        return pattern

    def _pattern_match_score(self, sequence: List[str], pattern_roles: List[str]) -> float:
        """计算模式匹配分数"""
        score = 0
        min_len = min(len(sequence), len(pattern_roles))

        for i in range(min_len):
            if sequence[i] == pattern_roles[i]:
                score += 1

        return score / max(len(sequence), len(pattern_roles))

    def _update_templates(self, video_structure: VideoStructure):
        """更新结构模板"""
        pattern = video_structure.structure_pattern
        if pattern == "unknown":
            return

        template_id = f"struct_{hash(pattern) % 10000:04d}"

        if template_id not in self.templates:
            self.templates[template_id] = self._create_template(video_structure, template_id)
        else:
            self.templates[template_id].usage_count += 1

    def _create_template(self, video_structure: VideoStructure, template_id: str) -> StructureTemplate:
        """创建结构模板"""
        hook_type = self._extract_role_type(video_structure, "hook")
        gameplay_type = self._extract_role_type(video_structure, "gameplay")
        reward_type = self._extract_role_type(video_structure, "reward")
        cta_type = self._extract_role_type(video_structure, "cta")

        avg_duration = np.mean([s.duration for s in video_structure.shots])

        return StructureTemplate(
            structure_id=template_id,
            name=self._generate_template_name(hook_type, gameplay_type),
            pattern=video_structure.structure_pattern,
            hook_type=hook_type,
            gameplay_type=gameplay_type,
            reward_type=reward_type,
            cta_type=cta_type,
            shot_count=len(video_structure.shots),
            avg_duration=round(avg_duration, 2),
            usage_count=1,
        )

    def _extract_role_type(self, video_structure: VideoStructure, role: str) -> str:
        """提取指定角色的类型"""
        role_shots = [s for s in video_structure.shots if s.role == role]
        if not role_shots:
            return "unknown"

        actions = [s.action for s in role_shots if s.action]
        if actions:
            return Counter(actions).most_common(1)[0][0]

        emotions = [s.emotion for s in role_shots if s.emotion]
        if emotions:
            return Counter(emotions).most_common(1)[0][0]

        subjects = [s.subject for s in role_shots if s.subject]
        if subjects:
            return Counter(subjects).most_common(1)[0][0]

        return "unknown"

    def _generate_template_name(self, hook_type: str, gameplay_type: str) -> str:
        """生成模板名称"""
        name_parts = []
        if hook_type != "unknown":
            name_parts.append(hook_type)
        if gameplay_type != "unknown":
            name_parts.append(gameplay_type)

        if name_parts:
            return "_".join(name_parts)
        return "generic_structure"

    def get_top_templates(self, min_usage: int = 1, limit: int = 10) -> List[StructureTemplate]:
        """获取最常用的结构模板"""
        templates = [t for t in self.templates.values() if t.usage_count >= min_usage]
        templates.sort(key=lambda t: -t.usage_count)
        return templates[:limit]

    def get_template_by_pattern(self, pattern: str) -> Optional[StructureTemplate]:
        """按模式获取模板"""
        for template in self.templates.values():
            if template.pattern == pattern:
                return template
        return None

    def generate_structure_report(self) -> Dict:
        """生成结构分析报告"""
        pattern_counts = Counter()
        role_distribution = Counter()
        avg_shot_count = 0
        avg_duration = 0

        for video_id, structure in self.video_structures.items():
            pattern_counts[structure.structure_pattern] += 1

            for shot in structure.shots:
                role_distribution[shot.role] += 1

            avg_shot_count += len(structure.shots)
            avg_duration += structure.total_duration

        total_videos = len(self.video_structures)
        if total_videos > 0:
            avg_shot_count /= total_videos
            avg_duration /= total_videos

        return {
            "total_videos_analyzed": total_videos,
            "total_templates": len(self.templates),
            "avg_shot_count": round(avg_shot_count, 2),
            "avg_video_duration": round(avg_duration, 2),
            "pattern_distribution": dict(pattern_counts),
            "role_distribution": dict(role_distribution),
            "top_templates": [asdict(t) for t in self.get_top_templates(limit=5)],
            "timestamp": datetime.now().isoformat(),
        }

    def save_templates(self, output_path: Path):
        """保存结构模板"""
        data = {
            "version": "V3.9.1",
            "templates": {tid: asdict(t) for tid, t in self.templates.items()},
            "video_structures": {vid: {
                "video_id": vs.video_id,
                "total_duration": vs.total_duration,
                "structure_pattern": vs.structure_pattern,
                "structure_sequence": vs.structure_sequence,
                "shots": [asdict(s) for s in vs.shots],
            } for vid, vs in self.video_structures.items()},
            "stats": self.generate_structure_report(),
            "timestamp": datetime.now().isoformat(),
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_templates(self):
        """加载结构模板"""
        template_path = Path("winner_structure_templates.json")
        if template_path.exists():
            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for tid, tdata in data.get("templates", {}).items():
                    self.templates[tid] = StructureTemplate(**tdata)
            except (json.JSONDecodeError, TypeError):
                pass

    def suggest_remix_structure(self, target_duration: float = 15.0) -> StructureTemplate:
        """推荐混剪结构"""
        if not self.templates:
            return self._create_default_template(target_duration)

        templates = sorted(self.templates.values(), key=lambda t: -t.usage_count)

        for template in templates:
            if abs(template.avg_duration - target_duration) < 5:
                return template

        return templates[0]

    def _create_default_template(self, duration: float) -> StructureTemplate:
        """创建默认模板"""
        segments = duration / 4
        return StructureTemplate(
            structure_id="struct_default",
            name="default_15s",
            pattern="hook-gameplay-reward-cta",
            hook_type="surprise",
            gameplay_type="merge",
            reward_type="evolution",
            cta_type="download",
            shot_count=4,
            avg_duration=round(segments, 2),
            usage_count=0,
        )