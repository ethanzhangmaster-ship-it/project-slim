"""Shot Extractor V3.9.1 — 从视频中提取真实 Shots 并构建素材库

对比 V3.9：
❌ ShotDetector（固定时间切分）
❌ ShotAnalyzer（文件名推断）
✅ RealShotDetector（真实帧分析）
✅ VisualDNAExtractor（CLIP/OpenCV视觉分析）

输入：历史视频文件
输出：shot_library.json（包含真实 VisualDNA）

流程：
1. 遍历所有视频
2. RealShotDetector 检测真实镜头边界（帧差+直方图+光流）
3. VisualDNAExtractor 提取真实视觉 DNA
4. Shot Role Classifier 分类角色
5. 存入 Shot Database（支持 VisualDNA）
6. 生成 Shot Embedding
"""
import json
from pathlib import Path
from typing import List, Dict, Optional, Union
from datetime import datetime
from dataclasses import asdict

from .real_shot_detector import RealShotDetector, RealShotBoundary
from .visual_dna_extractor import VisualDNAExtractor, VisualDNA
from .shot_role_classifier import ShotRoleClassifier
from .shot_database import ShotDatabase
from .shot_embedding import ShotEmbedding


class ShotExtractor:
    """Shot 提取器 V3.9.1"""

    def __init__(self,
                 db_path: Optional[Path] = None,
                 output_dir: Optional[Path] = None,
                 use_real_detector: bool = True):
        self.use_real_detector = use_real_detector
        if use_real_detector:
            self.detector = RealShotDetector()
        else:
            from .shot_detector import ShotDetector
            self.detector = ShotDetector()

        self.dna_extractor = VisualDNAExtractor()
        self.classifier = ShotRoleClassifier()
        self.database = ShotDatabase(db_path)
        self.embedding = ShotEmbedding()
        self.output_dir = output_dir or Path("shot_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_from_video(self, video_path: Path, video_id: Optional[str] = None) -> List[Union[VisualDNA, dict]]:
        """从单个视频提取真实 shots（使用 RealShotDetector + VisualDNAExtractor）"""
        video_name = video_path.stem
        video_id = video_id or video_name

        print(f"  [ShotExtractor] Processing: {video_name}")

        if not video_path.exists():
            print(f"    Error: Video not found - {video_path}")
            return []

        # Step 1: 检测真实 shot 边界
        if self.use_real_detector:
            boundaries = self.detector.detect(video_path, video_id)
        else:
            from .shot_detector import ShotDetector
            detector = ShotDetector()
            boundaries = detector.detect(video_path)

        print(f"    Detected {len(boundaries)} shots")

        if not boundaries:
            return []

        # Step 2: 提取真实视觉 DNA
        dna_list = self.dna_extractor.batch_extract(video_path, boundaries, video_id)
        print(f"    Extracted VisualDNA for {len(dna_list)} shots")

        # Step 3: 角色分类（基于 VisualDNA 特征）
        video_duration = max(b.end_time for b in boundaries) if boundaries else 30.0

        for i, dna in enumerate(dna_list):
            if hasattr(boundaries[i], 'start_time'):
                position = boundaries[i].start_time / video_duration
            else:
                position = 0.5

            emotions = dna.emotions if isinstance(dna.emotions, list) else [dna.emotions]
            emotion = emotions[0] if emotions else "curiosity"

            role_probs = self.classifier.classify(
                duration=dna.duration,
                emotion=emotion,
                camera=dna.camera,
                visual_score=dna.visual_quality,
                position_in_video=position,
            )
            dna.role = max(role_probs, key=role_probs.get)

        # Step 4: 上下文重新分类
        dna_list = self._reclassify_with_context(dna_list, video_duration)

        return dna_list

    def _reclassify_with_context(self, dna_list: List[VisualDNA], video_duration: float) -> List[VisualDNA]:
        """结合上下文重新分类"""
        if len(dna_list) < 2:
            return dna_list

        for i, dna in enumerate(dna_list):
            if hasattr(dna, 'start_time'):
                position = dna.start_time / video_duration
            else:
                position = i / len(dna_list)

            emotions = dna.emotions if isinstance(dna.emotions, list) else [dna.emotions]
            emotion = emotions[0] if emotions else "curiosity"

            role = self.classifier.predict_role(
                duration=dna.duration,
                emotion=emotion,
                camera=dna.camera,
                visual_score=dna.visual_quality,
                position_in_video=position,
            )
            dna.role = role

        if len(dna_list) >= 3:
            if dna_list[0].role not in ["hook", "story"]:
                dna_list[0].role = "hook"
            if dna_list[-1].role not in ["ending", "reward"]:
                dna_list[-1].role = "ending"

        return dna_list

    def extract_from_directory(self, video_dir: Path,
                               pattern: str = "*.mp4",
                               max_videos: Optional[int] = None) -> Dict[str, List[VisualDNA]]:
        """从目录批量提取（真实视觉分析）"""
        all_shots = {}
        video_files = list(video_dir.glob(pattern))

        if max_videos:
            video_files = video_files[:max_videos]

        print(f"[ShotExtractor V3.9.1] Found {len(video_files)} videos in {video_dir}")

        total_shots = 0
        for video_path in video_files:
            video_id = video_path.stem
            shots = self.extract_from_video(video_path, video_id)
            all_shots[video_id] = shots

            self.database.add_many(shots)
            total_shots += len(shots)

            print(f"    Video: {video_id} -> {len(shots)} shots")

        print(f"[ShotExtractor] Total extracted: {total_shots} shots from {len(video_files)} videos")

        self._generate_embeddings()
        self.database.save()
        self._save_library_json(all_shots)

        return all_shots

    def extract_from_list(self, video_paths: List[Path]) -> Dict[str, List[VisualDNA]]:
        """从视频路径列表提取"""
        all_shots = {}

        print(f"[ShotExtractor] Processing {len(video_paths)} videos")

        for video_path in video_paths:
            video_id = video_path.stem
            shots = self.extract_from_video(video_path, video_id)
            all_shots[video_id] = shots
            self.database.add_many(shots)

        self._generate_embeddings()
        self.database.save()
        self._save_library_json(all_shots)

        return all_shots

    def _generate_embeddings(self):
        """为所有 shot 生成 embedding"""
        shots = list(self.database.shots.values())
        if not shots:
            return

        embeddings = self.embedding.batch_encode(shots)
        for shot, emb in zip(shots, embeddings):
            self.embedding.embeddings[shot.shot_id] = emb

        print(f"  Generated {len(embeddings)} embeddings")

    def _save_library_json(self, all_shots: Dict[str, List[VisualDNA]]):
        """保存 shot_library.json（支持 VisualDNA）"""
        library = {
            "version": "V3.9.1",
            "metadata": {
                "total_videos": len(all_shots),
                "total_shots": sum(len(s) for s in all_shots.values()),
                "timestamp": datetime.now().isoformat(),
                "extraction_method": "real_video_analysis",
            },
            "videos": {},
        }

        for video_id, shots in all_shots.items():
            library["videos"][video_id] = {
                "shot_count": len(shots),
                "shots": [],
            }
            for shot in shots:
                if isinstance(shot, VisualDNA):
                    library["videos"][video_id]["shots"].append(asdict(shot))
                elif hasattr(shot, 'to_dict'):
                    library["videos"][video_id]["shots"].append(shot.to_dict())
                else:
                    library["videos"][video_id]["shots"].append(dict(shot))

        library_path = self.output_dir / "shot_library.json"
        with open(library_path, "w", encoding="utf-8") as f:
            json.dump(library, f, ensure_ascii=False, indent=2)

        print(f"  Shot library saved: {library_path}")

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.database.get_stats()

    def find_similar_shots(self, shot_id: str, top_k: int = 5) -> List:
        """查找相似 shot"""
        query_shot = self.database.get(shot_id)
        if not query_shot:
            return []

        candidates = list(self.database.shots.values())
        return self.embedding.find_similar(query_shot, candidates, top_k)

    def get_shots_for_role(self, role: str, min_performance: int = 70,
                           limit: int = 20) -> List[VisualDNA]:
        """获取指定角色的 shots"""
        return self.database.query(
            role=role,
            min_performance_score=min_performance,
            limit=limit
        )

    def get_top_hooks(self, min_hook_strength: float = 70.0,
                      limit: int = 20) -> List[VisualDNA]:
        """获取 Hook 强度高的 shots"""
        return self.database.get_top_hooks(min_hook_strength, limit)


def build_shot_library(video_dir: str,
                       db_path: Optional[str] = None,
                       output_dir: Optional[str] = None,
                       max_videos: Optional[int] = None) -> ShotExtractor:
    """构建 shot 素材库（便捷函数）"""
    extractor = ShotExtractor(
        db_path=Path(db_path) if db_path else None,
        output_dir=Path(output_dir) if output_dir else None,
        use_real_detector=True,
    )

    video_path = Path(video_dir)
    if video_path.is_dir():
        extractor.extract_from_directory(video_path, max_videos=max_videos)
    else:
        print(f"Error: {video_dir} is not a directory")

    return extractor


def build_shot_library_from_list(video_paths: List[str],
                                 db_path: Optional[str] = None,
                                 output_dir: Optional[str] = None) -> ShotExtractor:
    """从视频路径列表构建 shot 素材库"""
    extractor = ShotExtractor(
        db_path=Path(db_path) if db_path else None,
        output_dir=Path(output_dir) if output_dir else None,
        use_real_detector=True,
    )

    path_list = [Path(p) for p in video_paths if Path(p).exists()]
    extractor.extract_from_list(path_list)

    return extractor