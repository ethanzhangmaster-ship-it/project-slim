"""Gameplay Detector — 识别 Merge/Drag/Evolution/Puzzle/Collect/Reward/Upgrade"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict


class GameplayDetector:
    """玩法检测器"""

    # 关键词映射
    GAMEPLAY_KEYWORDS = {
        "merge": ["merge", "he", "合", "drag", "拖", "swipe", "滑", "match", "配"],
        "evolution": ["evol", "进化", "升级", "upgrade", "transform", "变身"],
        "puzzle": ["puzzle", "谜", "solve", "解", "level", "关"],
        "collect": ["collect", "收", "gather", "集", "item", "道具"],
        "reward": ["reward", "奖励", "gift", "treasure", "宝箱", "unlock", "解锁"],
        "battle": ["battle", "战", "attack", "攻", "fight", "boss", "boss"],
        "idle": ["idle", "挂", "auto", "自动", "farm", "刷"],
    }

    def analyze(self, frame_paths: List[Path], video_name: str = "") -> Dict:
        """
        分析视频是否包含玩法元素。
        基于文件名 + 帧特征（网格检测、UI元素检测）。
        """
        name_score, detected_types = self._analyze_name(video_name)

        # 帧级分析
        grid_scores = []
        ui_scores = []
        motion_scores = []

        valid = [p for p in frame_paths if p.exists()]
        for i, fp in enumerate(valid):
            img = cv2.imread(str(fp))
            if img is None:
                continue
            grid_scores.append(self._detect_grid(img))
            ui_scores.append(self._detect_ui(img))
            if i > 0:
                prev = cv2.imread(str(valid[i - 1]), cv2.IMREAD_GRAYSCALE)
                curr = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                if prev is not None:
                    motion_scores.append(np.mean(cv2.absdiff(prev, curr)))

        avg_grid = np.mean(grid_scores) if grid_scores else 0
        avg_ui = np.mean(ui_scores) if ui_scores else 0
        avg_motion = np.mean(motion_scores) if motion_scores else 0

        # Gameplay score = 文件名信号(30%) + 网格检测(25%) + UI检测(25%) + 运动连续性(20%)
        gameplay_score = (
            name_score * 0.30 +
            avg_grid * 0.25 +
            avg_ui * 0.25 +
            min(100, avg_motion * 2) * 0.20
        )

        # 确定主要玩法类型
        if not detected_types:
            # 基于帧特征推断
            if avg_grid > 50 and avg_motion > 30:
                detected_types = ["merge"]
            elif avg_ui > 60:
                detected_types = ["reward"]
            else:
                detected_types = ["idle"]

        return {
            "gameplay_score": round(min(100, gameplay_score), 1),
            "gameplay_type": detected_types[0] if detected_types else "unknown",
            "gameplay_types": detected_types,
            "grid_score": round(avg_grid, 1),
            "ui_score": round(avg_ui, 1),
            "motion_continuous": round(avg_motion, 1),
        }

    def _analyze_name(self, name: str) -> tuple:
        """从文件名分析玩法类型"""
        s = name.lower()
        scores = {}
        for gtype, kws in self.GAMEPLAY_KEYWORDS.items():
            for kw in kws:
                if kw in s:
                    scores[gtype] = scores.get(gtype, 0) + 20

        if not scores:
            return 30, []

        best_type = max(scores, key=scores.get)
        return min(100, scores[best_type]), [best_type]

    def _detect_grid(self, img: np.ndarray) -> float:
        """检测网格结构（Merge/Puzzle 游戏常见）"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        # 霍夫直线检测
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                                minLineLength=gray.shape[1] * 0.15,
                                maxLineGap=10)
        if lines is None:
            return 0

        # 统计水平和垂直线
        h_lines = sum(1 for l in lines if abs(l[0][1] - l[0][3]) < 5)
        v_lines = sum(1 for l in lines if abs(l[0][0] - l[0][2]) < 5)

        # 网格感 = 水平线和垂直线都较多
        gridness = min(100, (h_lines + v_lines) * 3)
        return gridness

    def _detect_ui(self, img: np.ndarray) -> float:
        """检测 UI 元素（按钮、文字框等）"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # 边缘密度高的区域可能是 UI
        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = np.count_nonzero(edges) / (edges.shape[0] * edges.shape[1])

        # 颜色均匀区域可能是 UI 面板
        blur = cv2.GaussianBlur(gray, (21, 21), 0)
        flat_ratio = np.count_nonzero(np.abs(gray.astype(int) - blur.astype(int)) < 10) / gray.size

        ui_score = min(100, (edge_ratio * 200 + flat_ratio * 50))
        return ui_score
