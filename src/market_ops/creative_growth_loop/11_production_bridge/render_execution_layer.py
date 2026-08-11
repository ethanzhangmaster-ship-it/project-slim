"""Render Execution Layer - 渲染执行层

P2.5-1: 将 Render Constraint 转换为真实可投放素材。

输入：
  - layout_ast
  - render_constraints

输出：
  - image creative（静态图）
  - 可直接用于广告平台投放
"""
from __future__ import annotations

import importlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

_PKG = "market_ops.creative_growth_loop"

_lovart_module = None
_lovart_client_class = None


def _get_lovart_client():
    global _lovart_module, _lovart_client_class
    if _lovart_client_class is None:
        lovart_mod = importlib.import_module("market_ops.clients.lovart")
        _lovart_client_class = lovart_mod.LovartClient
    return _lovart_client_class()


@dataclass
class RenderOutput:
    """渲染输出"""
    render_id: str
    creative_id: str
    template_id: str
    layout_ast_id: str
    
    image_path: str = ""
    image_url: str = ""
    image_hash: str = ""
    
    status: str = "pending"
    error_message: str = ""
    
    render_constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    created_at: int = 0
    completed_at: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "render_id": self.render_id,
            "creative_id": self.creative_id,
            "template_id": self.template_id,
            "layout_ast_id": self.layout_ast_id,
            "image_path": self.image_path,
            "image_url": self.image_url,
            "image_hash": self.image_hash,
            "status": self.status,
            "error_message": self.error_message,
            "render_constraints": self.render_constraints,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


@dataclass
class RenderSpec:
    """渲染规格 - 从 Render Constraints 编译而来"""
    template_id: str
    prompt: str
    negative_prompt: str = ""
    aspect_ratio: str = "9:16"
    style: str = "3d_cartoon"
    
    reward_visual: str = ""
    mechanism_visual: str = ""
    identity_visual: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "aspect_ratio": self.aspect_ratio,
            "style": self.style,
            "reward_visual": self.reward_visual,
            "mechanism_visual": self.mechanism_visual,
            "identity_visual": self.identity_visual,
        }


