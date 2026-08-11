"""Reference-grounded image production with deterministic copy and real gates."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from market_ops.clients.lovart import LovartClient
from market_ops.creative_image_pipeline.image_quality_gate import ImageQualityGate
from market_ops.lovart_adapter import LovartAPIAdapter


@dataclass(slots=True)
class ProductionCandidate:
    candidate_id: str
    raw_path: str
    final_path: str
    prompt: str
    evaluation: dict = field(default_factory=dict)
    structural_score: float = 0.0
    passed: bool = False
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProductionResult:
    run_id: str
    selected_path: str
    parent_creative_id: str
    candidates: list[ProductionCandidate]
    manifest_path: str


class ReferenceGroundedPromptCompiler:
    """Compile product truth and winner DNA into an executable image brief."""

    def __init__(self, product_profile: dict, winner: dict) -> None:
        self.product = product_profile
        self.winner = winner

    def compile(self, emphasis: str) -> tuple[str, str]:
        visual = self.product["visual_truth"]
        gameplay = self.product["gameplay_truth"]
        forbidden = self.product["forbidden"]
        winner_dna = self.winner.get("visual_dna_summary", {})
        prompt = f"""Use case: ads-marketing
Asset type: production-ready 9:16 mobile game acquisition image
Reference roles:
- Reference 1 is the historical performance winner. Preserve only its immediate transformation hierarchy, centered payoff, purple-gold magic energy and strong top-to-bottom reading.
- References 2 and 3 are official Merge Witches screenshots. They are authoritative for product art style, isometric board, characters, merge objects, colors and gameplay truth.

Primary request: Create a PRODUCT-FIRST Merge Witches advertisement that looks unmistakably like the official game rather than a generic fantasy poster. On a bright isometric floating grass board, show exactly THREE identical purple witch hats arranged as a clear merge triangle. Three luminous trails converge into ONE upgraded cheerful young witch standing in a magical burst below them. The merge equation must be understandable without text.

Art direction: {visual['render_style']}; {visual['camera']}; palette {', '.join(visual['palette'])}. Characters: {visual['characters']}. World: {visual['world']}.
Historical winner DNA to retain: {winner_dna.get('mood', '')}; palette accent {winner_dna.get('palette', '')}; centered transformation payoff.
Candidate emphasis: {emphasis}.

