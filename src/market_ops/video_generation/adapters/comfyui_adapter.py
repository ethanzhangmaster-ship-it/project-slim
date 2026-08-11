"""ComfyUI Platform Adapter"""
from typing import Dict, Any
from .base_adapter import BaseAdapter
from ..models.adapter_result import AdapterResult
from .capability import capability_manager
from .prompt_mapper import prompt_mapper


class ComfyUIAdapter(BaseAdapter):
    platform_name = "comfyui"

    def _load_capabilities(self):
        self.platform_capabilities = capability_manager.get_capability("comfyui")

    def _load_prompt_mapping(self):
        self.prompt_mapping = prompt_mapper.get_mapping("comfyui")

    def compile(self, master_prompt: Dict[str, Any]) -> AdapterResult:
        prompt = self._transform_prompt(master_prompt)

        prompt.setdefault("checkpoint_name", "realisticVisionV51_v51VAE.safetensors")
        prompt.setdefault("sampler_name", "DPM++ 2M SDE Karras")
        prompt.setdefault("cfg", 7.0)
        prompt.setdefault("steps", 20)
        prompt.setdefault("control_net", "canny")

        validation = self.validate(prompt)
        cost = self.estimate_cost(prompt)

        return self._build_result(prompt, validation, cost)

    def compile_workflow(self, master_prompt: Dict[str, Any]) -> Dict[str, Any]:
        positive = master_prompt.get("image_prompt", "")
        negative = master_prompt.get("negative_prompt", "")
        seed = master_prompt.get("seed", -1)

        workflow = {
            "version": 1,
            "nodes": [
                {
                    "id": "checkpoint_loader",
                    "type": "CheckpointLoaderSimple",
                    "inputs": {
                        "ckpt_name": "realisticVisionV51_v51VAE.safetensors"
                    }
                },
                {
                    "id": "positive_prompt",
                    "type": "CLIPTextEncode",
                    "inputs": {
                        "text": positive,
                        "clip": ["checkpoint_loader", 1]
                    }
                },
                {
                    "id": "negative_prompt",
                    "type": "CLIPTextEncode",
                    "inputs": {
                        "text": negative,
                        "clip": ["checkpoint_loader", 1]
                    }
                },
                {
                    "id": "sampler",
                    "type": "KSampler",
                    "inputs": {
                        "seed": seed,
                        "steps": 20,
                        "cfg": 7.0,
                        "sampler_name": "DPM++ 2M SDE Karras",
                        "model": ["checkpoint_loader", 0],
                        "positive": ["positive_prompt", 0],
                        "negative": ["negative_prompt", 0]
                    }
                },
                {
                    "id": "image_saver",
                    "type": "SaveImage",
                    "inputs": {
                        "images": ["sampler", 0]
                    }
                }
            ],
            "connections": [
                ["checkpoint_loader", 1, "positive_prompt", 1],
                ["checkpoint_loader", 1, "negative_prompt", 1],
                ["checkpoint_loader", 0, "sampler", 3],
                ["positive_prompt", 0, "sampler", 4],
                ["negative_prompt", 0, "sampler", 5],
                ["sampler", 0, "image_saver", 0]
            ]
        }

        return workflow
