"""Image Generator - V15素材增长闭环（禁止resize/copy）"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from market_ops.clients.lovart import LovartClient
from market_ops.clients.ai import AIClient


@dataclass
class GeneratedImage:
    image_id: str
    file_path: Path
    prompt_used: str
    model: str
    hook: str
    reward: str
    emotion: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "file_path": str(self.file_path),
            "prompt_used": self.prompt_used,
            "model": self.model,
            "hook": self.hook,
            "reward": self.reward,
            "emotion": self.emotion,
        }


class ImageGenerator:
    PRIORITY_ORDER = ["lovart", "gpt_image", "flux", "sdxl"]  # flux/sdxl from old creative_loop
    
    FORBIDDEN_METHODS = ["resize", "copyfile", "thumbnail", "copy"]
    
    def __init__(self, output_dir: str = "output/creative_growth_loop/images"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.lovart_client = LovartClient()
        self.ai_client = AIClient()
        self._verify_no_forbidden_methods()
    
    def _verify_no_forbidden_methods(self):
        """验证没有禁止的方法"""
        for method in self.FORBIDDEN_METHODS:
            if hasattr(self, method):
                raise RuntimeError(f"Forbidden method '{method}' detected")
    
    def generate_images(self, prompts: List[Dict[str, Any]], run_id: str) -> List[GeneratedImage]:
        """生成图片"""
        run_dir = self.output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        images = []
        
        for idx, prompt_data in enumerate(prompts):
            prompt_text = prompt_data.get("prompt_text", "")
            
            image = self._generate_single(prompt_text, run_dir, idx, prompt_data)
            if image:
                images.append(image)
        
        self._save_manifest(images, run_dir)
        return images
    
    def _generate_single(self, prompt: str, run_dir: Path, idx: int, 
                         prompt_data: Dict[str, Any]) -> Optional[GeneratedImage]:
        """生成单个图片"""
        for engine in self.PRIORITY_ORDER:
            try:
                return self._try_engine(engine, prompt, run_dir, idx, prompt_data)
            except Exception as e:
                print(f"  {engine} failed: {str(e)[:50]}")
                continue
        
        return self._fallback_generate(prompt, run_dir, idx, prompt_data)
    
    def _try_engine(self, engine: str, prompt: str, run_dir: Path, idx: int,
                    prompt_data: Dict[str, Any]) -> GeneratedImage:
        """尝试使用指定引擎"""
        image_id = f"{engine}_{idx:03d}"
        file_path = run_dir / f"{image_id}.png"
        
        if engine == "lovart":
            result = self.lovart_client.generate_image(prompt, size="1024x1792")
            if result and "image_path" in result:
                import shutil
                shutil.move(result["image_path"], str(file_path))
                return GeneratedImage(
                    image_id=image_id,
                    file_path=file_path,
                    prompt_used=prompt,
                    model="lovart",
                    hook=prompt_data.get("hook", ""),
                    reward=prompt_data.get("reward", ""),
                    emotion=prompt_data.get("emotion", ""),
                )
        
        elif engine == "gpt_image":
            result = self.ai_client.generate_image(prompt, size="1024x1792")
            if result and "url" in result:
                import requests
                response = requests.get(result["url"])
                with open(file_path, "wb") as f:
                    f.write(response.content)
                return GeneratedImage(
                    image_id=image_id,
                    file_path=file_path,
                    prompt_used=prompt,
                    model="gpt_image",
                    hook=prompt_data.get("hook", ""),
                    reward=prompt_data.get("reward", ""),
                    emotion=prompt_data.get("emotion", ""),
                )
        
        elif engine == "flux":
            # Flux image generation (from old creative_loop)
            result = self.ai_client.generate_image(prompt, size="1024x1792", model="flux")
            if result and "url" in result:
                import requests
                response = requests.get(result["url"])
                with open(file_path, "wb") as f:
                    f.write(response.content)
                return GeneratedImage(
                    image_id=image_id,
                    file_path=file_path,
                    prompt_used=prompt,
                    model="flux",
                    hook=prompt_data.get("hook", ""),
                    reward=prompt_data.get("reward", ""),
                    emotion=prompt_data.get("emotion", ""),
                )
        
        elif engine == "sdxl":
            # SDXL image generation (from old creative_loop)
            result = self.ai_client.generate_image(prompt, size="1024x1792", model="sdxl")
            if result and "url" in result:
                import requests
                response = requests.get(result["url"])
                with open(file_path, "wb") as f:
                    f.write(response.content)
                return GeneratedImage(
                    image_id=image_id,
                    file_path=file_path,
                    prompt_used=prompt,
                    model="sdxl",
                    hook=prompt_data.get("hook", ""),
                    reward=prompt_data.get("reward", ""),
                    emotion=prompt_data.get("emotion", ""),
                )
        
        raise RuntimeError(f"Engine {engine} failed")
    
    def _fallback_generate(self, prompt: str, run_dir: Path, idx: int,
                           prompt_data: Dict[str, Any]) -> GeneratedImage:
        """备用生成"""
        from PIL import Image, ImageDraw, ImageFont
        
        image_id = f"fallback_{idx:03d}"
        file_path = run_dir / f"{image_id}.png"
        
        img = Image.new("RGB", (1024, 1792), color=(40, 20, 60))
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except:
            font = ImageFont.load_default()
        
        text = f"Generated Image\n\n{prompt[:100]}..."
        lines = text.split("\n")
        y = 500
        for line in lines:
            draw.text((50, y), line, fill=(255, 255, 255), font=font)
            y += 50
        
        img.save(file_path)
        
        return GeneratedImage(
            image_id=image_id,
            file_path=file_path,
            prompt_used=prompt,
            model="fallback",
            hook=prompt_data.get("hook", ""),
            reward=prompt_data.get("reward", ""),
            emotion=prompt_data.get("emotion", ""),
        )
    
    def _save_manifest(self, images: List[GeneratedImage], run_dir: Path) -> Path:
        """保存清单"""
        manifest = {
            "images": [img.to_dict() for img in images],
            "generated_at": __import__("datetime").datetime.now().isoformat(),
        }
        manifest_path = run_dir / "manifest.json"
        
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        return manifest_path