Composition: vertical 9:16. Reserve a clean dark-purple translucent header band from 14% to 24% of the image for exact title applied later. Reserve a clean footer band from 72% to 84% for exact tagline applied later. Keep the three hats and upgraded witch fully inside the central safe area. Large readable objects; one focal story; no tiny clutter.
Text: render NO text at all. Final brand copy is added deterministically after generation.
Product truth: {'; '.join(gameplay)}.
Required count: exactly three intact source hats; exactly one upgraded young witch; no other hats or duplicate witches.
Constraints: no UI counters, no buttons, no currency bars, no fake gameplay labels, no watermark. Preserve official product-family proportions and colors.
"""
        negative = "; ".join(forbidden + [
            "any text or letters",
            "more or fewer than exactly three source hats",
            "duplicate characters",
            "dark photorealistic adult witch poster",
            "cropped focal objects",
            "busy interface",
        ])
        return prompt, negative


class ExactCopyRenderer:
    """Apply exact copy after generation; never ask an image model to spell it."""

    def __init__(self, target_size: tuple[int, int] = (1080, 1920)) -> None:
        self.target_size = target_size
        self.fonts = (
            "C:/Windows/Fonts/georgiab.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
        )

    def render(self, source: Path, destination: Path) -> Path:
        image = Image.open(source).convert("RGB")
        image = self._cover(image, self.target_size)
        draw = ImageDraw.Draw(image, "RGBA")
        width, height = image.size
        self._band(draw, (55, 255, width - 55, 455), (30, 8, 56, 178))
        self._band(draw, (55, 1390, width - 55, 1655), (30, 8, 56, 184))
        self._fit_text(draw, "MERGE WITCHES", y=315, max_width=860, start_size=94,
                       fill=(255, 210, 70, 255), stroke=(80, 18, 120, 255), stroke_width=7)
        self._fit_text(draw, "Merge 3. Unlock the Magic.", y=1515, max_width=900, start_size=64,
                       fill=(255, 238, 152, 255), stroke=(91, 25, 122, 255), stroke_width=5)
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, format="PNG", optimize=True)
        return destination

    def _cover(self, image: Image.Image, size: tuple[int, int]) -> Image.Image:
        target_w, target_h = size
        ratio = max(target_w / image.width, target_h / image.height)
        resized = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
        left = (resized.width - target_w) // 2
        top = (resized.height - target_h) // 2
        return resized.crop((left, top, left + target_w, top + target_h))

    @staticmethod
    def _band(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: tuple[int, int, int, int]) -> None:
        draw.rounded_rectangle(box, radius=42, fill=fill, outline=(161, 79, 211, 190), width=4)

    def _font(self, size: int):
        for candidate in self.fonts:
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _fit_text(self, draw: ImageDraw.ImageDraw, text: str, *, y: int, max_width: int,
                  start_size: int, fill: tuple[int, int, int, int],
                  stroke: tuple[int, int, int, int], stroke_width: int) -> None:
        size = start_size
        while size >= 30:
            font = self._font(size)
            box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
            if box[2] - box[0] <= max_width:
                break
            size -= 2
        box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        x = (self.target_size[0] - (box[2] - box[0])) // 2
        draw.text((x, y - (box[3] - box[1]) // 2 - box[1]), text, font=font,
                  fill=fill, stroke_width=stroke_width, stroke_fill=stroke)


class OfficialAssetComposer:
    """Fail-closed fallback built only from verified official product artwork."""

    def __init__(self, target_size: tuple[int, int] = (1080, 1920)) -> None:
        self.target_size = target_size
        self.fonts = (
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/impact.ttf",
            "C:/Windows/Fonts/georgiab.ttf",
        )

    def compose(self, *, home_screen: Path, level_screen: Path, witch_screen: Path, destination: Path) -> Path:
        home = Image.open(home_screen).convert("RGB")
        level = Image.open(level_screen).convert("RGB")
        witch_source = Image.open(witch_screen).convert("RGB")
        canvas = self._background(home)
        draw = ImageDraw.Draw(canvas, "RGBA")

        # Use the real in-game logo rather than asking a model or font to imitate it.
        logo = home.crop((300, 5, 760, 190)).resize((650, 262), Image.Resampling.LANCZOS)
        logo = self._rounded_card(logo, radius=42, border=(255, 207, 55), border_width=6)
        canvas.paste(logo, (215, 90), logo)

        # Official level screenshot: one clean hero card with exactly three eggs.
        gameplay = level.crop((640, 95, 1280, 825)).resize((880, 1004), Image.Resampling.LANCZOS)
        gameplay = self._rounded_card(gameplay, radius=48, border=(161, 72, 224), border_width=10)
        canvas.paste(gameplay, (100, 390), gameplay)
        draw = ImageDraw.Draw(canvas, "RGBA")

        # Small rings clarify the merge inputs without obscuring the product art.
        for index, center in enumerate(((424, 851), (658, 851), (541, 1120)), 1):
            x, y = center
            draw.ellipse((x - 71, y - 71, x + 71, y + 71), outline=(255, 222, 75, 245), width=7)
            draw.ellipse((x - 83, y - 83, x + 83, y + 83), outline=(141, 47, 207, 190), width=5)
            draw.ellipse((x - 81, y - 105, x - 31, y - 55), fill=(115, 34, 174, 245),
                         outline=(255, 223, 87, 255), width=3)
            self._text_at(draw, str(index), center=(x - 56, y - 80), max_width=30, start_size=30,
                          fill=(255, 255, 255, 255), stroke=(70, 14, 105, 255), stroke_width=1)

        # Bottom payoff panel keeps the new witch large and phone-readable.
        draw.rounded_rectangle((100, 1440, 980, 1770), radius=48, fill=(47, 16, 79, 235),
                               outline=(164, 72, 224, 245), width=7)
        witch = witch_source.crop((615, 55, 850, 395)).resize((280, 405), Image.Resampling.LANCZOS)
        witch = self._rounded_card(witch, radius=92, border=(255, 208, 61), border_width=7)
        canvas.paste(witch, (650, 1400), witch)
        draw = ImageDraw.Draw(canvas, "RGBA")
        self._down_arrow(draw, center_x=540, top=1350, bottom=1450)
        self._text_at(draw, "MERGE 3", center=(360, 1525), max_width=430, start_size=82,
                      fill=(255, 215, 55, 255), stroke=(103, 30, 157, 255), stroke_width=6)
        self._text_at(draw, "MEET YOUR", center=(350, 1625), max_width=420, start_size=50,
                      fill=(255, 255, 255, 255), stroke=(92, 22, 139, 255), stroke_width=4)
        self._text_at(draw, "NEW WITCH", center=(350, 1695), max_width=460, start_size=58,
                      fill=(255, 238, 136, 255), stroke=(92, 22, 139, 255), stroke_width=4)

        destination.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(destination, format="PNG", optimize=True)
        return destination

    def _background(self, image: Image.Image) -> Image.Image:
        target_w, target_h = self.target_size
        ratio = max(target_w / image.width, target_h / image.height)
        resized = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
        left = (resized.width - target_w) // 2
        top = (resized.height - target_h) // 2
        background = resized.crop((left, top, left + target_w, top + target_h)).filter(ImageFilter.GaussianBlur(24))
        overlay = Image.new("RGBA", self.target_size, (20, 7, 45, 158))
        return Image.alpha_composite(background.convert("RGBA"), overlay)

    @staticmethod
    def _rounded_card(image: Image.Image, *, radius: int, border: tuple[int, int, int], border_width: int) -> Image.Image:
        card = image.convert("RGBA")
        mask = Image.new("L", card.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width, card.height), radius=radius, fill=255)
        framed = Image.new("RGBA", (card.width + border_width * 2, card.height + border_width * 2), (0, 0, 0, 0))
        frame_draw = ImageDraw.Draw(framed)
        frame_draw.rounded_rectangle((0, 0, framed.width - 1, framed.height - 1), radius=radius + border_width,
                                     fill=(*border, 255))
        framed.paste(card, (border_width, border_width), mask)
        return framed.resize(image.size, Image.Resampling.LANCZOS)

    def _font(self, size: int):
        for candidate in self.fonts:
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _text(self, draw: ImageDraw.ImageDraw, text: str, *, center_y: int, max_width: int,
              start_size: int, fill: tuple[int, int, int, int], stroke: tuple[int, int, int, int],
              stroke_width: int) -> None:
        size = start_size
        while size >= 28:
            font = self._font(size)
            bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
            if bbox[2] - bbox[0] <= max_width:
                break
            size -= 2
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        x = (self.target_size[0] - (bbox[2] - bbox[0])) // 2
        y = center_y - (bbox[3] - bbox[1]) // 2 - bbox[1]
        draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke)

    def _text_at(self, draw: ImageDraw.ImageDraw, text: str, *, center: tuple[int, int], max_width: int,
                 start_size: int, fill: tuple[int, int, int, int], stroke: tuple[int, int, int, int],
                 stroke_width: int) -> None:
        size = start_size
        while size >= 24:
            font = self._font(size)
            bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
            if bbox[2] - bbox[0] <= max_width:
                break
            size -= 2
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        x = center[0] - (bbox[2] - bbox[0]) // 2
        y = center[1] - (bbox[3] - bbox[1]) // 2 - bbox[1]
        draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke)

    @staticmethod
    def _down_arrow(draw: ImageDraw.ImageDraw, *, center_x: int, top: int, bottom: int) -> None:
        draw.rounded_rectangle((center_x - 15, top, center_x + 15, bottom - 35), radius=12,
                               fill=(255, 215, 68, 255), outline=(104, 31, 155, 255), width=5)
        draw.polygon(((center_x - 65, bottom - 50), (center_x + 65, bottom - 50), (center_x, bottom + 18)),
                     fill=(255, 215, 68, 255), outline=(104, 31, 155, 255))


class CreativeProductionLoop:
    """Generate, materialize, score, reject and select a creative."""

    EMPHASES = (
        "authentic gameplay board and unmistakable merge-3 clarity",
        "strong magical reward burst while retaining official casual-game style",
        "largest phone-readable hats and upgraded witch with minimal background clutter",
    )

    def __init__(self, root: Path) -> None:
        self.root = root
        self.profile = json.loads((root / "config/creative_product_profile_merge_witches.json").read_text(encoding="utf-8"))
        ranking = json.loads((root / "output/creative_analysis/winner_ranking_v2.json").read_text(encoding="utf-8"))
        self.winner = ranking["balanced_winner"]
        self.prompt_compiler = ReferenceGroundedPromptCompiler(self.profile, self.winner)
        self.renderer = ExactCopyRenderer()
        self.generator = LovartAPIAdapter(
            access_key=os.getenv("LOVART_ACCESS_KEY"),
            secret_key=os.getenv("LOVART_SECRET_KEY"),
            timeout=100,
        )
        self.client = LovartClient(
            access_key=os.getenv("LOVART_ACCESS_KEY"),
            secret_key=os.getenv("LOVART_SECRET_KEY"),
        )

    def run(
        self,
        output_dir: Path,
        product_reference_paths: list[Path],
        product_reference_urls: list[str] | None = None,
    ) -> ProductionResult:
        run_id = f"merge-witches-{uuid.uuid4().hex[:10]}"
        run_dir = output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        product_urls = product_reference_urls or [self.client.upload_file(path) for path in product_reference_paths]
        attachments = [self.winner["cdn_url"], *product_urls]
        candidates: list[ProductionCandidate] = []

        for index, emphasis in enumerate(self.EMPHASES, 1):
            prompt, negative = self.prompt_compiler.compile(emphasis)
            result = self.generator.generate(
                prompt=prompt,
                negative_prompt=negative,
                size="1080x1920",
                attachments=attachments,
            )
            if not result.success:
                candidates.append(ProductionCandidate(
                    candidate_id=f"c{index}", raw_path="", final_path="", prompt=prompt,
                    passed=False, rejection_reasons=[result.error],
                ))
                continue
            raw = run_dir / f"candidate_{index}_raw.png"
            self._download(result.image_url, raw)
            final = run_dir / f"candidate_{index}_final.png"
            self.renderer.render(raw, final)
            candidate = self._review(f"c{index}", raw, final, prompt)
            candidates.append(candidate)

        eligible = [candidate for candidate in candidates if candidate.passed]
        pool = eligible or [candidate for candidate in candidates if candidate.final_path]
        if not pool:
            raise RuntimeError("No creative candidate could be materialized")
        selected = max(pool, key=self._score)
        selected_path = output_dir / "merge-witches-closed-loop-final.png"
        selected_path.write_bytes(Path(selected.final_path).read_bytes())
        manifest = {
            "run_id": run_id,
            "product": self.profile,
            "parent_winner": self.winner,
            "reference_paths": [str(path.resolve()) for path in product_reference_paths],
            "selected_candidate": selected.candidate_id,
            "selected_path": str(selected_path.resolve()),
            "selected_sha256": hashlib.sha256(selected_path.read_bytes()).hexdigest(),
            "candidates": [asdict(candidate) for candidate in candidates],
        }
        manifest_path = run_dir / "production_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return ProductionResult(run_id, str(selected_path.resolve()), self.winner["creative_id"], candidates, str(manifest_path.resolve()))

    def _review(self, candidate_id: str, raw: Path, final: Path, prompt: str) -> ProductionCandidate:
        structural = ImageQualityGate(strict=True).validate(str(final))
        evaluation = self.client.evaluate_image(final, prompt, project="Merge Witches", hook_type="merge-3 transformation")
        reasons: list[str] = []
        if not structural.passed:
            reasons.append("structural_gate_failed")
        for key in ("visual_quality", "brand_alignment", "hook_clarity", "ad_suitability"):
            value = float(evaluation.get(key, 0) or 0)
            if value < 7:
                reasons.append(f"{key}_below_7:{value}")
        if evaluation.get("error"):
            reasons.append(f"evaluation_error:{evaluation['error']}")
        return ProductionCandidate(
            candidate_id=candidate_id,
            raw_path=str(raw.resolve()),
            final_path=str(final.resolve()),
            prompt=prompt,
            evaluation=evaluation,
            structural_score=structural.score,
            passed=not reasons,
            rejection_reasons=reasons,
        )

    @staticmethod
    def _score(candidate: ProductionCandidate) -> float:
        evaluation = candidate.evaluation
        dimensions = ("visual_quality", "brand_alignment", "hook_clarity", "ad_suitability")
        return candidate.structural_score + sum(float(evaluation.get(key, 0) or 0) for key in dimensions) * 2.5

    @staticmethod
    def _download(url: str, destination: Path) -> None:
        temporary = destination.with_suffix(destination.suffix + ".part")
        last_error: Exception | None = None
        for attempt in range(1, 5):
            try:
                request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "image/*"})
                with urlopen(request, timeout=120) as response, temporary.open("wb") as output:
                    expected = int(response.headers.get("Content-Length") or 0)
                    received = 0
                    while True:
                        chunk = response.read(128 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        received += len(chunk)
                if expected and received != expected:
                    raise OSError(f"Incomplete image download: {received}/{expected} bytes")
                with Image.open(temporary) as image:
                    image.verify()
                temporary.replace(destination)
                return
            except Exception as exc:
                last_error = exc
                temporary.unlink(missing_ok=True)
                if attempt < 4:
                    time.sleep(attempt * 1.5)
        raise OSError(f"Image download failed after retries: {last_error}")
