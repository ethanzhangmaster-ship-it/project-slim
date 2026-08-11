"""E13.7.2 Response Parser — 结构化输出解析器.

将 LLM 的原始文本输出解析为结构化数据:
  - JSON 解析
  - 字段验证
  - 类型转换
  - 错误恢复

设计原则:
  - 强制 JSON 输出解析
  - 支持 invalid response 容错
  - 验证置信度范围
  - 提取可执行动作

用法:
    parser = ResponseParser()
    parsed = parser.parse(llm_response.content)
    insights = parsed.to_insights()
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Parsed Response
# ═══════════════════════════════════════════════════════════════


@dataclass
class ParsedResponse:
    """解析后的 LLM 响应.

    Attributes:
        insight_type: 洞察类型
        diagnosis: 诊断
        hypothesis: 假设
        confidence: 置信度 [0, 1]
        recommended_actions: 推荐行动
        evidence: 证据
        alternative_hypotheses: 替代假设
        learning_notes: 学习笔记
        parse_success: 解析是否成功
        parse_errors: 解析错误
        raw_content: 原始内容
        metadata: 扩展元数据
    """
    insight_type: str = "NORMAL"
    diagnosis: str = ""
    hypothesis: str = ""
    confidence: float = 0.5
    recommended_actions: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    alternative_hypotheses: list[str] = field(default_factory=list)
    learning_notes: str = ""
    parse_success: bool = True
    parse_errors: list[str] = field(default_factory=list)
    raw_content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight_type": self.insight_type,
            "diagnosis": self.diagnosis,
            "hypothesis": self.hypothesis,
            "confidence": self.confidence,
            "recommended_actions": self.recommended_actions,
            "evidence": self.evidence,
            "alternative_hypotheses": self.alternative_hypotheses,
            "learning_notes": self.learning_notes,
            "parse_success": self.parse_success,
            "parse_errors": self.parse_errors,
        }


# ═══════════════════════════════════════════════════════════════
# Response Parser
# ═══════════════════════════════════════════════════════════════


class ResponseParser:
    """响应解析器 — 将 LLM 输出解析为结构化数据.

    处理:
      - 标准 JSON 解析
      - JSON 在 markdown 代码块中
      - 部分 JSON 提取
      - 字段类型验证和修正
    """

    # 有效 insight_type 值
    VALID_INSIGHT_TYPES = {
        "CREATIVE_FATIGUE",
        "ROAS_DECLINE",
        "ROAS_OPPORTUNITY",
        "ANOMALY",
        "PATTERN",
        "NORMAL",
    }

    def __init__(self, strict: bool = False):
        """初始化解析器.

        Args:
            strict: 严格模式 (True 则解析失败时抛异常)
        """
        self._strict = strict
        self._parse_count: int = 0

    @property
    def parse_count(self) -> int:
        return self._parse_count

    def parse(self, content: str) -> ParsedResponse:
        """解析 LLM 响应.

        Args:
            content: LLM 原始输出

        Returns:
            ParsedResponse: 解析后的结构化响应
        """
        self._parse_count += 1
        errors = []

        if not content or not content.strip():
            return ParsedResponse(
                parse_success=False,
                parse_errors=["Empty content"],
                raw_content=content,
            )

        # 尝试提取 JSON
        json_data = self._extract_json(content)
        if json_data is None:
            errors.append("Failed to extract JSON from content")
            if self._strict:
                return ParsedResponse(
                    parse_success=False,
                    parse_errors=errors,
                    raw_content=content,
                )
            # 非严格模式: 尝试用文本解析
            return self._parse_text_fallback(content, errors)

        # 验证并规范化字段
        return self._normalize(json_data, content, errors)

    def _extract_json(self, content: str) -> dict[str, Any] | None:
        """从内容中提取 JSON.

        尝试顺序:
          1. 直接 JSON 解析
          2. 从 markdown ```json 代码块中提取
          3. 从 markdown ``` 代码块中提取
          4. 正则提取 JSON 对象
        """
        # 1. 直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 2. markdown json 代码块
        match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 3. markdown 代码块
        match = re.search(r'```\s*\n(.*?)\n```', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 4. 正则提取 { ... }
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def _normalize(
        self,
        data: dict[str, Any],
        raw_content: str,
        errors: list[str],
    ) -> ParsedResponse:
        """规范化字段."""
        # insight_type
        insight_type = str(data.get("insight_type", "NORMAL")).upper()
        if insight_type not in self.VALID_INSIGHT_TYPES:
            insight_type = "NORMAL"

        # diagnosis
        diagnosis = str(data.get("diagnosis", ""))

        # hypothesis
        hypothesis = str(data.get("hypothesis", ""))

        # confidence
        confidence = self._parse_confidence(data.get("confidence", 0.5))

        # recommended_actions
        actions = data.get("recommended_actions", [])
        if not isinstance(actions, list):
            actions = []
        actions = [self._normalize_action(a) for a in actions if isinstance(a, dict)]

        # evidence
        evidence = data.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []
        evidence = [str(e) for e in evidence]

        # alternative_hypotheses
        alternatives = data.get("alternative_hypotheses", [])
        if not isinstance(alternatives, list):
            alternatives = []
        alternatives = [str(a) for a in alternatives]

        # learning_notes
        learning_notes = str(data.get("learning_notes", ""))

        return ParsedResponse(
            insight_type=insight_type,
            diagnosis=diagnosis,
            hypothesis=hypothesis,
            confidence=confidence,
            recommended_actions=actions,
            evidence=evidence,
            alternative_hypotheses=alternatives,
            learning_notes=learning_notes,
            parse_success=True,
            parse_errors=errors,
            raw_content=raw_content,
        )

    def _parse_confidence(self, value: Any) -> float:
        """解析置信度."""
        try:
            v = float(value)
            return max(0.0, min(1.0, v))
        except (ValueError, TypeError):
            return 0.5

    def _normalize_action(self, action: dict[str, Any]) -> dict[str, Any]:
        """规范化行动."""
        return {
            "action_type": str(action.get("action_type", "UNKNOWN")),
            "parameters": action.get("parameters", {}) if isinstance(action.get("parameters"), dict) else {},
            "reasoning": str(action.get("reasoning", "")),
            "expected_impact": str(action.get("expected_impact", "")),
            "risk": str(action.get("risk", "low")).lower(),
        }

    def _parse_text_fallback(
        self,
        content: str,
        errors: list[str],
    ) -> ParsedResponse:
        """文本降级解析 — JSON 解析失败时从文本中提取关键信息."""
        errors.append("Using text fallback parsing")

        # 尝试从文本中提取关键字段
        insight_type = "NORMAL"
        if "fatigue" in content.lower() or "疲劳" in content.lower():
            insight_type = "CREATIVE_FATIGUE"
        elif "roas" in content.lower() and ("decline" in content.lower() or "下降" in content.lower()):
            insight_type = "ROAS_DECLINE"
        elif "roas" in content.lower() and ("increase" in content.lower() or "上升" in content.lower()):
            insight_type = "ROAS_OPPORTUNITY"

        return ParsedResponse(
            insight_type=insight_type,
            diagnosis=content[:500],
            hypothesis="",
            confidence=0.3,
            parse_success=False,
            parse_errors=errors,
            raw_content=content,
        )

    def reset(self) -> None:
        self._parse_count = 0