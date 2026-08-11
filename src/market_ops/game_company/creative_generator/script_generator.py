from typing import Dict, List, Any, Optional
from collections import OrderedDict

from .creative_factory import SUBSCENE_TEMPLATES, HOOK_SCRIPTS
from .variant_engine import CreativeAsset


class ScriptGenerator:
    def __init__(self):
        self._subscenes = SUBSCENE_TEMPLATES

    def generate(self, asset: CreativeAsset, total_duration: float = 20.0) -> Dict[str, Any]:
        hero = asset.hero
        env = asset.environment
        obj = asset.merge_object
        reward = asset.reward
        camera = asset.camera
        hook_script = asset.hook_script

        script = OrderedDict()
        script["title"] = f"Creative Script: {asset.title}"
        script["total_duration"] = f"{total_duration}s"
        script["aspect_ratio"] = "9:16 vertical"
        script["hook_type"] = asset.hook_type
        script["scenes"] = []

        ordered_keys = sorted(self._subscenes.keys())
        for i, key in enumerate(ordered_keys):
            tmpl = self._subscenes[key]
            scene = self._build_scene(tmpl, i + 1, hero, env, obj, reward, camera, hook_script, asset.hook_type)
            script["scenes"].append(scene)

        return script

    def _build_scene(self, tmpl: Dict, scene_num: int, hero: Dict, env: Dict, obj: Dict, reward: Dict, camera: Dict, hook_script: Dict, hook_type: str = "collection") -> Dict:
        hname = hero.get("name", "Witch")
        pname = hero.get("pet", "Companion")
        ename = env.get("name", "Magic World")
        oname = obj.get("name", "items")
        rname = reward.get("name", "Reward")
        cam_name = camera.get("name", "Center Shot")
        cam_angle = camera.get("angle", "eye level")
        cam_move = camera.get("movement", "still")
        hook_line = hook_script.get("hook_line", "Welcome!")
        env_light = env.get("lighting", "natural")
        reward_effect = reward.get("effect", "magical effects")

        hooks = HOOK_SCRIPTS.get(hook_type, HOOK_SCRIPTS["collection"])

        cta_text = hook_script.get("cta_text", "Download Now!")

        scene_actions = {
            1: f"{hname} appears in center frame with {pname}. {env_light} lighting. {cam_angle} angle. {hname} looks directly at viewer, smiles mysteriously. {pname} glows with magical energy.",
            2: f"{pname} moves forward, interacts with {hname}. First {oname} appears. Camera: {cam_name}, {cam_move}. {hname} gestures toward the {oname}, inviting viewer to interact.",
            3: f"Merge gameplay: {oname} merge chain shown ({obj.get('chain', 'merge progression')}). Arrows indicate merge path. Numbers show progress: 1/200, 5/200, 15/200. {hname} nods approvingly.",
            4: f"REWARD MOMENT: {rname}! {reward_effect}. Screen brightness surges. Saturation increases. Particle effects fill frame. {hname} and {pname} celebrate together.",
            5: f"More merge variety: different {oname} combinations shown. Each merge produces unique results. Collection counter fills up faster. {hname} waves wand, more items appear.",
            6: f"Collection showcase: ALL creatures/items displayed in grid. Counter reaches 200/200. Celebration animation. {hname} stands proudly with full collection. {pname} jumps with joy.",
            7: f"Social proof overlay: '4.8★ - 500,000+ Players' appears. {hname} gives thumbs up. App store badges shown. 'Top 10 Merge Game 2026' badge displayed.",
            8: f"CTA: {hname} points at screen. {pname} nods. CTA button pulses: '{cta_text}'. App Store + Google Play badges. {hname} waves goodbye.",
        }

        action = scene_actions.get(scene_num, f"{hname} continues adventure in {ename}.")

        script = {
            "scene": scene_num,
            "time": tmpl["time"],
            "category": tmpl["category"],
            "duration": f"{tmpl['duration']}s",
            "target": hook_line if scene_num == 1 else "",
            "camera": f"{cam_name}: {cam_angle}, {cam_move}" if scene_num in (1, 2, 8) else f"Dynamic, following action",
            "action": action,
            "narration": self._get_narration(scene_num, hook_line, hooks, hname, oname, rname),
            "subtitles": self._get_subtitles(scene_num, hook_line, cta_text),
            "effects": self._get_effects(scene_num, reward_effect),
            "transition": self._get_transition(scene_num),
        }
        return script

    def _get_narration(self, scene_num: int, hook_line: str, hooks: Dict, hname: str, oname: str, rname: str) -> str:
        lines = {
            1: hook_line,
            2: f"Meet {hname} and their magical companion! Together they'll discover incredible {oname}.",
            3: f"Merge {oname} to unlock more powerful forms. Each merge brings you closer to legendary items!",
            4: f"{rname}! This is what you've been waiting for!",
            5: f"But wait, there's more! Combine different {oname} for surprising results!",
            6: f"Collect them all! Over 200 unique creatures and items await!",
            7: f"Join 500,000+ players who are already merging and collecting!",
            8: f"Start your magical journey today! Download FREE!",
        }
        return lines.get(scene_num, "")

    def _get_subtitles(self, scene_num: int, hook_line: str, cta_text: str) -> str:
        lines = {
            1: hook_line,
            2: "Meet your magical companion!",
            3: "Merge to evolve!",
            4: "LEGENDARY UNLOCKED!",
            5: "Discover new combinations!",
            6: "200+ Creatures to Collect!",
            7: "500,000+ Happy Players",
            8: cta_text,
        }
        return lines.get(scene_num, "")

    def _get_effects(self, scene_num: int, reward_effect: str) -> str:
        effects = {
            1: "Soft glow around character, magical sparkles",
            2: "Pet appears with light particles, fairy dust trail",
            3: "Merge flash, progress bar fills, UI animations",
            4: reward_effect,
            5: "Colorful merge animations, variety of particle colors",
            6: "Collection grid animation, celebration fireworks",
            7: "Social proof fade-in, star ratings animation",
            8: "CTA pulse glow, button hover effect, badges shine",
        }
        return effects.get(scene_num, "Standard magical effects")

    def _get_transition(self, scene_num: int) -> str:
        transitions = {
            1: "Cut (instant)",
            2: "Soft fade with particles",
            3: "Swipe right (gameplay reveal)",
            4: "Flash burst (reward impact)",
            5: "Smooth crossfade",
            6: "Zoom out (collection reveal)",
            7: "Fade up (text overlay)",
            8: "Hold on CTA (no transition)",
        }
        return transitions.get(scene_num, "Crossfade")

    def to_markdown(self, script: Dict[str, Any]) -> str:
        md = f"""# {script['title']}

**Total Duration:** {script['total_duration']}
**Aspect Ratio:** {script['aspect_ratio']}
**Hook Type:** {script['hook_type']}

## Scenes

"""
        for scene in script["scenes"]:
            md += f"""### Scene {scene['scene']}: {scene['time']} [{scene['category'].upper()}]
**Duration:** {scene['duration']}
**Camera:** {scene['camera']}
**Action:**
{scene['action']}
**Narration:** {scene['narration']}
**Subtitles:** {scene['subtitles']}
**Effects:** {scene['effects']}
**Transition:** {scene['transition']}

"""
        return md

    def get_stats(self) -> Dict[str, Any]:
        return {"total_subscene_types": len(self._subscenes)}