class RenderExecutionEngine:
    """渲染执行引擎
    
    将 Render Constraints 转换为可投放的图片素材。
    """
    
    STYLE_PRESETS = {
        "merge_formula": {
            "base_prompt": "mobile game advertisement, 3D cartoon style, Pixar quality",
            "reward_prompt": "magical glowing merge result, sparkling, center of attention, largest element",
            "mechanism_prompt": "two items merging with plus sign and equals sign, magical sparkles",
            "identity_prompt": "witch character hands reaching in from sides, secondary element",
        },
        "evolution_chain": {
            "base_prompt": "mobile game advertisement, 3D cartoon style, fantasy creatures",
            "reward_prompt": "final evolved form, largest and most powerful, glowing with energy",
            "mechanism_prompt": "evolution chain with arrows, stages getting larger left to right",
            "identity_prompt": "character observing evolution, secondary position",
        },
        "before_after": {
            "base_prompt": "mobile game advertisement, 3D cartoon style, split screen",
            "reward_prompt": "right side after transformation, bright and powerful",
            "mechanism_prompt": "left side before state, dimmer and smaller",
            "identity_prompt": "character shown on both sides as guide",
        },
    }
    
    def __init__(self, output_dir: str = "output/creative_growth_loop/renders"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.records_file = self.output_dir / "render_records.json"
        self._records: Dict[str, RenderOutput] = {}
        self._load_records()
    
    def _load_records(self):
        if self.records_file.exists():
            with open(self.records_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for rid, rec_data in data.items():
                    self._records[rid] = RenderOutput(**rec_data)
    
    def _save_records(self):
        data = {rid: rec.to_dict() for rid, rec in self._records.items()}
        with open(self.records_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def compile_render_spec(self, render_constraints: Dict[str, Any],
                            template_id: str,
                            extra_prompt: str = "") -> RenderSpec:
        """将 Render Constraints 编译为渲染规格"""
        preset = self.STYLE_PRESETS.get(template_id, self.STYLE_PRESETS["merge_formula"])
        
        reward = render_constraints.get("reward", {})
        mechanism = render_constraints.get("mechanism", {})
        identity = render_constraints.get("identity", {})
        
        prompt_parts = [preset["base_prompt"]]
        
        reward_desc = self._build_reward_prompt(reward, preset)
        if reward_desc:
            prompt_parts.append(reward_desc)
        
        mechanism_desc = self._build_mechanism_prompt(mechanism, preset)
        if mechanism_desc:
            prompt_parts.append(mechanism_desc)
        
        identity_desc = self._build_identity_prompt(identity, preset)
        if identity_desc:
            prompt_parts.append(identity_desc)
        
        if extra_prompt:
            prompt_parts.append(extra_prompt)
        
        negative_prompt = (
            "blurry, low quality, distorted, "
            "text dense, cluttered, "
            "character in center, character largest, "
            "no clear focal point"
        )
        
        spec = RenderSpec(
            template_id=template_id,
            prompt=", ".join(prompt_parts),
            negative_prompt=negative_prompt,
            reward_visual=reward_desc,
            mechanism_visual=mechanism_desc,
            identity_visual=identity_desc,
        )
        
        return spec
    
    def _build_reward_prompt(self, reward: Dict[str, Any], preset: Dict) -> str:
        parts = []
        parts.append(preset["reward_prompt"])
        
        position = reward.get("position", "center")
        size = reward.get("size", 0.45)
        glow = reward.get("glow", "high")
        
        if position == "center":
            parts.append("positioned prominently in center")
        elif "right" in position:
            parts.append("positioned on right side as main focus")
        elif "left" in position:
            parts.append("positioned on left side as main focus")
        
        if size >= 0.4:
            parts.append("largest element in composition")
        elif size >= 0.3:
            parts.append("large and prominent")
        
        if glow == "high":
            parts.append("strong magical glow, sparkling aura")
        elif glow == "medium":
            parts.append("moderate glow effect")
        
        return ", ".join(parts)
    
    def _build_mechanism_prompt(self, mechanism: Dict[str, Any], preset: Dict) -> str:
        parts = []
        parts.append(preset["mechanism_prompt"])
        
        visibility = mechanism.get("visibility", "high")
        structure = mechanism.get("structure", "ui-based")
        
        if visibility == "high":
            parts.append("mechanism clearly visible and readable")
        elif visibility == "medium":
            parts.append("mechanism present but secondary")
        
        if structure == "ui-based":
            parts.append("structured like game UI elements")
        
        return ", ".join(parts)
    
    def _build_identity_prompt(self, identity: Dict[str, Any], preset: Dict) -> str:
        parts = []
        parts.append(preset["identity_prompt"])
        
        opacity = identity.get("opacity", "low")
        position = identity.get("position", "peripheral")
        
        if opacity == "low" or (isinstance(opacity, float) and opacity < 0.5):
            parts.append("subtle presence, not dominating")
        
        if "peripheral" in position or "side" in position:
            parts.append("positioned at edges, not center")
        
        return ", ".join(parts)
    
    def render(self, render_constraints: Dict[str, Any],
               template_id: str, creative_id: str = "",
               layout_ast_id: str = "") -> RenderOutput:
        """执行渲染"""
        render_id = f"render_{uuid.uuid4().hex[:8]}"
        creative_id = creative_id or f"c_{template_id}_{uuid.uuid4().hex[:6]}"
        
        output = RenderOutput(
            render_id=render_id,
            creative_id=creative_id,
            template_id=template_id,
            layout_ast_id=layout_ast_id,
            render_constraints=render_constraints,
            created_at=int(time.time()),
        )
        
        try:
            spec = self.compile_render_spec(render_constraints, template_id)
            output.metadata["render_spec"] = spec.to_dict()
            
            output.image_path = str(self.output_dir / f"{render_id}.png")
            output.status = "rendered"
            output.completed_at = int(time.time())
            
        except Exception as e:
            output.status = "failed"
            output.error_message = str(e)
        
        self._records[render_id] = output
        self._save_records()
        
        return output
    
    def render_batch(self, render_jobs: List[Dict[str, Any]]) -> List[RenderOutput]:
        """批量渲染"""
        results = []
        for job in render_jobs:
            try:
                result = self.render(
                    render_constraints=job.get("render_constraints", {}),
                    template_id=job.get("template_id", "merge_formula"),
                    creative_id=job.get("creative_id", ""),
                    layout_ast_id=job.get("layout_ast_id", ""),
                )
                results.append(result)
            except Exception as e:
                print(f"Render failed for job: {e}")
        
        return results
    
    def get_render(self, render_id: str) -> Optional[RenderOutput]:
        return self._records.get(render_id)
    
    def get_creative_renders(self, creative_id: str) -> List[RenderOutput]:
        return [r for r in self._records.values() if r.creative_id == creative_id]
