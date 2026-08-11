"""Base Adapter Interface"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from ..models.adapter_result import AdapterResult as ResultSchema
from .prompt_mapper import prompt_mapper
from .cost_model import cost_model_manager
from .capability_validator import CapabilityValidator


@dataclass
class PlatformPrompt:
    platform: str = ""
    prompt: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationError:
    code: str = ""
    message: str = ""
    field: str = ""
    severity: str = "error"


class BaseAdapter(ABC):
    platform_name: str = "base"
    platform_capabilities: Dict[str, Any] = {}
    prompt_mapping: Dict[str, str] = {}

    def __init__(self):
        self._load_capabilities()
        self._load_prompt_mapping()
        self.capability_validator = CapabilityValidator(self.platform_capabilities)

    def _load_capabilities(self):
        pass

    def _load_prompt_mapping(self):
        pass

    @abstractmethod
    def compile(self, master_prompt: Dict[str, Any]) -> ResultSchema:
        pass

    def validate(self, prompt: Dict[str, Any]) -> Dict[str, Any]:
        errors = []
        warnings = []

        required_fields = self.platform_capabilities.get("required_fields", [])
        for field_name in required_fields:
            if field_name not in prompt or not prompt[field_name]:
                errors.append(ValidationError(
                    code="missing_field",
                    message=f"Required field '{field_name}' is missing or empty",
                    field=field_name
                ))

        cap_validation = self.capability_validator.validate(prompt)
        if not cap_validation["passed"]:
            errors.extend([ValidationError(**v) for v in cap_validation["violations"]])
        warnings.extend([ValidationError(**w) for w in cap_validation["warnings"]])

        return {
            "passed": len(errors) == 0,
            "errors": [e.__dict__ for e in errors],
            "warnings": [w.__dict__ for w in warnings]
        }

    def estimate_cost(self, prompt: Dict[str, Any]) -> Dict[str, Any]:
        duration = prompt.get("duration", 5)
        resolution = prompt.get("resolution", "1080p")
        return cost_model_manager.get_cost(self.platform_name, duration, resolution)

    def _transform_prompt(self, master_prompt: Dict[str, Any]) -> Dict[str, Any]:
        return prompt_mapper.transform(master_prompt, self.platform_name)

    def _build_result(self, prompt: Dict[str, Any], validation: Dict[str, Any], cost: Dict[str, Any]) -> ResultSchema:
        status = "success" if validation.get("passed", False) else "failed"
        return ResultSchema(
            platform=self.platform_name,
            status=status,
            prompt=prompt,
            validation=validation,
            cost=cost,
            metadata={
                "capabilities": self.platform_capabilities,
                "mapping": self.prompt_mapping
            }
        )
