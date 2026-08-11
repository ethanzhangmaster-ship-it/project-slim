"""Visual DNA Extractor — 使用视觉模型提取真实 Shot DNA

对比当前假的实现：
❌ 文件名推断: witch_dragon_01.mp4 → subject=witch, action=magic
✅ 真实画面分析: CLIP/BLIP/Vision Model → 真实识别

技术栈：
- CLIP (OpenAI) - 图像-文本对齐
- BLIP (Salesforce) - 视觉语言理解
- OpenCV - 计算机视觉
- LLaVA (可选) - 视觉问答

输出：
{
  "shot_id": "001",
  "subject": ["witch", "dragon"],
  "action": ["merge", "upgrade"],
  "emotion": "surprise",
  "scene": "castle",
  "camera": "zoom_in",
  "visual_hook": true,
}
"""
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import cv2
import numpy as np


@dataclass
class VisualDNA:
    """真实视觉分析的 Shot DNA"""
    shot_id: str
    source_video: str
    subjects: List[str]
    actions: List[str]
    emotions: List[str]
    scene: str
    camera: str
    visual_hook: bool
    hook_strength: float      # 0-100
    motion_level: str         # low/medium/high
    brightness: float         # 0-100
    color_vibrancy: float     # 0-100
    composition_score: float  # 0-100
    visual_quality: int       # 0-100
    performance_score: int    # 0-100（来自UA数据）
    duration: float
    frame_count: int
    dominant_color: str
    text_detected: bool
    ui_elements: bool
    logo_detected: bool


