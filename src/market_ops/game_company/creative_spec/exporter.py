import os
import json
from typing import Dict, Any
from datetime import datetime


class CreativeExporter:
    def __init__(self, output_dir: str = None):
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "output", "creative_spec")
        self._output_dir = output_dir

    def ensure_dir(self):
        os.makedirs(self._output_dir, exist_ok=True)

    def export_production_spec_json(self, data: Dict[str, Any], filename: str = None) -> str:
        self.ensure_dir()
        if filename is None:
            filename = f"production_spec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self._output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return filepath

    def export_storyboard_json(self, data: Dict[str, Any], filename: str = None) -> str:
        self.ensure_dir()
        if filename is None:
            filename = f"storyboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self._output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return filepath

    def export_prompt_json(self, data: Dict[str, Any], filename: str = None) -> str:
        self.ensure_dir()
        if filename is None:
            filename = f"prompt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self._output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return filepath

    def export_creative_brief_md(self, data: Dict[str, Any], filename: str = None) -> str:
        self.ensure_dir()
        if filename is None:
            filename = f"creative_brief_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(self._output_dir, filename)

        project = data.get("project", "P04 Witch")
        hook = data.get("hook_type", "collection")
        score = data.get("score", {})

        md = f"""# {project} - Creative Brief

## Overview
- **Project:** {project}
- **Hook Type:** {hook}
- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Spec Summary
- **Overall Score:** {score.get('overall_score', 'N/A')}
- **Grade:** {score.get('grade', 'N/A')}
- **Expected ROAS:** {score.get('predictions', {}).get('expected_roas', 'N/A')}
- **Expected CTR:** {score.get('predictions', {}).get('expected_ctr', 'N/A')}

## Key Requirements
1. Subject in center 40% of frame within 0.8 seconds
2. First frame contrast >= 0.15
3. First frame saturation >= 0.45
4. No text overlay in first 3 seconds
5. Visual structure change between 0.8-3.0s
6. Visual reward event after 6 seconds
7. CTA present in last 3 seconds
8. 9:16 vertical aspect ratio
9. Warm palette with high color diversity (entropy > 7.8)

## Visual Direction
- **Style:** 3D cartoon, warm golden yellows + soft purples + pastel blues
- **Character:** Cute witch, adorable, whimsical
- **Mood:** Enchanting, magical, satisfying collection appeal

## Storyboard
"""
        scenes = data.get("storyboard", {}).get("scenes", [])
        for i, scene in enumerate(scenes):
            md += f"""
### Scene {i+1}: {scene.get('time_range', '')} [{scene.get('category', '')}]
- **Prompt:** {scene.get('prompt', '')}
- **Camera:** {scene.get('camera', '')}
- **Duration:** {scene.get('duration_seconds', 0)}s
"""

        md += """
## CTA Requirements
- Ornate golden banner at bottom (preferred)
- Pulse animation on button
- Social proof near CTA
- High contrast color for button

## Anti-Patterns to Avoid
- Do NOT start with empty background
- Do NOT use text-only first frame
- Do NOT use low contrast/flat lighting
- Do NOT use cold/icy palette
- Do NOT put text overlay in first 3 seconds
- Do NOT show UI labels/menus in hook phase
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)
        return filepath

    def export_creative_checklist_md(self, data: Dict[str, Any], filename: str = None) -> str:
        self.ensure_dir()
        if filename is None:
            filename = f"creative_checklist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(self._output_dir, filename)

        md = f"""# Creative Production Checklist
**Project:** {data.get('project', 'P04 Witch')}
**Date:** {datetime.now().strftime('%Y-%m-%d')}

## Pre-Production
- [ ] Hook type selected: {data.get('hook_type', 'collection')}
- [ ] Hero/character selected: {data.get('hero', 'witch')}
- [ ] Aspect ratio: 9:16
- [ ] Duration: 15-45 seconds (recommended 25s)
- [ ] Warm palette confirmed

## Production
- [ ] Subject centered in first frame (center 40%)
- [ ] First frame contrast >= 0.15
- [ ] First frame saturation >= 0.45
- [ ] No text overlay in first 3 seconds
- [ ] Visual structure change between 0.8-3.0s
- [ ] Core gameplay shown at 3-6s
- [ ] Visual reward event after 6s (brighter + more saturated)
- [ ] CTA in last 3 seconds

## Post-Production
- [ ] QA Check passed
- [ ] Score Engine score >= 70
- [ ] Aspect ratio verified 720x1280 (9:16)
- [ ] Text density < 0.015
- [ ] No anti-pattern violations

## AI Video Generation Checklist
- [ ] System prompt includes all spec rules
- [ ] User prompt describes all 5 scenes
- [ ] Negative prompt excludes anti-patterns
- [ ] Platform-specific format confirmed
- [ ] Total duration matches spec
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)
        return filepath

    def get_stats(self) -> Dict[str, Any]:
        return {"output_dir": self._output_dir, "supported_formats": ["JSON", "Markdown"]}
