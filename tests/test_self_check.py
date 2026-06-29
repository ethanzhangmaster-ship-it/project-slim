from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market_ops.self_check import (
    SelfCheckIssue,
    SelfCheckResult,
    _check_text_absence,
    _check_text_presence,
    _check_text_encoding,
    _check_stale_action_logic,
    _check_boss_summary_length,
    _check_market_summary_quality,
    _extract_project_block,
    _extract_project_metrics,
    _check_payback_math,
    _compare_metric,
    _check_company_labels,
    _normalize_segment_for_check,
)


class TestSelfCheckIssue:
    def test_create(self):
        issue = SelfCheckIssue(
            code="test_code",
            source="test_source",
            message="test message",
            actual="a",
            expected="b",
        )
        assert issue.code == "test_code"
        assert issue.actual == "a"


class TestSelfCheckResult:
    def test_create(self):
        from dataclasses import field
        result = SelfCheckResult(
            passed=True,
            issues=[],
            warnings=[],
            preview_paths=None,
            markdown_path=Path("test.md"),
            json_path=Path("test.json"),
        )
        assert result.passed is True


class TestCheckTextAbsence:
    def test_forbidden_found(self):
        issues = []
        _check_text_absence("test", "contains Meta text", "Meta", issues, "Facebook")
        assert len(issues) == 1
        assert issues[0].code == "forbidden_text"

    def test_forbidden_not_found(self):
        issues = []
        _check_text_absence("test", "clean text", "Meta", issues, "Facebook")
        assert len(issues) == 0


class TestCheckTextPresence:
    def test_required_found(self):
        issues = []
        _check_text_presence("test", "contains 素材 info", "素材", issues, "素材字段")
        assert len(issues) == 0

    def test_required_missing(self):
        issues = []
        _check_text_presence("test", "no such word", "素材", issues, "素材字段")
        assert len(issues) == 1
        assert issues[0].code == "missing_required_text"


class TestCheckTextEncoding:
    def test_mojibake_detected(self):
        issues = []
        text = "锛銆鏈闆鍥浼璇" + "x" * 100  # mojibake markers
        _check_text_encoding("test", text, issues)
        assert len(issues) == 1
        assert issues[0].code == "encoding_mojibake"

    def test_clean_text(self):
        issues = []
        _check_text_encoding("test", "干净的文本内容 clean text", issues)
        assert len(issues) == 0


class TestCheckStaleActionLogic:
    def test_stale_found(self):
        issues = []
        _check_stale_action_logic("test", "暂停 P02 Mermaid 相关操作", issues)
        assert len(issues) >= 1
        # Check at least one issue is stale_action_logic or paid_scope_wrong_owner
        codes = {i.code for i in issues}
        assert "stale_action_logic" in codes or "paid_scope_wrong_owner" in codes or "bare_roi_label" in codes

    def test_clean_text(self):
        issues = []
        _check_stale_action_logic("test", "当前应继续观察 ROI 趋势", issues)
        assert len(issues) == 0


class TestExtractProjectBlock:
    def test_extracts_block(self):
        md = "**P04 Witch**\n- 花费 5000\n- ROI 1.20\n\n---\n\n**P02 Mermaid**\n- 花费 3000"
        block = _extract_project_block(md, "P04 Witch", ["P04 Witch", "P02 Mermaid"])
        assert "P04 Witch" in block
        assert "P02" not in block

    def test_no_match(self):
        md = "- **P02 Mermaid**"
        block = _extract_project_block(md, "P04 Witch", ["P04 Witch", "P02 Mermaid"])
        assert block == ""


class TestExtractProjectMetrics:
    def test_extracts_spend(self):
        block = "**P04 Witch**\n- 花费 `5000`\n- 预测D180 `1.20`\n- 距离回本还差约 1000\n- 利润空间约 2000"
        metrics = _extract_project_metrics(block)
        assert metrics["spend"] == "5000"
        assert metrics["forecast"] == "1.20"
        assert metrics["gap"] == "1000"
        assert metrics["profit"] == "2000"

    def test_partial(self):
        block = "**P04 Witch**\n- 花费 `3000`"
        metrics = _extract_project_metrics(block)
        assert metrics["spend"] == "3000"
        assert "forecast" not in metrics


class TestCheckPaybackMath:
    def test_correct_math(self):
        issues = []
        metrics = {"spend": "5000", "forecast": "1.20", "gap": "0", "profit": "1000"}
        _check_payback_math("P04", "test", metrics, issues)
        # spend=5000, forecast=1.20, gap expected = 5000*(1-1.2)=0, profit expected=5000*(1.2-1)=1000
        # These should match
        assert len(issues) == 0

    def test_wrong_gap(self):
        issues = []
        metrics = {"spend": "5000", "forecast": "0.60", "gap": "500", "profit": "0"}
        _check_payback_math("P04", "test", metrics, issues)
        # expected gap = 5000*(1-0.6) = 2000, but gap is 500
        gap_issues = [i for i in issues if i.code == "payback_gap_math"]
        assert len(gap_issues) == 1

    def test_wrong_profit(self):
        issues = []
        metrics = {"spend": "5000", "forecast": "1.50", "gap": "0", "profit": "500"}
        _check_payback_math("P04", "test", metrics, issues)
        # expected profit = 5000*(1.5-1) = 2500, but profit is 500
        profit_issues = [i for i in issues if i.code == "payback_profit_math"]
        assert len(profit_issues) == 1


class TestCompareMetric:
    def test_match(self):
        issues = []
        _compare_metric("P04", "花费", "5000", "5000", "a", "b", issues)
        assert len(issues) == 0

    def test_mismatch(self):
        issues = []
        _compare_metric("P04", "花费", "5000", "6000", "a", "b", issues)
        assert len(issues) == 1
        assert issues[0].code == "cross_source_mismatch"


class TestBossSummaryLength:
    def test_too_long(self):
        issues = []
        text = "第一页：管理层摘要\n- item1\n- item2\n- item3\n- item4\n- item5\n- item6\n---\n第二层：项目分析"
        _check_boss_summary_length("test", text, issues)
        assert len(issues) >= 1

    def test_acceptable(self):
        issues = []
        text = "## 第一层：管理层摘要\n- item1\n- item2\n- item3\n## 第二层：项目分析"
        _check_boss_summary_length("test", text, issues)
        # 3 bullets is fine
        for i in issues:
            if i.code == "boss_summary_too_long":
                pytest.fail("Should not have too_long issue")


class TestMarketSummaryQuality:
    def test_too_long(self):
        issues = []
        text = "**市场负责人摘要**\n- a\n- b\n- c\n- d\n- e\n- f\n- g\n---"
        _check_market_summary_quality("test", text, issues)
        too_long = [i for i in issues if i.code == "market_summary_too_long"]
        assert len(too_long) == 1

    def test_acceptable(self):
        issues = []
        text = "**市场负责人摘要**\n- a\n- b\n- c\n---"
        _check_market_summary_quality("test", text, issues)
        too_long = [i for i in issues if i.code == "market_summary_too_long"]
        assert len(too_long) == 0


class TestNormalizeSegment:
    def test_normalize(self):
        result = _normalize_segment_for_check("iOS / Facebook")
        assert "ios" in result
        assert "facebook" in result

    def test_meta_to_facebook(self):
        result = _normalize_segment_for_check("iOS / Meta")
        assert "facebook" in result
        assert "meta" not in result