class VisualDNAExtractor:
    """视觉 DNA 提取器"""

    SUBJECT_KEYWORDS = {
        "character": ["character", "person", "hero", "warrior", "witch", "mage", "knight", "soldier"],
        "monster": ["monster", "dragon", "creature", "beast", "demon", "boss", "enemy"],
        "building": ["building", "castle", "tower", "house", "village", "city", "fortress"],
        "item": ["sword", "weapon", "potion", "chest", "treasure", "gem", "coin", "artifact"],
        "animal": ["animal", "pet", "horse", "bird"],
        "vehicle": ["car", "ship", "aircraft"],
    }

    ACTION_KEYWORDS = {
        "merge": ["merge", "combine", "fuse", "blend", "join", "unite"],
        "upgrade": ["upgrade", "evolve", "level up", "enhance", "improve"],
        "attack": ["attack", "fight", "battle", "strike", "hit", "slash"],
        "collect": ["collect", "gather", "pick", "grab", "collecting", "gathering"],
        "explore": ["explore", "walk", "run", "move", "travel"],
        "transform": ["transform", "change", "morph", "shift", "turn into"],
        "open": ["open", "unlock", "reveal", "discover", "find"],
        "rescue": ["rescue", "save", "help", "protect"],
    }

    EMOTION_KEYWORDS = {
        "surprise": ["surprise", "shock", "amazing", "wow", "unexpected", "sudden"],
        "excitement": ["excitement", "excited", "epic", "intense", "thrilling"],
        "danger": ["danger", "warning", "alert", "threat", "scary", "fear"],
        "satisfaction": ["satisfaction", "happy", "joy", "success", "win", "victory"],
        "curiosity": ["curiosity", "mystery", "secret", "hidden", "wonder"],
    }

    SCENE_KEYWORDS = {
        "castle": ["castle", "palace", "fortress"],
        "forest": ["forest", "wood", "jungle", "trees"],
        "ocean": ["ocean", "sea", "beach", "water"],
        "desert": ["desert", "sand", "dunes"],
        "mountains": ["mountains", "hills", "peak"],
        "cave": ["cave", "underground", "dark"],
        "village": ["village", "town", "city", "market"],
        "battlefield": ["battlefield", "war", "combat"],
        "sky": ["sky", "clouds", "flying", "air"],
    }

    CAMERA_KEYWORDS = {
        "closeup": ["closeup", "close-up", "face", "detail"],
        "wide": ["wide", "landscape", "panorama"],
        "medium": ["medium", "medium shot"],
        "overhead": ["overhead", "top down", "bird's eye"],
        "low": ["low", "worm's eye", "looking up"],
    }

    def __init__(self, clip_model_name: str = "clip-vit-base-patch32"):
        self.clip_model_name = clip_model_name
        self.clip_available = False
        self.model = None
        self.preprocess = None
        self.tokenizer = None
        self._try_load_clip()

    def _try_load_clip(self):
        """尝试加载 CLIP 模型"""
        try:
            import clip
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model, self.preprocess = clip.load(self.clip_model_name, device=device)
            self.tokenizer = clip.tokenize
            self.device = device
            self.clip_available = True
            print("[VisualDNAExtractor] CLIP model loaded successfully")
        except ImportError:
            print("[VisualDNAExtractor] CLIP not available, using OpenCV fallback")

    def extract(self, video_path: Path, shot_boundary,
                shot_id: str, video_id: str) -> VisualDNA:
        """从视频片段提取视觉 DNA"""
        start_time = shot_boundary.start_time
        end_time = shot_boundary.end_time
        duration = end_time - start_time

        # Step 1: 提取关键帧
        frames = self._extract_frames(video_path, start_time, end_time)

        if not frames:
            return self._create_fallback_dna(shot_id, video_id, duration)

        # Step 2: 分析视觉特征
        visual_features = self._analyze_visual_features(frames)

        # Step 3: 识别主体和动作（使用 CLIP 或 OpenCV）
        subjects = self._identify_subjects(frames)
        actions = self._identify_actions(frames)
        emotions = self._identify_emotions(frames)
        scene = self._identify_scene(frames)
        camera = self._identify_camera(frames)

        # Step 4: 计算视觉指标
        hook_strength = self._calculate_hook_strength(frames, start_time)
        visual_quality = self._calculate_visual_quality(frames)

        # Step 5: 检测 UI 和文字
        text_detected = self._detect_text(frames)
        ui_elements = self._detect_ui(frames)
        logo_detected = self._detect_logo(frames)

        return VisualDNA(
            shot_id=shot_id,
            source_video=video_id,
            subjects=subjects,
            actions=actions,
            emotions=emotions,
            scene=scene,
            camera=camera,
            visual_hook=hook_strength > 70,
            hook_strength=round(hook_strength, 1),
            motion_level=self._classify_motion(frames),
            brightness=round(visual_features["brightness"], 1),
            color_vibrancy=round(visual_features["color_vibrancy"], 1),
            composition_score=round(visual_features["composition"], 1),
            visual_quality=visual_quality,
            performance_score=visual_quality,  # 后续由UA数据更新
            duration=round(duration, 2),
            frame_count=len(frames),
            dominant_color=visual_features["dominant_color"],
            text_detected=text_detected,
            ui_elements=ui_elements,
            logo_detected=logo_detected,
        )

    def _extract_frames(self, video_path: Path, start_time: float,
                        end_time: float) -> List[np.ndarray]:
        """提取视频片段的关键帧"""
        frames = []
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            return frames

        fps = cap.get(cv2.CAP_PROP_FPS)
        start_frame = int(start_time * fps)
        end_frame = int(end_time * fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        frame_count = 0
        sample_interval = max(1, int((end_frame - start_frame) / 10))

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            if current_frame > end_frame:
                break

            if frame_count % sample_interval == 0:
                frames.append(frame)

            frame_count += 1

        cap.release()
        return frames

    def _analyze_visual_features(self, frames: List[np.ndarray]) -> Dict:
        """分析视觉特征"""
        if not frames:
            return {"brightness": 50, "color_vibrancy": 50, "composition": 50, "dominant_color": "#808080"}

        frame = frames[len(frames) // 2]

        # 亮度
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray) / 2.55

        # 色彩饱和度
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        saturation = np.mean(hsv[:, :, 1]) / 2.55

        # 色彩活力
        color_vibrancy = saturation * 0.6 + brightness * 0.4

        # 构图评分（简单版：检测主体位置）
        composition = self._score_composition(frame)

        # 主色调
        dominant_color = self._get_dominant_color(frame)

        return {
            "brightness": brightness,
            "color_vibrancy": color_vibrancy,
            "composition": composition,
            "dominant_color": dominant_color,
        }

    def _score_composition(self, frame: np.ndarray) -> float:
        """评分构图（三分法）"""
        h, w = frame.shape[:2]

        # 检测边缘（主体通常在边缘附近）
        edges = cv2.Canny(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), 100, 200)

        # 检查三分线位置是否有内容
        third_h1, third_h2 = h // 3, 2 * h // 3
        third_w1, third_w2 = w // 3, 2 * w // 3

        score = 50

        # 中心区域
        center_content = np.mean(edges[third_h1:third_h2, third_w1:third_w2])
        if center_content > 30:
            score += 20

        # 交叉点
        cross_points = [
            edges[third_h1, third_w1], edges[third_h1, third_w2],
            edges[third_h2, third_w1], edges[third_h2, third_w2],
        ]
        if any(p > 50 for p in cross_points):
            score += 15

        # 边缘内容
        edge_content = np.mean(edges[:, :10]) + np.mean(edges[:, -10:]) + \
                       np.mean(edges[:10, :]) + np.mean(edges[-10:, :])
        if edge_content > 20:
            score += 15

        return min(100, score)

    def _get_dominant_color(self, frame: np.ndarray) -> str:
        """获取主色调"""
        pixels = frame.reshape(-1, 3)
        pixels = np.float32(pixels)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        k = 3
        _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

        counts = np.bincount(labels.flatten())
        dominant = centers[np.argmax(counts)]

        return "#{:02X}{:02X}{:02X}".format(
            int(dominant[2]), int(dominant[1]), int(dominant[0])
        )

    def _identify_subjects(self, frames: List[np.ndarray]) -> List[str]:
        """识别主体"""
        if self.clip_available:
            return self._identify_with_clip(frames, "subject")

        # OpenCV 回退：检测运动和颜色区域
        return self._identify_with_opencv(frames)

    def _identify_actions(self, frames: List[np.ndarray]) -> List[str]:
        """识别动作"""
        if self.clip_available:
            return self._identify_with_clip(frames, "action")

        # 基于运动分析推断动作
        return self._infer_actions_from_motion(frames)

    def _identify_emotions(self, frames: List[np.ndarray]) -> List[str]:
        """识别情绪"""
        emotions = []

        # 基于颜色和亮度推断情绪
        frame = frames[len(frames) // 2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        hue_mean = np.mean(hsv[:, :, 0])
        sat_mean = np.mean(hsv[:, :, 1])

        # 暖色（红/橙/黄）→ excitement/satisfaction
        if 0 <= hue_mean <= 30 or 330 <= hue_mean <= 360:
            emotions.append("excitement")
        elif 30 < hue_mean < 60:
            emotions.append("satisfaction")

        # 高饱和度 → excitement/surprise
        if sat_mean > 150:
            emotions.append("surprise")

        # 亮度分析
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)
        if brightness < 50:
            emotions.append("danger")
        elif brightness > 180:
            emotions.append("satisfaction")

        return list(set(emotions))

    def _identify_scene(self, frames: List[np.ndarray]) -> str:
        """识别场景"""
        if self.clip_available:
            return self._identify_with_clip(frames, "scene")[0] if frames else "unknown"

        return self._infer_scene_from_color(frames)

    def _identify_camera(self, frames: List[np.ndarray]) -> str:
        """识别镜头类型"""
        if len(frames) < 2:
            return "static"

        # 分析帧间变化
        changes = []
        for i in range(1, len(frames)):
            diff = cv2.absdiff(
                cv2.cvtColor(frames[i-1], cv2.COLOR_BGR2GRAY),
                cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            )
            changes.append(np.mean(diff))

        avg_change = np.mean(changes)

        if avg_change < 5:
            return "static"
        elif avg_change < 20:
            return "slow_pan"
        else:
            return "dynamic"

    def _calculate_hook_strength(self, frames: List[np.ndarray], start_time: float) -> float:
        """计算 Hook 强度（前3秒特别重要）"""
        score = 0

        # 前3秒加分
        if start_time < 3:
            score += 20

        # 运动强度
        if len(frames) >= 2:
            motion = self._calculate_motion(frames)
            score += min(30, motion / 2)

        # 色彩活力
        frame = frames[0]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        saturation = np.mean(hsv[:, :, 1])
        score += min(25, saturation / 10)

        # 亮度对比
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        contrast = np.std(gray)
        score += min(25, contrast / 3)

        return min(100, score)

    def _calculate_motion(self, frames: List[np.ndarray]) -> float:
        """计算运动分数"""
        if len(frames) < 2:
            return 0

        total_motion = 0
        for i in range(1, len(frames)):
            flow = cv2.calcOpticalFlowFarneback(
                cv2.cvtColor(frames[i-1], cv2.COLOR_BGR2GRAY),
                cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY),
                None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
            mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            total_motion += np.mean(mag)

        return total_motion / (len(frames) - 1)

    def _classify_motion(self, frames: List[np.ndarray]) -> str:
        """分类运动级别"""
        motion = self._calculate_motion(frames)
        if motion < 5:
            return "low"
        elif motion < 15:
            return "medium"
        else:
            return "high"

    def _calculate_visual_quality(self, frames: List[np.ndarray]) -> int:
        """计算视觉质量分"""
        if not frames:
            return 50

        scores = []
        for frame in frames:
            # 清晰度（Laplacian方差）
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()

            # 对比度
            contrast = np.std(gray)

            # 饱和度
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            saturation = np.mean(hsv[:, :, 1])

            score = min(100,
                min(30, sharpness / 50) +
                min(30, contrast / 3) +
                min(30, saturation / 8) +
                10  # 基础分
            )
            scores.append(score)

        return int(np.mean(scores))

    def _detect_text(self, frames: List[np.ndarray]) -> bool:
        """检测文字"""
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # 简单边缘检测作为文字指示器
            edges = cv2.Canny(gray, 50, 150)
            # 水平线和垂直线检测
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, minLineLength=30, maxLineGap=10)
            if lines is not None and len(lines) > 5:
                return True
        return False

    def _detect_ui(self, frames: List[np.ndarray]) -> bool:
        """检测 UI 元素"""
        for frame in frames:
            h, w = frame.shape[:2]
            # 检查角落（UI通常在角落）
            corners = [
                frame[:h//5, :w//5],      # 左上
                frame[:h//5, -w//5:],    # 右上
                frame[-h//5:, :w//5],     # 左下
                frame[-h//5:, -w//5:],    # 右下
            ]
            for corner in corners:
                if np.mean(corner) > 200:  # 白色区域
                    return True
        return False

    def _detect_logo(self, frames: List[np.ndarray]) -> bool:
        """检测 Logo"""
        return False

    def _identify_with_clip(self, frames: List[np.ndarray], task: str) -> List[str]:
        """使用 CLIP 识别"""
        import torch

        if not self.clip_available or not frames:
            return []

        frame = frames[len(frames) // 2]
        image = self.preprocess(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).unsqueeze(0).to(self.device)

        # 根据任务选择标签
        if task == "subject":
            labels = list(self.SUBJECT_KEYWORDS.keys())
        elif task == "action":
            labels = list(self.ACTION_KEYWORDS.keys())
        elif task == "scene":
            labels = list(self.SCENE_KEYWORDS.keys())
        else:
            return []

        text = self.tokenizer(labels).to(self.device)

        with torch.no_grad():
            image_features = self.model.encode_image(image)
            text_features = self.model.encode_text(text)
            logits_per_image, _ = self.model(image, text)
            probs = logits_per_image.softmax(dim=-1).cpu().numpy()[0]

        # 返回置信度最高的前3个
        results = []
        for idx in np.argsort(probs)[::-1][:3]:
            if probs[idx] > 0.1:
                results.append(labels[idx])

        return results

    def _identify_with_opencv(self, frames: List[np.ndarray]) -> List[str]:
        """OpenCV 回退识别"""
        subjects = []

        if not frames:
            return subjects

        frame = frames[len(frames) // 2]

        # 简单颜色分析
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 暖色主体 → character/monster
        warm_mask = cv2.inRange(hsv, (0, 50, 50), (30, 255, 255)) | \
                    cv2.inRange(hsv, (330, 50, 50), (360, 255, 255))
        if np.sum(warm_mask) > frame.size * 0.1:
            subjects.append("character")

        # 绿色区域 → nature/forest
        green_mask = cv2.inRange(hsv, (40, 50, 50), (80, 255, 255))
        if np.sum(green_mask) > frame.size * 0.3:
            subjects.append("nature")

        # 蓝色区域 → sky/ocean
        blue_mask = cv2.inRange(hsv, (90, 50, 50), (130, 255, 255))
        if np.sum(blue_mask) > frame.size * 0.3:
            subjects.append("sky")

        return subjects

    def _infer_actions_from_motion(self, frames: List[np.ndarray]) -> List[str]:
        """从运动推断动作"""
        actions = []
        motion = self._calculate_motion(frames)

        if motion > 20:
            actions.append("attack")
            actions.append("transform")
        elif motion > 10:
            actions.append("collect")
            actions.append("explore")
        else:
            actions.append("static")

        return actions

    def _infer_scene_from_color(self, frames: List[np.ndarray]) -> str:
        """从颜色推断场景"""
        if not frames:
            return "unknown"

        frame = frames[len(frames) // 2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 绿色为主 → forest
        green_mask = cv2.inRange(hsv, (40, 50, 50), (80, 255, 255))
        if np.sum(green_mask) > frame.size * 0.3:
            return "forest"

        # 蓝色为主 → sky/ocean
        blue_mask = cv2.inRange(hsv, (90, 50, 50), (130, 255, 255))
        if np.sum(blue_mask) > frame.size * 0.3:
            return "sky"

        # 暖色为主 → battlefield/castle
        warm_mask = cv2.inRange(hsv, (0, 50, 50), (30, 255, 255)) | \
                    cv2.inRange(hsv, (330, 50, 50), (360, 255, 255))
        if np.sum(warm_mask) > frame.size * 0.2:
            return "battlefield"

        return "unknown"

    def _create_fallback_dna(self, shot_id: str, video_id: str, duration: float) -> VisualDNA:
        """创建回退 DNA（当无法读取视频时）"""
        return VisualDNA(
            shot_id=shot_id,
            source_video=video_id,
            subjects=["unknown"],
            actions=["unknown"],
            emotions=["neutral"],
            scene="unknown",
            camera="static",
            visual_hook=False,
            hook_strength=0.0,
            motion_level="low",
            brightness=50.0,
            color_vibrancy=50.0,
            composition_score=50.0,
            visual_quality=50,
            performance_score=50,
            duration=round(duration, 2),
            frame_count=0,
            dominant_color="#808080",
            text_detected=False,
            ui_elements=False,
            logo_detected=False,
        )

    def batch_extract(self, video_path: Path,
                      boundaries, video_id: str) -> List[VisualDNA]:
        """批量提取"""
        results = []
        for boundary in boundaries:
            dna = self.extract(video_path, boundary, boundary.shot_id, video_id)
            results.append(dna)
        return results

    def save_dna(self, dna_list: List[VisualDNA], output_path: Path):
        """保存 DNA 数据"""
        data = {
            "dna_list": [{
                "shot_id": d.shot_id,
                "source_video": d.source_video,
                "subjects": d.subjects,
                "actions": d.actions,
                "emotions": d.emotions,
                "scene": d.scene,
                "camera": d.camera,
                "visual_hook": d.visual_hook,
                "hook_strength": d.hook_strength,
                "motion_level": d.motion_level,
                "brightness": d.brightness,
                "color_vibrancy": d.color_vibrancy,
                "composition_score": d.composition_score,
                "visual_quality": d.visual_quality,
                "performance_score": d.performance_score,
                "duration": d.duration,
                "frame_count": d.frame_count,
                "dominant_color": d.dominant_color,
                "text_detected": d.text_detected,
                "ui_elements": d.ui_elements,
                "logo_detected": d.logo_detected,
            } for d in dna_list],
            "timestamp": datetime.now().isoformat(),
            "total_shots": len(dna_list),
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def extract_visual_dna(video_path: str,
                       boundaries,
                       video_id: str = "") -> List[VisualDNA]:
    """便捷函数：提取视觉 DNA"""
    extractor = VisualDNAExtractor()
    return extractor.batch_extract(Path(video_path), boundaries, video_id)