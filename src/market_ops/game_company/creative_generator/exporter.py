import os
import json
from typing import Dict, List, Any
from datetime import datetime

from .variant_engine import CreativeAsset
from .script_generator import ScriptGenerator
from .prompt_generator import PromptGenerator
from .thumbnail_generator import ThumbnailGenerator
from .subtitle_generator import SubtitleGenerator
from .music_selector import MusicSelector
from .cta_generator import CTAGenerator
from .prediction_engine import PredictionEngine


class CreativeExporter:
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                    "output", "creative_generator")
        self._base_dir = base_dir
        self._script_gen = ScriptGenerator()
        self._prompt_gen = PromptGenerator()
        self._thumb_gen = ThumbnailGenerator()
        self._sub_gen = SubtitleGenerator()
        self._music_sel = MusicSelector()
        self._cta_gen = CTAGenerator()
        self._pred_engine = PredictionEngine()

    def ensure_dir(self, path: str):
        os.makedirs(path, exist_ok=True)

    def export_creative(self, asset: CreativeAsset, export_dir: str):
        self.ensure_dir(export_dir)

        prompts_dir = os.path.join(export_dir, "prompts")
        self.ensure_dir(prompts_dir)

        script = self._script_gen.generate(asset)
        self._write_json(os.path.join(export_dir, "script.json"), script)

        prompts = self._prompt_gen.generate_all(asset)
        for platform, data in prompts.items():
            self._write_json(os.path.join(prompts_dir, f"{platform}.json"), data)

        thumb = self._thumb_gen.generate(asset)
        self._write_json(os.path.join(export_dir, "thumbnail.json"), thumb)

        subs = self._sub_gen.generate(asset.hook_type)
        self._write_json(os.path.join(export_dir, "subtitles.json"), subs)

        srt = self._sub_gen.generate_srt(asset.hook_type)
        with open(os.path.join(export_dir, "subtitles.srt"), "w", encoding="utf-8") as f:
            f.write(srt)

        music = self._music_sel.select(asset)
        self._write_json(os.path.join(export_dir, "music.json"), music)

        cta = self._cta_gen.generate(asset.hook_type)
        self._write_json(os.path.join(export_dir, "cta.json"), cta)

        prediction = self._pred_engine.predict(asset)
        self._write_json(os.path.join(export_dir, "prediction.json"), prediction)

        self._write_markdown(os.path.join(export_dir, "script.md"), self._script_gen.to_markdown(script))
        self._write_markdown(os.path.join(export_dir, "creative_brief.md"), self._generate_brief(asset, prediction))
        self._write_markdown(os.path.join(export_dir, "creative_checklist.md"), self._generate_checklist(asset))

    def export_batch(self, assets: List[CreativeAsset]):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        batch_dir = os.path.join(self._base_dir, f"batch_{timestamp}")
        self.ensure_dir(batch_dir)

        predictions = []

        for asset in assets:
            creative_dir = os.path.join(batch_dir, asset.creative_id)
            self.export_creative(asset, creative_dir)
            pred = self._pred_engine.predict(asset)
            predictions.append({
                "creative_id": asset.creative_id,
                "title": asset.title,
                "prediction": pred,
            })

        self._write_json(os.path.join(batch_dir, "batch_summary.json"), {
            "batch_id": timestamp,
            "total_creatives": len(assets),
            "generated_at": datetime.now().isoformat(),
            "creatives": predictions,
        })

        return batch_dir

    def _write_json(self, path: str, data: Any):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _write_markdown(self, path: str, content: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _generate_brief(self, asset: CreativeAsset, prediction: Dict) -> str:
        return f"""# Creative Brief: {asset.title}

**ID:** {asset.creative_id}
**Hook Type:** {asset.hook_type}
**Hero:** {asset.hero.get('name')} with {asset.hero.get('pet')}
**Environment:** {asset.environment.get('name')}
**Merge Object:** {asset.merge_object.get('name')}
**Reward:** {asset.reward.get('name')}
**Camera:** {asset.camera.get('name')}

## Prediction
- Expected ROAS: {prediction.get('predicted_roas')}
- Expected CTR: {prediction.get('predicted_ctr')}
- Confidence: {prediction.get('confidence')}
- Grade: {prediction.get('grade')}

## Style
- Palette: {asset.hero.get('palette')}
- Music: {asset.music.get('genre')} ({asset.music.get('bpm')} BPM)
- CTA: {asset.cta.get('text')}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    def _generate_checklist(self, asset: CreativeAsset) -> str:
        return f"""# Creative Checklist: {asset.creative_id}

## Pre-Production
- [ ] Hook type selected: {asset.hook_type}
- [ ] Hero: {asset.hero.get('name')} with {asset.hero.get('pet')}
- [ ] Environment: {asset.environment.get('name')}
- [ ] Aspect ratio: 9:16
- [ ] Duration: 20 seconds

## Production
- [ ] Subject centered in first frame (center 40%)
- [ ] First frame contrast >= 0.15
- [ ] No text overlay in first 3 seconds
- [ ] Visual structure change between 0.8-3.0s
- [ ] Visual reward event after 6s (brighter + more saturated)
- [ ] CTA in last 3 seconds: '{asset.cta.get('text')}'

## Quality
- [ ] All AI prompts generated (8 platforms)
- [ ] Thumbnail prompt generated
- [ ] Subtitles generated
- [ ] Music recommendation ready
- [ ] Prediction: {asset.creative_id}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    def get_stats(self) -> Dict[str, Any]:
        return {"base_dir": self._base_dir}
