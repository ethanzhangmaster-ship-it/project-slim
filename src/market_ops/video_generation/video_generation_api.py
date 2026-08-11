"""Video Generation API"""
import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field

from .compiler.prompt_compiler import PromptCompiler
from .adapters.registry import registry
from .adapters.comfyui_adapter import ComfyUIAdapter
from .models.adapter_result import AdapterResult


@dataclass
class GenerationPackage:
    platform: str = ""
    prompt_files: list = field(default_factory=list)
    validation_file: str = ""
    cost_file: str = ""
    workflow_file: str = ""
    success: bool = False


def generate(blueprint_dir: str, platform: str = "veo") -> GenerationPackage:
    blueprint_path = Path(blueprint_dir)
    if not blueprint_path.exists():
        raise ValueError(f"Blueprint directory not found: {blueprint_dir}")

    compiler = PromptCompiler(blueprint_path)
    master_prompt = compiler.compile()

    master_prompt_dict = json.loads(master_prompt.to_json())

    adapter = registry.create(platform)

    platform_output_dir = Path("output") / "platform" / platform
    platform_output_dir.mkdir(parents=True, exist_ok=True)

    prompt_files = []

    for scene in master_prompt_dict.get("scenes", []):
        scene_id = scene.get("scene_id", "")
        result = adapter.compile(scene)

        scene_dir = platform_output_dir / scene_id
        scene_dir.mkdir(exist_ok=True)

        prompt_json_path = scene_dir / "prompt.json"
        with open(prompt_json_path, "w", encoding="utf-8") as f:
            json.dump(result.prompt, f, indent=2, ensure_ascii=False)
        prompt_files.append(str(prompt_json_path))

        prompt_md_path = scene_dir / "prompt.md"
        with open(prompt_md_path, "w", encoding="utf-8") as f:
            f.write(f"# {platform.capitalize()} Prompt - {scene_id}\n\n")
            for key, value in result.prompt.items():
                if value:
                    f.write(f"## {key}\n\n{value}\n\n")
        prompt_files.append(str(prompt_md_path))

        prompt_txt_path = scene_dir / "prompt.txt"
        with open(prompt_txt_path, "w", encoding="utf-8") as f:
            for key, value in result.prompt.items():
                if value:
                    f.write(f"{key}: {value}\n")
        prompt_files.append(str(prompt_txt_path))

        validation_path = scene_dir / "validation.json"
        with open(validation_path, "w", encoding="utf-8") as f:
            json.dump(result.validation, f, indent=2, ensure_ascii=False)

        cost_path = scene_dir / "cost.json"
        with open(cost_path, "w", encoding="utf-8") as f:
            json.dump(result.cost, f, indent=2, ensure_ascii=False)

    workflow_file = ""
    if platform == "comfyui":
        comfyui_adapter = ComfyUIAdapter()
        scenes = master_prompt_dict.get("scenes", [])
        first_scene = scenes[0] if scenes else {}
        workflow = comfyui_adapter.compile_workflow(first_scene)
        workflow_path = platform_output_dir / "workflow.json"
        with open(workflow_path, "w", encoding="utf-8") as f:
            json.dump(workflow, f, indent=2, ensure_ascii=False)
        workflow_file = str(workflow_path)

    return GenerationPackage(
        platform=platform,
        prompt_files=prompt_files,
        validation_file=str(platform_output_dir / "validation.json"),
        cost_file=str(platform_output_dir / "cost.json"),
        workflow_file=workflow_file,
        success=True
    )


def generate_all(blueprint_dir: str) -> Dict[str, GenerationPackage]:
    results = {}
    for platform in registry.list_platforms():
        try:
            results[platform] = generate(blueprint_dir, platform)
        except Exception as e:
            results[platform] = GenerationPackage(
                platform=platform,
                success=False
            )
    return results
