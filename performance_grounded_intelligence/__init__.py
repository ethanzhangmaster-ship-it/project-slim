"""Performance Grounded Creative Intelligence — Phase 2.1.8

真实投放数据 → 真实赚钱素材识别 → 视觉DNA提取 → 生成约束 → Facebook UA可投放素材

Modules:
- data_connector: Facebook + Adjust 数据融合
- asset_resolver: CLIP 视觉聚类 → visual_asset_id
- image_detector: 图片素材多维判定
- winner_miner: Confidence + WinnerScore + 三池输出
- vision_dna: GPT-4o Vision DNA 提取
- quality_gate: Winner Similarity + DNA Match
- reports: HTML 报告 + JSON 导出
"""

__version__ = "2.1.8"
