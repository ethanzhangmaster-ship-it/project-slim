"""Video Quality Analyzer V2 — V3.6.1 升级版

新增：
- Ad Value Score = Hook×35% + Retention×25% + Gameplay×20% + Reward×15% + CTA×5%
- 预测 CTR / CVR / Purchase Intent
"""
import cv2
import json
import subprocess
from pathlib import Path
from typing import Dict, List


class VideoQualityAnalyzerV2:
    """V2 视频质量自动分析器"""

    def analyze(self, video_path: Path) -> Dict:
        info = self._get_video_info(video_path)
        frames = self._extract_sample_frames(video_path, info)

        hook_score = self._analyze_hook(frames[:3], info)
        retention = self._predict_retention(frames, info)
        gameplay = self._analyze_gameplay(frames)
        reward = self._analyze_reward(frames)
        cta = self._analyze_cta(frames[-1:] if frames else [])

        # Ad Value Score
        ad_value = round(
            hook_score * 0.35 +
            retention * 0.25 +
            gameplay * 0.20 +
            reward * 0.15 +
            cta * 0.05,
            1
        )

        # 预测买量指标
        ctr = round(min(5.0, max(0.5, ad_value / 20)), 2)
        cvr = round(min(15.0, max(1.0, ad_value / 8)), 2)
        purchase_intent = round(min(80, max(10, ad_value * 0.8)), 1)

        overall = round((hook_score + retention + gameplay + reward + cta) / 5, 1)

        return {
            "video_name": video_path.stem,
            "hook_score": round(hook_score, 1),
            "retention_score": round(retention, 1),
            "gameplay_clarity": round(gameplay, 1),
            "reward_density": round(reward, 1),
            "cta_clarity": round(cta, 1),
            "ad_value_score": ad_value,
            "predicted_ctr": ctr,
            "predicted_cvr": cvr,
            "purchase_intent": purchase_intent,
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
            return {"width": int(s.get("width", 0)), "height": int(s.get("height", 0)),
                    "duration": float(s.get("duration", 0) or 0)}
        except Exception:
            return {"width": 0, "height": 0, "duration": 0}

    def _extract_sample_frames(self, video_path: Path, info: dict) -> List:
        import tempfile
        frames = []
        for ts in [0, 1, 2, 3, 5, 8, 11, 13, 14]:
            if ts > info.get("duration", 15):
                continue
            out = tempfile.gettempdir() + f"/v361_frame_{ts}.jpg"
            subprocess.run([
                "ffmpeg", "-y", "-ss", str(ts), "-i", str(video_path),
                "-vframes", "1", "-q:v", "2", "-loglevel", "error", out
            ], capture_output=True, timeout=15)
            img = cv2.imread(out)
            if img is not None:
                frames.append({"ts": ts, "img": img})
        return frames

    def _analyze_hook(self, frames: List[dict], info: dict) -> float:
        if len(frames) < 2:
            return 40.0
        scores = []
        for i, f in enumerate(frames):
            img = f["img"]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            contrast = min(100, gray.std() / 80 * 100)
            saturation = min(100, hsv[:, :, 1].mean() / 255 * 100)
            motion = 0
            if i > 0:
                prev = cv2.cvtColor(frames[i - 1]["img"], cv2.COLOR_BGR2GRAY)
                h, w = min(gray.shape[0], prev.shape[0]), min(gray.shape[1], prev.shape[1])
                motion = min(100, cv2.absdiff(cv2.resize(gray, (w, h)), cv2.resize(prev, (w, h))).mean() / 2)
            # 主体大小
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            subject = 30
            if contours:
                max_area = max(cv2.contourArea(c) for c in contours)
                h, w = img.shape[:2]
                subject = min(100, max_area / (h * w) * 100 * 4)
            time_weight = 1.0 if f["ts"] <= 1.5 else 0.7
            frame_score = (contrast * 0.2 + saturation * 0.2 + motion * 0.25 + subject * 0.25 + gray.mean() / 255 * 10) * time_weight
            scores.append(frame_score)
        return sum(scores) / len(scores) if scores else 40

    def _predict_retention(self, frames: List[dict], info: dict) -> float:
        if not frames:
            return 40.0
        early = [f for f in frames if f["ts"] <= 3]
        mid = [f for f in frames if 3 < f["ts"] <= 8]
        late = [f for f in frames if f["ts"] > 8]

        def gs(group):
            if not group:
                return 30
            scores = []
            for f in group:
                gray = cv2.cvtColor(f["img"], cv2.COLOR_BGR2GRAY)
                scores.append(gray.std() * 0.5 + cv2.countNonZero(cv2.Canny(gray, 50, 150)) / (gray.shape[0] * gray.shape[1]) * 200)
            return sum(scores) / len(scores)

        r3 = min(100, gs(early) / 1.5)
        r5 = min(100, (gs(early) * 0.6 + gs(mid) * 0.4) / 1.5)
        r15 = min(100, (gs(early) * 0.3 + gs(mid) * 0.3 + gs(late) * 0.4) / 1.5)
        return r3 * 0.35 + r5 * 0.35 + r15 * 0.30

    def _analyze_gameplay(self, frames: List[dict]) -> float:
        if len(frames) < 3:
            return 35.0
        grid_scores = []
        motion_scores = []
        for i, f in enumerate(frames):
            gray = cv2.cvtColor(f["img"], cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            lines = cv2.HoughLinesP(edges, 1, 3.14159 / 180, 60,
                                    minLineLength=gray.shape[1] * 0.12, maxLineGap=8)
            gridness = 0
            if lines is not None:
                h_lines = sum(1 for l in lines if abs(l[0][1] - l[0][3]) < 5)
                v_lines = sum(1 for l in lines if abs(l[0][0] - l[0][2]) < 5)
                gridness = min(100, (h_lines + v_lines) * 3)
            grid_scores.append(gridness)
            if i > 0:
                prev = cv2.cvtColor(frames[i - 1]["img"], cv2.COLOR_BGR2GRAY)
                h, w = min(gray.shape[0], prev.shape[0]), min(gray.shape[1], prev.shape[1])
                motion_scores.append(cv2.absdiff(cv2.resize(gray, (w, h)), cv2.resize(prev, (w, h))).mean())
        avg_grid = sum(grid_scores) / len(grid_scores)
        avg_motion = sum(motion_scores) / len(motion_scores) if motion_scores else 0
        return min(100, avg_grid * 0.5 + min(100, avg_motion * 2) * 0.3 + 20)

    def _analyze_reward(self, frames: List[dict]) -> float:
        if not frames:
            return 25.0
        flash_scores = []
        big_obj_scores = []
        bright_scores = []
        for f in frames:
            gray = cv2.cvtColor(f["img"], cv2.COLOR_BGR2GRAY)
            h, w = f["img"].shape[:2]
            _, bright = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
            flash_scores.append(min(100, cv2.countNonZero(bright) / (h * w) * 100 * 10))
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                big_obj_scores.append(min(100, max(cv2.contourArea(c) for c in contours) / (h * w) * 100 * 5))
            else:
                big_obj_scores.append(10)
            bright_scores.append(gray.mean() / 255 * 100)
        return min(100, sum(flash_scores) / len(flash_scores) * 0.25 + sum(big_obj_scores) / len(big_obj_scores) * 0.25 + sum(bright_scores) / len(bright_scores) * 0.20 + 30)

    def _analyze_cta(self, frames: List[dict]) -> float:
        if not frames:
            return 30.0
        img = frames[0]["img"]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # CTA 通常有高对比度 + 文字区域
        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = cv2.countNonZero(edges) / (gray.shape[0] * gray.shape[1])
        return min(100, edge_ratio * 300 + 30)
