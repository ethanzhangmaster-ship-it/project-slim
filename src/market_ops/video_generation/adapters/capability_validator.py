"""Capability Validator"""
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class CapabilityViolation:
    code: str
    message: str
    field: str
    severity: str = "error"


class CapabilityValidator:
    def __init__(self, capabilities: Dict[str, Any]):
        self.capabilities = capabilities

    def validate(self, prompt: Dict[str, Any]) -> Dict[str, Any]:
        violations = []
        warnings = []

        max_duration = self.capabilities.get("duration", 0)
        if max_duration > 0 and "duration" in prompt:
            duration = prompt["duration"]
            if isinstance(duration, (int, float)) and duration > max_duration:
                violations.append(CapabilityViolation(
                    code="duration_exceeded",
                    message=f"Duration {duration}s exceeds platform max {max_duration}s",
                    field="duration"
                ))

        max_token_length = self.capabilities.get("max_token_length", 0)
        if max_token_length > 0:
            total_length = sum(len(str(v)) for v in prompt.values() if isinstance(v, str))
            if total_length > max_token_length:
                violations.append(CapabilityViolation(
                    code="max_length_exceeded",
                    message=f"Total prompt length {total_length} exceeds max {max_token_length}",
                    field="total"
                ))

        unsupported_fields = self.capabilities.get("unsupported_fields", [])
        for field_name in unsupported_fields:
            if field_name in prompt and prompt[field_name]:
                warnings.append(CapabilityViolation(
                    code="unsupported_field",
                    message=f"Field '{field_name}' is not supported by this platform",
                    field=field_name,
                    severity="warning"
                ))

        supported_aspect_ratios = self.capabilities.get("aspect_ratios", [])
        if supported_aspect_ratios and "aspect_ratio" in prompt:
            if prompt["aspect_ratio"] not in supported_aspect_ratios:
                violations.append(CapabilityViolation(
                    code="unsupported_aspect_ratio",
                    message=f"Aspect ratio '{prompt['aspect_ratio']}' not supported. Supported: {supported_aspect_ratios}",
                    field="aspect_ratio"
                ))

        return {
            "passed": len(violations) == 0,
            "violations": [v.__dict__ for v in violations],
            "warnings": [w.__dict__ for w in warnings]
        }
