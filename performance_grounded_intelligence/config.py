"""Performance Grounded Intelligence — 全局配置"""
from pathlib import Path

# === 路径配置 ===
BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent

# 数据源路径
DATA_ROOT = PROJECT_ROOT / "output" / "video_intelligence" / "p04"
FB_API_JSON = DATA_ROOT / "p04_full_ad_hierarchy.json"
ADJUST_JSON = DATA_ROOT / "adjust_creative_data.json"
FB_EXCEL_PATH = Path(r"c:\Users\ethan\Downloads\无标题报告11-月-1-2025-7-月-13-2026 (2).xlsx")

# 输出路径
OUTPUT_DIR = PROJECT_ROOT / "output" / "performance_grounded"
THUMBNAILS_DIR = OUTPUT_DIR / "thumbnails"
WINNERS_DIR = OUTPUT_DIR / "winners"
REPORTS_DIR = OUTPUT_DIR / "reports"

# === 图片检测阈值 ===
IMAGE_SCORE_THRESHOLD = 0.7
IMAGE_KEYWORDS = ["图片", "原图", "image", "pic", "static"]

# === Confidence Model 参数 ===
CONFIDENCE_WEIGHTS = {
    "spend": 0.4,
    "installs": 0.3,
    "data_days": 0.3,
}
CONFIDENCE_CAPS = {
    "spend": 3000,       # $3000 满分
    "installs": 100,     # 100 安装满分
    "data_days": 30,     # 30天满分
}

# === Winner Score 参数 ===
WINNER_SCORE_WEIGHTS = {
    "roas": 0.4,
    "scale": 0.3,
    "confidence": 0.2,
    "revpi": 0.1,
}
WINNER_SCORE_CAPS = {
    "roas": 1.0,         # ROAS 100% = 满分
    "scale": 5000,       # $5000 总收入满分
    "revpi": 20,         # $20/install 满分
}

# === Winner Pools 条件 ===
POOL_SCALE = {
    "min_spend": 5000,
    "min_roas": 0.3,
}
POOL_EFFICIENCY = {
    "min_spend": 500,
    "min_roas": 0.8,
}
POOL_PATTERN = {
    "top_percentile": 0.10,  # Top 10%
}

# === Asset Resolver (CLIP) ===
CLIP_MODEL = "ViT-B-32"
CLIP_PRETRAINED = "laion2b_s34b_b79k"
CLUSTER_EPS = 0.15           # DBSCAN eps (cosine distance)
CLUSTER_MIN_SAMPLES = 1

# === Quality Gate V3 ===
WINNER_SIMILARITY_THRESHOLD = 0.75
PRODUCTION_SCORE_WEIGHTS_V3 = {
    "gameplay": 0.25,
    "reward": 0.20,
    "winner_similarity": 0.20,
    "composition": 0.15,
    "visual_quality": 0.10,
    "diversity": 0.10,
}

# === Vision DNA (LLM) ===
VISION_MODEL = "gpt-4o"
DNA_MAX_WINNERS = 20  # 最多分析 Top N winner 的 DNA

# === DNA Evolution Engine ===
DNA_EVOLUTION_DIR = OUTPUT_DIR / "dna_evolution"

# 不可变因素权重 (PRD: Hook=30%, Gameplay=25%, Reward=20%, Composition=15%, Style=10%)
PRESERVE_WEIGHTS = {
    "hook": 0.30,
    "gameplay": 0.25,
    "reward": 0.20,
    "composition": 0.15,
    "style": 0.10,
}

# 变异强度: 每个策略的变异比例
MUTATION_INTENSITIES = {
    "A": 0.40,  # 变异 40% 的维度 (保留 gameplay+reward)
    "B": 0.25,  # 变异 25% 的维度 (保留 composition+hook)
    "C": 0.30,  # 变异 30% 的维度 (保留 reward)
    "D": 0.20,  # 变异 20% 的维度 (保留 style)
}

# Evolution Score 权重
EVOLUTION_SCORE_WEIGHTS = {
    "winner_similarity": 0.35,
    "gameplay_preserve": 0.25,
    "reward_visibility": 0.20,
    "novelty": 0.20,
}

# Evolution Quality Gate 阈值
EVO_SIMILARITY_MIN = 0.70
EVO_DIVERSITY_MIN = 0.25
EVO_GAMEPLAY_MIN = 0.85
EVO_REWARD_MIN = 0.20

# 演化引擎参数
EVO_TOP_WINNERS = 10     # 使用 Top N winner 做变异
EVO_VARIANTS_PER = 4     # 每个 winner 的变异策略数
FB_TEST_BATCH_SIZE = 20  # Facebook 测试批次 TOP N


def ensure_dirs():
    """确保输出目录存在"""
    for d in [OUTPUT_DIR, THUMBNAILS_DIR, WINNERS_DIR, REPORTS_DIR, DNA_EVOLUTION_DIR]:
        d.mkdir(parents=True, exist_ok=True)
