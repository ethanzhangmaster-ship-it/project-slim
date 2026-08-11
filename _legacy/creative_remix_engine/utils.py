"""工具函数"""
import csv
import json
import subprocess
import re
from pathlib import Path
from typing import List, Dict, Optional

from .models import VideoAsset, PerformanceData


def load_adjust_data(csv_path: Path) -> List[PerformanceData]:
    """读取 Adjust 投放数据"""
    data = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(PerformanceData(
                creative_id=row.get("creative_id", ""),
                v_num=row.get("v_num", ""),
                spend=float(row.get("spend", 0) or 0),
                revenue=float(row.get("revenue", 0) or 0),
                roas=float(row.get("roas", 0) or 0),
                purchase=int(float(row.get("purchase", 0) or 0)),
                ctr=float(row.get("ctr", 0) or 0),
                cvr=float(row.get("cvr", 0) or 0),
                cost=float(row.get("cost", 0) or 0),
                installs=int(float(row.get("installs", 0) or 0)),
                content_type=row.get("content", ""),
                duration=row.get("duration", ""),
                ratio=row.get("ratio", ""),
            ))
    return data


def load_eagle_index(json_path: Path) -> List[Dict]:
    """读取 Eagle 素材索引"""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_video_info(filepath: Path) -> Optional[Dict]:
    """ffprobe 获取视频信息"""
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration",
            "-of", "json",
            str(filepath)
        ], capture_output=True, text=True)
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        return {
            "width": int(stream.get("width", 0)),
            "height": int(stream.get("height", 0)),
            "duration": float(stream.get("duration", 0) or 0),
        }
    except Exception:
        return None


def classify_ratio(width: int, height: int) -> str:
    """根据分辨率分类比例"""
    if width == 0 or height == 0:
        return "unknown"
    r = width / height
    if r < 0.7:
        return "9X16"
    elif r > 1.3:
        return "16X9"
    else:
        return "1X1"


def build_video_index(source_dir: Path) -> Dict[str, VideoAsset]:
    """构建本地视频素材索引"""
    index = {}
    for video_file in source_dir.iterdir():
        if video_file.is_file() and video_file.suffix.lower() == ".mp4":
            m = re.search(r'v(\d+)', video_file.stem)
            if not m:
                continue
            v_num = f"v{m.group(1)}"
            info = get_video_info(video_file)
            if info:
                ratio = classify_ratio(info["width"], info["height"])
            else:
                ratio = "9X16" if "9X16" in video_file.stem else "1X1"
            index[v_num] = VideoAsset(
                v_num=v_num,
                filepath=video_file,
                ratio=ratio,
                width=info["width"] if info else 0,
                height=info["height"] if info else 0,
                duration=info["duration"] if info else 0,
                filename=video_file.name,
            )
    return index


def safe_name(text: str) -> str:
    """安全文件名"""
    return re.sub(r'[^\w\-_.]', '_', text)
