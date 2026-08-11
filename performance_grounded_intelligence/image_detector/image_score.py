"""Image Score — 图片素材多维检测评分

替代纯关键词方案, 使用三维信号融合:
  ImageScore = 0.5 * meta_type + 0.3 * thumbnail_exists + 0.2 * keyword

阈值: >= 0.7 判定为图片广告
"""
from typing import Dict, List

from ..config import IMAGE_KEYWORDS, IMAGE_SCORE_THRESHOLD


def calculate_image_score(ad: dict) -> float:
    """计算单条广告的 Image Detection Score

    Args:
        ad: 包含 creative_type, video_id, thumbnail_url, ad_name 的广告记录

    Returns:
        0.0 ~ 1.0 的图片置信分
    """
    creative_type = (ad.get("creative_type", "") or "").lower()
    video_id = ad.get("video_id", "") or ""
    thumbnail_url = ad.get("thumbnail_url", "") or ""
    ad_name = (ad.get("ad_name", "") or "").lower()

    # 维度1: Meta creative type (权重 0.5)
    if creative_type == "image":
        meta_score = 1.0
    elif not video_id:
        # 无 video_id 但类型不明确 → 可能是图片
        meta_score = 0.5
    else:
        # 有 video_id → 视频广告
        meta_score = 0.0

    # 维度2: Thumbnail URL 存在 (权重 0.3)
    thumb_score = 1.0 if thumbnail_url else 0.0

    # 维度3: 广告名关键词 (权重 0.2)
    keyword_score = 1.0 if any(kw in ad_name for kw in IMAGE_KEYWORDS) else 0.0

    return 0.5 * meta_score + 0.3 * thumb_score + 0.2 * keyword_score


def is_image_ad(ad: dict) -> bool:
    """判定广告是否为图片广告"""
    return calculate_image_score(ad) >= IMAGE_SCORE_THRESHOLD


def classify_batch(ads: List[dict]) -> Dict[str, List[dict]]:
    """批量分类广告为 image / video / uncertain

    Returns:
        {"image": [...], "video": [...], "uncertain": [...]}
    """
    result = {"image": [], "video": [], "uncertain": []}

    for ad in ads:
        score = calculate_image_score(ad)
        if score >= IMAGE_SCORE_THRESHOLD:
            result["image"].append(ad)
        elif score <= 0.3:
            result["video"].append(ad)
        else:
            result["uncertain"].append(ad)

    return result
