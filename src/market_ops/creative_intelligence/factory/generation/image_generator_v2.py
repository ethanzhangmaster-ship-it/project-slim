"""Image Generator V2 — Phase 1 统一图像生成器。

替换 creative_image_gen.py 的角色（旧模块保留不动，不影响现有 ua_renderer /
hybrid_renderer / golden_sample_verify）。

Phase 1 仅支持：Reference Mutation Mode
- 以赢家参考图为 img2img 锚点（Lovart attachments）
- 保留：角色身份 / 色调 / 视觉层级
- 变化：背景 / 奖励物 / 构图细节
- 生成 count 张差异化创意，逐张落盘到 creatives/

提供 dry_run 模式（本地占位图，不调用 Lovart、不消耗额度），
用于在不烧 API 的情况下验证整条管线接线。
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from market_ops.clients.lovart import LovartClient, download_image  # noqa: E402


# --- Reference Mutation 变化库（P04 Witch 主题）----------------------------
_BACKGROUNDS = [
    "an enchanted moonlit forest with glowing mushrooms",
    "an ancient gothic library with floating candles",
    "a stormy volcanic crater with rivers of lava",
    "a serene magical lake reflecting the night sky",
    "a crystal cavern with bioluminescent crystals",
    "a floating sky island above the clouds",
    "a mysterious witch's potion lab with shelves of jars",
    "a snowy mountain peak at dawn",
    "a haunted carnival at midnight",
    "an underwater coral palace with light rays",
]
_REWARD_OBJECTS = [
    "a legendary shadow dragon egg cracking open",
    "a crown of pure starlight",
    "a glowing fusion crystal pulsing with energy",
    "a mythical phoenix feather",
    "a treasure chest overflowing with enchanted coins",
    "a blooming celestial flower",
    "a miniature floating castle",
    "a prism of captured magic",
    "a golden grimoire glowing with runes",
    "a swirling galaxy orb",
]
_COMPOSITIONS = [
    "split-screen: messy before vs polished after merge",
    "close-up hero shot with minimal game UI at the edges",
    "diagonal composition leading the eye to the reward",
    "central symmetry with the character framed by magic circles",
    "rule-of-thirds with the reward at a power point",
    "layered depth: foreground character, midground reward, background castle",
    "top-to-bottom progression arrow showing merge stages",
    "wide cinematic frame with strong leading lines",
    "tight crop emphasizing the reward object",
    "dynamic diagonal burst of magical particles",
]


def _build_prompt(dna: dict[str, Any], idx: int) -> str:
    palette = dna.get("palette") or "deep purple and gold, magical glow"
    bg = _BACKGROUNDS[idx % len(_BACKGROUNDS)]
    rw = _REWARD_OBJECTS[(idx * 3) % len(_REWARD_OBJECTS)]
    cp = _COMPOSITIONS[(idx * 7) % len(_COMPOSITIONS)]
    return (
        "Use this winning UA creative as reference.\n\n"
        "Preserve:\n"
        "- character identity (the main subject / witch)\n"
        f"- color palette: {palette}\n"
        "- visual hierarchy and brand feel\n\n"
        "Change:\n"
        f"- background: {bg}\n"
        f"- reward object: {rw}\n"
        f"- composition details: {cp}\n\n"
        "Create a new mobile game ad creative for P04 Witch, a dark fantasy merge "
        "puzzle game. 1:1 square 1080x1080, professional Facebook ad quality. "
        "No watermarks, no realistic photos, no unrelated UI."
    )


def _build_prompt_from_variant(variant: dict[str, Any], base: dict[str, Any]) -> str:
    """Phase 2：基于变异后 DNA 构建 img2img 提示词。

    保留核心维度（character / color），按变异 DNA 明确改变 reward / background /
    composition / hook，使每张图对应一个具体创意方向。
    """
    character = variant.get("character") or base.get("character") or "the main witch character"
    palette = variant.get("color") or base.get("color") or "deep purple and gold"
    bg = variant.get("background") or "an enchanted environment"
    rw = variant.get("reward") or "a magical reward"
    cp = variant.get("composition") or "balanced hero composition"
    hook = variant.get("hook") or base.get("hook") or "collection"
    return (
        "Use this winning UA creative as reference.\n\n"
        "Preserve:\n"
        f"- character identity: {character}\n"
        f"- color palette: {palette}\n"
        "- visual hierarchy and brand feel\n\n"
        "Change (per mutation brief):\n"
        f"- reward object: {rw}\n"
        f"- background: {bg}\n"
        f"- composition: {cp}\n"
        f"- hook: {hook}\n\n"
        f"Mutation note: {variant.get('mutation_reason', '')}\n\n"
        "Create a new mobile game ad creative for P04 Witch, a dark fantasy merge "
        "puzzle game. 1:1 square 1080x1080, professional Facebook ad quality. "
        "No watermarks, no realistic photos, no unrelated UI."
    )


class ImageGeneratorV2:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self._lovart: LovartClient | None = None
        if not dry_run:
            # 缺 AK/SK 时在此直接抛错（明确终止，不静默降级）
            self._lovart = LovartClient()

    # ------------------------------------------------------------------
    def generate(
        self,
        context: Any,
        reference_image: dict[str, Any],
        count: int = 50,
        dna_variants: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """生成 count 张创意，返回批次结果（不含 batch_metadata.json 的持久化，
        由 CreativeFactory 负责写入）。

        Args:
            dna_variants: Phase 2 传入的变异 DNA 列表（每个含 mutation_id/dna/
                mutation_reason）。若提供，逐张绑定变异元数据，并以变异 DNA 构建
                提示词；若为空，回退到 Phase 1 行为（保留 winner DNA + 轮换变化）。
        """
        if dna_variants is not None and len(dna_variants) < count:
            raise ValueError(
                f"dna_variants 数量({len(dna_variants)})少于 count({count})"
            )

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        batch_id = f"batch_{ts}_{uuid.uuid4().hex[:6]}"
        batch_dir = Path(context.output_dir) / batch_id
        creatives_dir = batch_dir / "creatives"
        creatives_dir.mkdir(parents=True, exist_ok=True)

        winner_code = context.winner_code or "000"
        ref_url = (reference_image.get("url") or "").strip()
        ref_filename = f"winner_{winner_code}.png"
        model = context.metadata.get("model") or (
            self._lovart._models[0] if self._lovart else "dry-run"
        )
        base_dna = context.winner_dna or {}

        creatives: list[dict[str, Any]] = []
        for i in range(count):
            if dna_variants is not None:
                v = dna_variants[i]
                variant_dna = v.get("dna", {})
                mutation_id = v.get("mutation_id", f"mut_{i + 1:03d}")
                prompt = _build_prompt_from_variant(variant_dna, base_dna)
                gen_mode = "dna_mutation"
            else:
                variant_dna = {
                    "theme": base_dna.get("theme", ""),
                    "palette": base_dna.get("palette", ""),
                }
                mutation_id = None
                prompt = _build_prompt(base_dna, i)
                gen_mode = "reference_mutation"

            creative_id = f"p04_{winner_code}_{i + 1:03d}"
            dest = creatives_dir / f"{i + 1:03d}.png"

            status = "ready"
            if self.dry_run:
                self._write_placeholder(dest, i)
            else:
                status = self._generate_one(prompt, ref_url, dest)

            creatives.append({
                "creative_id": creative_id,
                "mutation_id": mutation_id,
                "winner_id": context.winner_id,
                "generation_mode": gen_mode,
                "reference_image": ref_filename,
                "file": str(dest),
                "prompt": prompt,
                "dna": variant_dna,
                "mutation_reason": (dna_variants[i].get("mutation_reason", "") if dna_variants else ""),
                "model": model,
                "status": status,
                "created_at": datetime.now().isoformat(),
            })

        return {
            "batch_id": batch_id,
            "batch_dir": str(batch_dir),
            "creatives_dir": str(creatives_dir),
            "creatives": creatives,
            "model": model,
            "dry_run": self.dry_run,
        }

    # ------------------------------------------------------------------
    def _generate_one(self, prompt: str, ref_url: str, dest: Path) -> str:
        assert self._lovart is not None
        attachments = [ref_url] if ref_url else None
        result = self._lovart.generate_image(prompt, attachments=attachments)
        if result.status == "done" and result.image_urls:
            try:
                download_image(result.image_urls[0], dest)
                return "ready"
            except Exception as exc:
                return f"download_error: {exc}"
        return f"gen_error: {result.status}"

    @staticmethod
    def _write_placeholder(dest: Path, idx: int) -> None:
        from PIL import Image

        # 用稳定但每张略不同的底色，便于肉眼区分
        hue = (idx * 37) % 256
        color = (hue, (hue * 2) % 256, (255 - hue) % 256)
        img = Image.new("RGB", (1080, 1080), color)
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "PNG")
