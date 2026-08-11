"""Shot Database — Shot 素材库管理 V3.9.1

功能：
- 存储和管理所有真实提取的 shot
- 支持 VisualDNA（基于真实视觉分析）
- 按角色、主体、动作、情绪等多维度索引
- 支持相似性搜索和多样性选择
- 支持按表现分排序

对比 V3.9：
❌ ShotDNA（基于文件名推断）
✅ VisualDNA（基于真实画面分析）
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from dataclasses import asdict

import numpy as np

from .shot_analyzer import ShotDNA
from .visual_dna_extractor import VisualDNA


class ShotDatabase:
    """Shot 素材库 V3.9.1 — 支持 VisualDNA"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("shot_library.json")
        self.shots: Dict[str, Union[ShotDNA, VisualDNA]] = {}
        self.indexes = {
            "by_role": {},
            "by_subject": {},
            "by_action": {},
            "by_emotion": {},
            "by_camera": {},
            "by_source_video": {},
            "by_scene": {},
            "by_motion_level": {},
            "by_visual_hook": {},
        }
        self._load()

    def add(self, shot: Union[ShotDNA, VisualDNA]):
        """添加 shot（支持 ShotDNA 和 VisualDNA）"""
        self.shots[shot.shot_id] = shot
        self._update_indexes(shot)

    def add_many(self, shots: List[Union[ShotDNA, VisualDNA]]):
        """批量添加"""
        for shot in shots:
            self.add(shot)

    def get(self, shot_id: str) -> Optional[Union[ShotDNA, VisualDNA]]:
        """获取 shot"""
        return self.shots.get(shot_id)

    def query(self,
              role: Optional[str] = None,
              subject: Optional[str] = None,
              action: Optional[str] = None,
              emotion: Optional[str] = None,
              camera: Optional[str] = None,
              scene: Optional[str] = None,
              motion_level: Optional[str] = None,
              visual_hook: Optional[bool] = None,
              min_visual_score: Optional[int] = None,
              min_performance_score: Optional[int] = None,
              min_hook_strength: Optional[float] = None,
              limit: int = 100) -> List[Union[ShotDNA, VisualDNA]]:
        """多维度查询（支持 VisualDNA 字段）"""
        results = list(self.shots.values())

        if role:
            results = [s for s in results if getattr(s, 'role', '') == role]
        if subject:
            subjects = getattr(results[0], 'subjects', []) if results else []
            if isinstance(subjects, list):
                results = [s for s in results if subject in getattr(s, 'subjects', [])]
            else:
                results = [s for s in results if getattr(s, 'subject', '') == subject]
        if action:
            actions = getattr(results[0], 'actions', []) if results else []
            if isinstance(actions, list):
                results = [s for s in results if action in getattr(s, 'actions', [])]
            else:
                results = [s for s in results if getattr(s, 'action', '') == action]
        if emotion:
            emotions = getattr(results[0], 'emotions', []) if results else []
            if isinstance(emotions, list):
                results = [s for s in results if emotion in getattr(s, 'emotions', [])]
            else:
                results = [s for s in results if getattr(s, 'emotion', '') == emotion]
        if camera:
            results = [s for s in results if getattr(s, 'camera', '') == camera]
        if scene:
            results = [s for s in results if getattr(s, 'scene', '') == scene]
        if motion_level:
            results = [s for s in results if getattr(s, 'motion_level', '') == motion_level]
        if visual_hook is not None:
            results = [s for s in results if getattr(s, 'visual_hook', False) == visual_hook]
        if min_visual_score is not None:
            results = [s for s in results if getattr(s, 'visual_quality', 0) >= min_visual_score]
        if min_performance_score is not None:
            results = [s for s in results if getattr(s, 'performance_score', 0) >= min_performance_score]
        if min_hook_strength is not None:
            results = [s for s in results if getattr(s, 'hook_strength', 0) >= min_hook_strength]

        results.sort(key=lambda s: -getattr(s, 'performance_score', 0))
        return results[:limit]

    def get_by_role(self, role: str, limit: int = 100) -> List[Union[ShotDNA, VisualDNA]]:
        """按角色获取"""
        return self.query(role=role, limit=limit)

    def get_top_hooks(self, min_hook_strength: float = 70.0,
                      limit: int = 50) -> List[Union[ShotDNA, VisualDNA]]:
        """获取 Hook 强度高的 shots"""
        return self.query(
            role="hook",
            min_hook_strength=min_hook_strength,
            limit=limit
        )

    def get_top_performing(self, role: Optional[str] = None,
                           min_score: int = 70,
                           limit: int = 50) -> List[Union[ShotDNA, VisualDNA]]:
        """获取表现最好的 shots"""
        return self.query(role=role, min_performance_score=min_score, limit=limit)

    def get_diverse_selection(self, role: str, n: int = 5) -> List[Union[ShotDNA, VisualDNA]]:
        """获取多样化的 shot 选择（避免过于相似）"""
        candidates = self.get_by_role(role, limit=100)
        if len(candidates) <= n:
            return candidates

        selected = []
        subjects_seen = set()
        scenes_seen = set()

        for shot in candidates:
            shot_subjects = getattr(shot, 'subjects', [getattr(shot, 'subject', '')])
            shot_scene = getattr(shot, 'scene', '')

            if isinstance(shot_subjects, list):
                subject_key = tuple(sorted(shot_subjects))
            else:
                subject_key = shot_subjects

            is_diverse = subject_key not in subjects_seen or shot_scene not in scenes_seen
            if is_diverse or len(selected) < n // 2:
                selected.append(shot)
                subjects_seen.add(subject_key)
                scenes_seen.add(shot_scene)
            if len(selected) >= n:
                break

        return selected

    def get_shots_with_subject(self, subject: str,
                               limit: int = 50) -> List[Union[ShotDNA, VisualDNA]]:
        """获取包含特定主体的 shots"""
        return self.query(subject=subject, limit=limit)

    def get_shots_with_action(self, action: str,
                              limit: int = 50) -> List[Union[ShotDNA, VisualDNA]]:
        """获取包含特定动作的 shots"""
        return self.query(action=action, limit=limit)

    def get_stats(self) -> dict:
        """获取统计信息（增强版）"""
        if not self.shots:
            return {"total": 0, "version": "V3.9.1"}

        roles = {}
        subjects = {}
        scenes = {}
        motion_levels = {}
        avg_visual = 0
        avg_performance = 0
        avg_hook_strength = 0
        visual_hook_count = 0
        dna_type_count = {"ShotDNA": 0, "VisualDNA": 0}

        for shot in self.shots.values():
            role = getattr(shot, 'role', 'unknown')
            roles[role] = roles.get(role, 0) + 1

            shot_subjects = getattr(shot, 'subjects', [getattr(shot, 'subject', '')])
            if isinstance(shot_subjects, list):
                for s in shot_subjects:
                    subjects[s] = subjects.get(s, 0) + 1
            else:
                subjects[shot_subjects] = subjects.get(shot_subjects, 0) + 1

            scene = getattr(shot, 'scene', 'unknown')
            scenes[scene] = scenes.get(scene, 0) + 1

            motion_level = getattr(shot, 'motion_level', 'unknown')
            motion_levels[motion_level] = motion_levels.get(motion_level, 0) + 1

            avg_visual += getattr(shot, 'visual_quality', getattr(shot, 'visual_score', 0))
            avg_performance += getattr(shot, 'performance_score', 0)
            avg_hook_strength += getattr(shot, 'hook_strength', 0)

            if getattr(shot, 'visual_hook', False):
                visual_hook_count += 1

            if isinstance(shot, VisualDNA):
                dna_type_count["VisualDNA"] += 1
            else:
                dna_type_count["ShotDNA"] += 1

        total = len(self.shots)
        return {
            "total": total,
            "version": "V3.9.1",
            "dna_type_distribution": dna_type_count,
            "avg_visual_score": round(avg_visual / total, 1),
            "avg_performance_score": round(avg_performance / total, 1),
            "avg_hook_strength": round(avg_hook_strength / total, 1),
            "visual_hook_ratio": round(visual_hook_count / total, 3),
            "role_distribution": roles,
            "subject_distribution": subjects,
            "scene_distribution": scenes,
            "motion_level_distribution": motion_levels,
        }

    def _update_indexes(self, shot: Union[ShotDNA, VisualDNA]):
        """更新索引（支持 VisualDNA 的多值字段）"""
        if isinstance(shot, VisualDNA):
            self._update_indexes_visual_dna(shot)
        else:
            self._update_indexes_shot_dna(shot)

    def _update_indexes_visual_dna(self, shot: VisualDNA):
        """更新 VisualDNA 索引"""
        if shot.shot_id not in self.indexes["by_source_video"].get(shot.source_video, []):
            self.indexes["by_source_video"].setdefault(shot.source_video, []).append(shot.shot_id)

        for subject in shot.subjects:
            if shot.shot_id not in self.indexes["by_subject"].get(subject, []):
                self.indexes["by_subject"].setdefault(subject, []).append(shot.shot_id)

        for action in shot.actions:
            if shot.shot_id not in self.indexes["by_action"].get(action, []):
                self.indexes["by_action"].setdefault(action, []).append(shot.shot_id)

        for emotion in shot.emotions:
            if shot.shot_id not in self.indexes["by_emotion"].get(emotion, []):
                self.indexes["by_emotion"].setdefault(emotion, []).append(shot.shot_id)

        if shot.shot_id not in self.indexes["by_camera"].get(shot.camera, []):
            self.indexes["by_camera"].setdefault(shot.camera, []).append(shot.shot_id)

        if shot.shot_id not in self.indexes["by_scene"].get(shot.scene, []):
            self.indexes["by_scene"].setdefault(shot.scene, []).append(shot.shot_id)

        if shot.shot_id not in self.indexes["by_motion_level"].get(shot.motion_level, []):
            self.indexes["by_motion_level"].setdefault(shot.motion_level, []).append(shot.shot_id)

        hook_key = str(shot.visual_hook)
        if shot.shot_id not in self.indexes["by_visual_hook"].get(hook_key, []):
            self.indexes["by_visual_hook"].setdefault(hook_key, []).append(shot.shot_id)

    def _update_indexes_shot_dna(self, shot: ShotDNA):
        """更新 ShotDNA 索引（兼容旧格式）"""
        for field, index in [
            ("role", "by_role"),
            ("subject", "by_subject"),
            ("action", "by_action"),
            ("emotion", "by_emotion"),
            ("camera", "by_camera"),
            ("source_video", "by_source_video"),
        ]:
            value = getattr(shot, field)
            if value not in self.indexes[index]:
                self.indexes[index][value] = []
            if shot.shot_id not in self.indexes[index][value]:
                self.indexes[index][value].append(shot.shot_id)

    def _convert_to_json_serializable(self, obj):
        """转换为 JSON 可序列化类型"""
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: self._convert_to_json_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._convert_to_json_serializable(item) for item in obj]
        return obj

    def save(self):
        """保存数据库（支持 VisualDNA）"""
        data = {
            "version": "V3.9.1",
            "shots": {},
            "stats": self.get_stats(),
            "timestamp": datetime.now().isoformat(),
        }

        for sid, shot in self.shots.items():
            if isinstance(shot, VisualDNA):
                shot_dict = self._convert_to_json_serializable(asdict(shot))
                data["shots"][sid] = {
                    "type": "VisualDNA",
                    **shot_dict
                }
            else:
                data["shots"][sid] = {
                    "type": "ShotDNA",
                    **shot.to_dict()
                }

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        """加载数据库（支持新旧格式）"""
        if not self.db_path.exists():
            return
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for sid, sdata in data.get("shots", {}).items():
                shot_type = sdata.pop("type", "ShotDNA")
                try:
                    if shot_type == "VisualDNA":
                        shot = VisualDNA(**sdata)
                    else:
                        shot = ShotDNA(**sdata)
                    self.shots[sid] = shot
                    self._update_indexes(shot)
                except TypeError:
                    pass
        except (json.JSONDecodeError, TypeError):
            pass

    def export_for_training(self) -> List[dict]:
        """导出训练数据"""
        results = []
        for shot in self.shots.values():
            if isinstance(shot, VisualDNA):
                results.append(asdict(shot))
            else:
                results.append(shot.to_dict())
        return results

    def migrate_to_visual_dna(self, video_path: Path,
                              shot_boundaries) -> None:
        """将旧的 ShotDNA 迁移为 VisualDNA"""
        from .visual_dna_extractor import VisualDNAExtractor
        extractor = VisualDNAExtractor()

        migrated_count = 0
        for shot_id, shot in list(self.shots.items()):
            if isinstance(shot, ShotDNA):
                video_id = shot.source_video
                video_file = video_path / f"{video_id}.mp4"

                if video_file.exists():
                    boundary = next((b for b in shot_boundaries
                                     if b.shot_id == shot_id), None)
                    if boundary:
                        visual_dna = extractor.extract(
                            video_file, boundary, shot_id, video_id
                        )
                        self.shots[shot_id] = visual_dna
                        self._update_indexes(visual_dna)
                        migrated_count += 1

        print(f"[ShotDatabase] Migrated {migrated_count} shots to VisualDNA")