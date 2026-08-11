"""Prompt Validator - 提示词验证器"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

MAX_TOKENS_DEFAULT = 8000


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    truncated: bool = False
    final_token_count: int = 0


class PromptValidator:
    """提示词验证器"""

    def __init__(self, platform_capability: Dict[str, Any]):
        self.capability = platform_capability
        self.max_tokens = platform_capability.get("max_tokens", MAX_TOKENS_DEFAULT)
        self.supported_features = {k: v for k, v in platform_capability.items() if isinstance(v, bool)}

    def validate(self, prompt: str, shot_id: str = "") -> ValidationResult:
        """验证提示词"""
        result = ValidationResult()

        token_count = self._count_tokens(prompt)
        result.final_token_count = token_count

        if token_count > self.max_tokens:
            result.passed = False
            result.errors.append(f"Token count {token_count} exceeds max {self.max_tokens}")
            result.truncated = True

        result.warnings.extend(self._check_feature_support(prompt))

        if result.errors:
            result.passed = False

        return result

    def truncate(self, prompt: str) -> str:
        """截断提示词到最大 Token 数"""
        tokens = prompt.split(", ")
        total = 0
        result = []
        for token in tokens:
            token_len = len(token.split())
            if total + token_len <= self.max_tokens:
                result.append(token)
                total += token_len
            else:
                break
        return ", ".join(result)

    def _count_tokens(self, text: str) -> int:
        """计算 Token 数量（简化版）"""
        return len(text.split())

    def _check_feature_support(self, prompt: str) -> List[str]:
        """检查功能支持"""
        warnings = []

        if not self.supported_features.get("subtitle", True):
            if any(kw in prompt.lower() for kw in ["subtitle", "text", "caption"]):
                warnings.append("Platform does not support subtitle - will be removed")

        if not self.supported_features.get("music", True):
            if any(kw in prompt.lower() for kw in ["music", "sound", "audio"]):
                warnings.append("Platform does not support music - will be removed")

        return warnings


class CapabilityManager:
    """平台能力管理器"""

    def __init__(self, capability_file: str = None):
        self.capabilities: Dict[str, Dict[str, Any]] = {}
        if capability_file and Path(capability_file).exists():
            with open(capability_file, "r", encoding="utf-8") as f:
                self.capabilities = json.load(f)

    def get_capability(self, platform: str) -> Dict[str, Any]:
        """获取平台能力"""
        return self.capabilities.get(platform, {})

    def filter_prompt(self, prompt: str, platform: str) -> str:
        """根据平台能力过滤提示词"""
        cap = self.get_capability(platform)
        if not cap:
            return prompt

        filtered = prompt

        if not cap.get("subtitle", True):
            for kw in ["subtitle", "text overlay", "caption"]:
                filtered = filtered.replace(kw, "")

        if not cap.get("music", True):
            for kw in ["music", "soundtrack", "audio"]:
                filtered = filtered.replace(kw, "")

        return filtered.strip()

    def supports(self, platform: str, feature: str) -> bool:
        """检查平台是否支持指定功能"""
        return self.get_capability(platform).get(feature, False)