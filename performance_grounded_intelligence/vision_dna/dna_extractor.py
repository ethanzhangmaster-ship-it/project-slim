"""Vision DNA Extractor — 综合 DNA 提取入口

调用 composition/gameplay/reward/style 分析器,
综合输出 true_winner_dna.json。

需要 OpenAI API (gpt-4o with vision) 或降级到规则模式。
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from ..config import OUTPUT_DIR, VISION_MODEL, DNA_MAX_WINNERS, WINNERS_DIR, ensure_dirs

# OpenAI API 可选
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


VISION_PROMPT = """Analyze this mobile game ad image (Merge Dragon-like puzzle game).
Return a JSON object with:

{
  "composition": {
    "gameplay_area": {"ratio": 0.0-1.0, "position": "center/top/bottom/left/right"},
    "reward_area": {"ratio": 0.0-1.0, "position": "..."},
    "character_area": {"ratio": 0.0-1.0, "position": "..."},
    "background_area": {"ratio": 0.0-1.0}
  },
  "gameplay": {
    "type": "merge_board|before_after|upgrade_arrow|progression|mixed",
    "elements": ["merge_items", "board_grid", "arrows", "numbers"]
  },
  "reward": {
    "type": "dragon|castle|magic_item|rare_reward|character|mixed",
    "elements": ["dragon", "castle", "gems", "chest"]
  },
  "style": {
    "color_palette": "purple_gold|green_nature|blue_magic|warm_sunset|dark_fantasy",
    "lighting": "magic_glow|natural|dramatic|flat",
    "camera": "top_down|isometric|front|close_up",
    "render_style": "3d_cartoon|2d_flat|semi_realistic|painted"
  },
  "hook": "merge_upgrade|reward_reveal|character_action|before_after|level_challenge",
  "layout": "center_merge|split_compare|reward_focus|character_center|full_board"
}

Only return the JSON, no explanations."""


class DNAExtractor:
    """True Winner Vision DNA 提取器"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = None
        if HAS_OPENAI and self.api_key:
            self.client = OpenAI(api_key=self.api_key)

    def extract_from_winners(self, winner_assets: List[dict],
                             thumbnails_dir: Optional[Path] = None) -> List[dict]:
        """从 winner assets 提取 DNA

        Args:
            winner_assets: winner pool 中的 assets (含 source_ad_ids, thumbnail_urls)
            thumbnails_dir: 缩略图目录

        Returns:
            带 DNA 标注的 winner 列表
        """
        ensure_dirs()

        results = []
        max_n = min(len(winner_assets), DNA_MAX_WINNERS)

        print(f"[DNAExtractor] 分析 Top {max_n} winners...")

        for i, asset in enumerate(winner_assets[:max_n]):
            asset_id = asset.get("asset_id", f"unknown_{i}")
            print(f"  [{i+1}/{max_n}] {asset_id}")

            # 尝试获取图片路径
            image_path = self._find_image(asset, thumbnails_dir)

            if image_path and self.client:
                dna = self._extract_with_vision(image_path)
            else:
                dna = self._extract_rule_based(asset)

            results.append({
                "asset_id": asset_id,
                "performance": {
                    "spend": asset.get("spend", 0),
                    "iap_roas": asset.get("iap_roas", 0),
                    "all_revenue": asset.get("all_revenue", 0),
                    "installs": asset.get("installs", 0),
                    "cpi": asset.get("cpi", 0),
                },
                "dna": dna,
                "sample_names": asset.get("sample_names", [])[:3],
                "thumbnail_urls": asset.get("thumbnail_urls", [])[:1],
            })

        # 保存
        output_path = OUTPUT_DIR / "true_winner_dna.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": "2.1.8",
                "total": len(results),
                "winners": results,
            }, f, ensure_ascii=False, indent=2)

        print(f"[DNAExtractor] 已保存: {output_path}")
        return results

    def _find_image(self, asset: dict, thumbnails_dir: Optional[Path]) -> Optional[Path]:
        """查找 asset 对应的本地缩略图"""
        if not thumbnails_dir:
            from ..config import THUMBNAILS_DIR
            thumbnails_dir = THUMBNAILS_DIR

        for ad_id in asset.get("source_ad_ids", []):
            path = thumbnails_dir / f"{ad_id}.jpg"
            if path.exists():
                return path
        return None

    def _extract_with_vision(self, image_path: Path) -> dict:
        """使用 GPT-4o Vision 提取 DNA"""
        import base64

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        try:
            response = self.client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }}
                    ]
                }],
                max_tokens=1000,
                temperature=0.1,
            )

            content = response.choices[0].message.content
            # 解析 JSON
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(content)

        except Exception as e:
            print(f"    Vision API 失败: {e}")
            return self._extract_rule_based({})

    def _extract_rule_based(self, asset: dict) -> dict:
        """规则模式 (无 API 时的降级方案)"""
        names = " ".join(asset.get("sample_names", []))
        names_lower = names.lower()

        # 基于广告名推断
        gameplay_type = "merge_board"
        if "before" in names_lower or "对比" in names_lower:
            gameplay_type = "before_after"

        reward_type = "mixed"
        if "龙" in names or "dragon" in names_lower:
            reward_type = "dragon"
        elif "城堡" in names or "castle" in names_lower:
            reward_type = "castle"

        return {
            "composition": {
                "gameplay_area": {"ratio": 0.50, "position": "center"},
                "reward_area": {"ratio": 0.25, "position": "top_right"},
                "character_area": {"ratio": 0.15, "position": "bottom"},
                "background_area": {"ratio": 0.10},
            },
            "gameplay": {"type": gameplay_type, "elements": ["merge_items", "board_grid"]},
            "reward": {"type": reward_type, "elements": []},
            "style": {
                "color_palette": "purple_gold",
                "lighting": "magic_glow",
                "camera": "isometric",
                "render_style": "3d_cartoon",
            },
            "hook": "merge_upgrade",
            "layout": "center_merge",
            "_source": "rule_based",
        }
