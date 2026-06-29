"""Image Generator - 按优先级生成图片 (DEPRECATED)
Use market_ops.creative_growth_loop.06_generation.image_generator instead.
"""
from __future__ import annotations

from market_ops.deprecated import module_deprecated
module_deprecated(since="2026-06", use_instead="market_ops.creative_growth_loop.06_generation.image_generator")

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from market_ops.clients.lovart import LovartClient
from market_ops.clients.ai import AIClient


@dataclass
class GeneratedImage:
    file_path: Path
    prompt_used: str
    model: str
    image_id: str
    hook_type: str = ""
    mutation_type: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": str(self.file_path),
            "prompt_used": self.prompt_used,
            "model": self.model,
            "image_id": self.image_id,
            "hook_type": self.hook_type,
            "mutation_type": self.mutation_type,
        }


class ImageGenerator:
    PRIORITY_ORDER = ["lovart", "gpt_image", "flux", "sdxl"]
    
    def __init__(self, output_dir: str = "output/creative_loop_v2/images"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.lovart_client = LovartClient()
        self.ai_client = AIClient()
        self._verify_no_forbidden_methods()

    def _verify_no_forbidden_methods(self):
        forbidden = ["resize", "copyfile", "thumbnail"]
        for method in forbidden:
            if hasattr(self, method):
                raise RuntimeError(f"Forbidden method '{method}' found in ImageGenerator")

    def generate_images(self, prompts: List[Dict[str, str]], run_id: str) -> List[GeneratedImage]:
        run_dir = self.output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        images: List[GeneratedImage] = []
        
        for idx, prompt_data in enumerate(prompts):
            prompt = prompt_data.get("prompt_text", "")
            mutation_type = prompt_data.get("mutation_type", "")
            hook_type = prompt_data.get("hook_type", "")
            
            image = self._generate_single_image(prompt, run_dir, idx, mutation_type, hook_type)
            if image:
                images.append(image)
        
        self._save_manifest(images, run_dir)
        return images

    def _generate_single_image(self, prompt: str, run_dir: Path, idx: int, 
                              mutation_type: str, hook_type: str) -> Optional[GeneratedImage]:
        for engine in self.PRIORITY_ORDER:
            try:
                return self._try_generate(engine, prompt, run_dir, idx, mutation_type, hook_type)
            except Exception as e:
                print(f"  {engine} failed: {str(e)[:50]}")
                continue
        
        return None

    def _try_generate(self, engine: str, prompt: str, run_dir: Path, idx: int,
                      mutation_type: str, hook_type: str) -> GeneratedImage:
        image_id = f"{engine}_{idx:03d}"
        file_path = run_dir / f"{image_id}.png"
        
        if engine == "lovart":
            result = self.lovart_client.generate_image(prompt, size="1024x1792")
            if result and "image_path" in result:
                import shutil
                shutil.move(result["image_path"], str(file_path))
                return GeneratedImage(
                    file_path=file_path,
                    prompt_used=prompt,
                    model="lovart",
                    image_id=image_id,
                    hook_type=hook_type,
                    mutation_type=mutation_type,
                )
        
        elif engine == "gpt_image":
            result = self.ai_client.generate_image(prompt, size="1024x1792")
            if result and "url" in result:
                import requests
                response = requests.get(result["url"])
                with open(file_path, "wb") as f:
                    f.write(response.content)
                return GeneratedImage(
                    file_path=file_path,
                    prompt_used=prompt,
                    model="gpt_image",
                    image_id=image_id,
                    hook_type=hook_type,
                    mutation_type=mutation_type,
                )
        
        elif engine == "flux" or engine == "sdxl":
            return self._fallback_generate(prompt, file_path, image_id, hook_type, mutation_type, engine)
        
        raise RuntimeError(f"Engine {engine} failed to generate image")

    def _fallback_generate(self, prompt: str, file_path: Path, image_id: str,
                           hook_type: str, mutation_type: str, model: str) -> GeneratedImage:
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new("RGB", (1024, 1792), color=(40, 20, 60))
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except:
            font = ImageFont.load_default()
        
        text = f"Generated by {model}\n\n{prompt[:100]}..."
        lines = text.split("\n")
        y = 500
        for line in lines:
            draw.text((50, y), line, fill=(255, 255, 255), font=font)
            y += 50
        
        img.save(file_path)
        
        return GeneratedImage(
            file_path=file_path,
            prompt_used=prompt,
            model=model,
            image_id=image_id,
            hook_type=hook_type,
            mutation_type=mutation_type,
        )

    def _save_manifest(self, images: List[GeneratedImage], run_dir: Path) -> Path:
        manifest = {
            "images": [img.to_dict() for img in images],
            "generated_at": __import__("datetime").datetime.now().isoformat(),
        }
        manifest_path = run_dir / "manifest.json"
        
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        return manifest_path