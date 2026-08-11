"""Hailuo Platform Adapter"""
from typing import Dict, Any
from .base_adapter import BaseAdapter
from ..models.adapter_result import AdapterResult
from .capability import capability_manager
from .prompt_mapper import prompt_mapper


class HailuoAdapter(BaseAdapter):
    platform_name = "hailuo"

    def _load_capabilities(self):
        self.platform_capabilities = capability_manager.get_capability("hailuo")

    def _load_prompt_mapping(self):
        self.prompt_mapping = prompt_mapper.get_mapping("hailuo")

    def compile(self, master_prompt: Dict[str, Any]) -> AdapterResult:
        prompt = self._transform_prompt(master_prompt)

        prompt["emotion"] = "excited"

        validation = self.validate(prompt)
        cost = self.estimate_cost(prompt)

        return self._build_result(prompt, validation, cost)
