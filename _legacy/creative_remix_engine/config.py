"""系统配置 V3.1"""
from pathlib import Path

BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage"
RECIPE_DIR = STORAGE_DIR / "recipes"
OUTPUT_DIR = STORAGE_DIR / "outputs"
MEMORY_DIR = STORAGE_DIR / "memory"

# 数据源路径（复用已有数据）
DATA_ROOT = Path("d:/project_slim/project_slim/output/video_intelligence/p04")
ADJUST_CSV = DATA_ROOT / "final_adjust_material_report.csv"
EAGLE_INDEX = DATA_ROOT / "eagle_assets_full.json"
VIDEO_SOURCE_DIR = Path("d:/project_slim/output/P04_remix_videos/广告视频")
VIDEO_ANALYSIS_DIR = Path("d:/project_slim/output/video_analysis")

# DNA 结构模板
DNA_TEMPLATES = {
    "standard_30s": [
        {"role": "hook", "duration": 3, "weight": 0.35},
        {"role": "problem", "duration": 5, "weight": 0.15},
        {"role": "gameplay", "duration": 15, "weight": 0.30},
        {"role": "reward", "duration": 4, "weight": 0.15},
        {"role": "cta", "duration": 3, "weight": 0.05},
    ],
    "bomb_15s": [
        {"role": "hook", "duration": 2, "weight": 0.40},
        {"role": "gameplay", "duration": 8, "weight": 0.35},
        {"role": "reward", "duration": 3, "weight": 0.20},
        {"role": "cta", "duration": 2, "weight": 0.05},
    ],
    "story_40s": [
        {"role": "hook", "duration": 3, "weight": 0.25},
        {"role": "problem", "duration": 7, "weight": 0.20},
        {"role": "gameplay", "duration": 20, "weight": 0.30},
        {"role": "reward", "duration": 7, "weight": 0.20},
        {"role": "cta", "duration": 3, "weight": 0.05},
    ],
}

# 内容类型到 DNA 角色映射
CONTENT_ROLE_MAP = {
    "角色展示": ["reward", "hook"],
    "剧情": ["problem", "reward"],
    "文字滚动": ["problem", "cta"],
    "开场": ["hook"],
    "场景展示": ["hook", "problem"],
    "玩法展示": ["gameplay"],
    "宠物展示": ["hook", "reward"],
    "其他": ["hook"],
}

# 视频比例分类
RATIO_CLASSES = {
    "9X16": {"width": 1080, "height": 1920, "target_ratio": 9/16},
    "1X1": {"width": 1080, "height": 1080, "target_ratio": 1.0},
    "16X9": {"width": 1920, "height": 1080, "target_ratio": 16/9},
}

# V3.0 评分权重（保留兼容）
SCORE_WEIGHTS = {
    "roas": 0.35,
    "purchase_rate": 0.25,
    "visual_match": 0.20,
    "retention": 0.10,
    "freshness": 0.10,
}

# V3.1 Material Ranking V2 权重
SCORE_WEIGHTS_V2 = {
    "roas": 0.30,
    "purchase_rate": 0.25,
    "dna_match": 0.20,
    "visual_quality": 0.15,
    "freshness": 0.10,
}

# Segment Score 权重
SEGMENT_WEIGHTS = {
    "hook_impact": 0.35,
    "motion": 0.25,
    "emotion": 0.20,
    "gameplay_match": 0.20,
}

# Mutation 配置
MUTATION_CONFIG = {
    "hook_variants": [
        "dragon_attack", "witch_rescue", "castle_collapse",
        "magic_explosion", "pet_summon", "boss_appear"
    ],
    "gameplay_variants": [
        "fast_merge", "combo_merge", "upgrade_reveal",
        "rare_item", "skill_cast", "transform"
    ],
    "ending_variants": [
        "character_reward", "castle_unlock", "cta_download",
        "power_up", "new_world", "treasure_open"
    ],
}

# Winner DNA 默认配置
DEFAULT_WINNER_DNA = {
    "theme": ["witch", "dragon", "castle"],
    "visual_style": ["high_contrast", "bright_color", "dynamic"],
    "structure": ["hook", "problem", "gameplay", "reward", "cta"],
    "emotion_arc": ["curiosity", "tension", "excitement", "satisfaction"],
}

# ffmpeg 参数
FFMPEG_PRESET = "fast"
FFMPEG_CRF = 18
FADE_DURATION = 0.3

# 预测模型阈值
PREDICTION_THRESHOLDS = {
    "test": 80,
    "test_low_budget": 60,
    "skip": 0,
}

# 批量生成默认数量
DEFAULT_BATCH_SIZE = 100
TOP_N_ASSEMBLE = 10
