"""Video Quality Analyzer — 自动评估生成视频质量

评估维度：
- Hook Quality (0-100): 前3秒冲击力
- Retention Score (0-100): 3s/5s/15s 完播预测
- Gameplay Clarity (0-100): 玩法展示清晰度
- Reward Density (0-100): 奖励元素密度
"""
import cv2
import json
import subprocess
from pathlib import Path
from typing import Dict, List


class VideoQualityAnalyzer:
    """视频质量自动分析器"""

    def analyze(self, video_path: Path) -> Dict:
        """对单个视频进行全面质量分析"""
        info = self._get_video_info(video_path)
        frames = self._extract_sample_frames(video_path, info)

        hook_score = self._analyze_hook(frames[:3], info)
        retention = self._predict_retention(frames, info)
        gameplay = self._analyze_gameplay(frames)
        reward = self._analyze_reward(frames)

        overall = round((hook_score + retention + gameplay + reward) / 4, 1)

        return {
            "video_name": video_path.stem,
            "hook_score": round(hook_score, 1),
            "retention_score": round(retention, 1),
            "gameplay_clarity": round(gameplay, 1),
            "reward_density": round(reward, 1),
            "overall_score": overall,
        }

    def _get_video_info(self, video_path: Path) -> dict:
        try:
            r = subprocess.run([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration",
                "-of", "json", str(video_path)
            ], capture_output=True, text=True, timeout=10)
            s = json.loads(r.stdout).get("streams", [{}])[0]
            return {
                "width": int(s.get("width", 0)),
                "height": int(s.get("height", 0)),
                "duration": float(s.get("duration", 0) or 0),
            }
        except Exception:
            return {"width": 0, "height": 0, "duration": 0}

    def _extract_sample_frames(self, video_path: Path, info: dict) -> List:
        """提取关键帧：0s, 1s, 2s, 3s, 5s, 8s, 11s, 13s, 14s"""
        import tempfile
        frames = []
        ts_points = [0, 1, 2, 3, 5, 8, 11, 13, 14]
        for ts in ts_points:
            if ts > info.get("duration", 15):
                continue
            out = tempfile.gettempdir() + f"/v36_frame_{ts}.jpg"
            subprocess.run([
                "ffmpeg", "-y", "-ss", str(ts), "-i", str(video_path),
                "-vframes", "1", "-q:v", "2", "-loglevel", "error", out
            ], capture_output=True, timeout=15)
            img = cv2.imread(out)
            if img is not None:
                frames.append({"ts": ts, "img": img})
        return frames

    def _analyze_hook(self, frames: List[dict], info: dict) -> float:
        """Hook 质量 = 前3秒冲击力"""
        if len(frames) < 2:
            return 40.0

        scores = []
        for i, f in enumerate(frames):
            img = f["img"]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # 视觉冲击
            contrast = min(100, gray.std() / 80 * 100)
            saturation = min(100, hsv[:, :, 1].mean() / 255 * 100)
            brightness = gray.mean() / 255 * 100

            # 运动强度（帧间差分）
            motion = 0
            if i > 0:
                prev_gray = cv2.cvtColor(frames[i - 1]["img"], cv2.COLOR_BGR2GRAY)
                h, w = min(gray.shape[0], prev_gray.shape[0]), min(gray.shape[1], prev_gray.shape[1])
                gray_r = cv2.resize(gray, (w, h))
                prev_r = cv2.resize(prev_gray, (w, h))
                motion = min(100, cv2.absdiff(gray_r, prev_r).mean() / 2)

            # 主体大小
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            subject = 30
            if contours:
                max_area = max(cv2.contourArea(c) for c in contours)
                h, w = img.shape[:2]
                subject = min(100, max_area / (h * w) * 100 * 4)

            # 前3秒权重更高
            time_weight = 1.0 if f["ts"] <= 1.5 else 0.7
            frame_score = (contrast * 0.2 + saturation * 0.2 + motion * 0.25 + subject * 0.25 + brightness * 0.1) * time_weight
            scores.append(frame_score)

        return sum(scores) / len(scores) if scores else 40

    def _predict_retention(self, frames: List[dict], info: dict) -> float:
        """留存预测 = 3s/5s/15s 完播潜力"""
        if not frames:
            return 40.0

        # 按时间段分组评分
        early = [f for f in frames if f["ts"] <= 3]
        mid = [f for f in frames if 3 < f["ts"] <= 8]
        late = [f for f in frames if f["ts"] > 8]

        def group_score(group):
            if not group:
                return 30
            scores = []
            for f in group:
                img = f["img"]
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                # 兴趣度 = 对比度 + 边缘密度（内容丰富度）
                contrast = gray.std()
                edges = cv2.Canny(gray, 50, 150)
                edge_ratio = cv2.countNonZero(edges) / (edges.shape[0] * edges.shape[1])
                scores.append(contrast * 0.5 + edge_ratio * 200)
            return sum(scores) / len(scores)

        s_early = group_score(early)
        s_mid = group_score(mid)
        s_late = group_score(late)

        # 留存曲线模拟：前3秒决定 3s留存，中后段决定完播
        retention_3s = min(100, s_early / 1.5)
        retention_5s = min(100, (s_early * 0.6 + s_mid * 0.4) / 1.5)
        retention_15s = min(100, (s_early * 0.3 + s_mid * 0.3 + s_late * 0.4) / 1.5)

        return (retention_3s * 0.35 + retention_5s * 0.35 + retention_15s * 0.30)

    def _analyze_gameplay(self, frames: List[dict]) -> float:
        """玩法清晰度 = 网格检测 + UI元素 + 运动连续性"""
        if len(frames) < 3:
            return 35.0

        grid_scores = []
        motion_scores = []

        for i, f in enumerate(frames):
            img = f["img"]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # 网格检测（Merge 游戏常见）
            edges = cv2.Canny(gray, 50, 150)
            lines = cv2.HoughLinesP(edges, 1, 3.14159 / 180, threshold=60,
                                    minLineLength=gray.shape[1] * 0.12, maxLineGap=8)
            gridness = 0
            if lines is not None:
                h_lines = sum(1 for l in lines if abs(l[0][1] - l[0][3]) < 5)
                v_lines = sum(1 for l in lines if abs(l[0][0] - l[0][2]) < 5)
                gridness = min(100, (h_lines + v_lines) * 3)
            grid_scores.append(gridness)

            # 运动连续性
            if i > 0:
                prev = cv2.cvtColor(frames[i - 1]["img"], cv2.COLOR_BGR2GRAY)
                h, w = min(gray.shape[0], prev.shape[0]), min(gray.shape[1], prev.shape[1])
                gray_r = cv2.resize(gray, (w, h))
                prev_r = cv2.resize(prev, (w, h))
                motion_scores.append(cv2.absdiff(gray_r, prev_r).mean())

        avg_grid = sum(grid_scores) / len(grid_scores) if grid_scores else 0
        avg_motion = sum(motion_scores) / len(motion_scores) if motion_scores else 0

        return min(100, avg_grid * 0.5 + min(100, avg_motion * 2) * 0.3 + 20)

    def _analyze_reward(self, frames: List[dict]) -> float:
        """奖励密度 = 闪光 + 粒子 + 大物体 + 亮度峰值"""
        if not frames:
            return 25.0

        flash_scores = []
        big_obj_scores = []
        bright_scores = []

        for f in frames:
            img = f["img"]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            h, w = img.shape[:2]

            # 闪光检测
            _, bright = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
            flash_ratio = cv2.countNonZero(bright) / (h * w)
            flash_scores.append(min(100, flash_ratio * 100 * 10))

            # 大物体
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                max_area = max(cv2.contourArea(c) for c in contours)
                big_obj_scores.append(min(100, max_area / (h * w) * 100 * 5))
            else:
                big_obj_scores.append(10)

            # 亮度
            bright_scores.append(gray.mean() / 255 * 100)

        avg_flash = sum(flash_scores) / len(flash_scores)
        avg_big = sum(big_obj_scores) / len(big_obj_scores)
        avg_bright = sum(bright_scores) / len(bright_scores)

        return min(100, avg_flash * 0.25 + avg_big * 0.25 + avg_bright * 0.20 + 30)
