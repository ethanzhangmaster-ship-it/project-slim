"""PeriodReportGenerator 测试套件 — 周期报告生成器 (日报/周报/月报).

测试覆盖:
  1. 数据模型 (ReportMetrics / PeriodReport) 序列化
  2. 枚举 (ReportPeriod / ReportType) 校验
  3. 生成器初始化
  4. 指标计算 (calculate_metrics)
  5. 各类型报告生成 (executive/growth/monetization/ua/creative/portfolio)
  6. 各周期报告生成 (daily/weekly/monthly)
  7. 报告持久化 (Markdown + JSON)
  8. 报告查询 (get_report / list_reports)
  9. 统计信息 (get_stats)
  10. API 端点 (4 个)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# 确保项目根目录在 path 中
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.market_ops.workspace.period_report_generator import (
    PeriodReport,
    PeriodReportGenerator,
    ReportMetrics,
    ReportPeriod,
    ReportType,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def generator(tmp_path: Path) -> PeriodReportGenerator:
    """每个测试用独立的临时目录, 避免污染真实数据。"""
    return PeriodReportGenerator(data_dir=str(tmp_path))


@pytest.fixture
def sample_metrics(generator: PeriodReportGenerator) -> ReportMetrics:
    """生成样例 metrics 用于章节测试。"""
    return generator.calculate_metrics("2026-08-01", "2026-08-10")


@pytest.fixture
def client(monkeypatch, tmp_path: Path) -> TestClient:
    """FastAPI TestClient, 用临时目录隔离单例。"""
    from src.market_ops.workspace import app as app_module

    # 重置单例
    if hasattr(app_module._get_period_report_generator, "_instance"):
        monkeypatch.delattr(app_module._get_period_report_generator, "_instance")

    # 注入测试 generator (使用临时目录)
    test_gen = PeriodReportGenerator(data_dir=str(tmp_path))
    monkeypatch.setattr(
        app_module,
        "_get_period_report_generator",
        lambda: test_gen,
    )

    from src.market_ops.workspace.app import app
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════
# 1. 枚举校验
# ═══════════════════════════════════════════════════════════════


class TestEnums:
    """ReportPeriod / ReportType 枚举测试。"""

    def test_report_period_all(self):
        """三种周期。"""
        assert ReportPeriod.all() == ["daily", "weekly", "monthly"]

    def test_report_period_is_valid(self):
        assert ReportPeriod.is_valid("daily") is True
        assert ReportPeriod.is_valid("weekly") is True
        assert ReportPeriod.is_valid("monthly") is True
        assert ReportPeriod.is_valid("quarterly") is False

    def test_report_type_all(self):
        """六种类型。"""
        assert set(ReportType.all()) == {
            "executive", "growth", "monetization", "ua", "creative", "portfolio",
        }

    def test_report_type_is_valid(self):
        for t in ReportType.all():
            assert ReportType.is_valid(t) is True
        assert ReportType.is_valid("unknown") is False


# ═══════════════════════════════════════════════════════════════
# 2. 数据模型
# ═══════════════════════════════════════════════════════════════


class TestDataModels:
    """数据模型测试。"""

    def test_report_metrics_defaults(self):
        """默认值。"""
        m = ReportMetrics(period="daily", start_date="2026-08-10", end_date="2026-08-10")
        assert m.total_revenue == 0.0
        assert m.total_spend == 0.0
        assert m.total_installs == 0
        assert m.avg_dau == 0
        assert m.top_games == []
        assert m.top_creatives == []
        assert m.anomalies == []
        assert m.alerts == []

    def test_report_metrics_to_dict(self):
        """to_dict 完整序列化。"""
        m = ReportMetrics(
            period="weekly", start_date="2026-08-04", end_date="2026-08-10",
            total_revenue=1000.0, total_spend=200.0, total_installs=500,
            avg_dau=3000, avg_arpdau=0.3333, overall_roas=500.0,
        )
        d = m.to_dict()
        assert d["period"] == "weekly"
        assert d["total_revenue"] == 1000.0
        assert d["total_installs"] == 500
        assert "alerts" in d
        assert "anomalies" in d

    def test_period_report_to_dict(self, sample_metrics):
        """PeriodReport.to_dict 含 metrics 字段。"""
        r = PeriodReport(
            report_id="test_001",
            report_type="executive",
            period="daily",
            start_date="2026-08-10",
            end_date="2026-08-10",
            metrics=sample_metrics,
            sections=[{"title": "x", "content": "y", "data": {}}],
            summary="summary",
            recommendations=["r1"],
            generated_at="2026-08-10T10:00:00",
        )
        d = r.to_dict()
        assert d["report_id"] == "test_001"
        assert d["report_type"] == "executive"
        assert d["period"] == "daily"
        assert d["metrics"]["total_revenue"] == sample_metrics.total_revenue
        assert d["sections"] == [{"title": "x", "content": "y", "data": {}}]
        assert d["recommendations"] == ["r1"]


# ═══════════════════════════════════════════════════════════════
# 3. 生成器初始化
# ═══════════════════════════════════════════════════════════════


class TestGeneratorInit:
    """生成器初始化测试。"""

    def test_default_data_dir(self):
        """不传 data_dir 时使用项目 data/。"""
        gen = PeriodReportGenerator()
        assert gen.reports_root.name == "reports"

    def test_custom_data_dir(self, tmp_path: Path):
        """自定义数据目录。"""
        gen = PeriodReportGenerator(data_dir=str(tmp_path))
        assert gen.data_dir == tmp_path
        assert gen.reports_root == tmp_path / "reports"
        # 自动创建
        assert gen.reports_root.exists()

    def test_cache_initial_empty(self, generator):
        assert generator._cache == {}


# ═══════════════════════════════════════════════════════════════
# 4. 指标计算
# ═══════════════════════════════════════════════════════════════


class TestCalculateMetrics:
    """calculate_metrics 测试。"""

    def test_daily_metrics(self, generator):
        """日报指标 (1 天)。"""
        m = generator.calculate_metrics("2026-08-10", "2026-08-10")
        assert m.period == "daily"
        assert m.start_date == "2026-08-10"
        assert m.end_date == "2026-08-10"
        assert m.total_revenue > 0
        assert m.total_spend > 0
        assert m.total_installs > 0
        assert m.avg_dau > 0
        # 派生指标
        assert m.avg_arpdau == round(m.total_revenue / m.avg_dau, 4)
        assert m.overall_roas == round((m.total_revenue / m.total_spend) * 100, 1)

    def test_weekly_metrics(self, generator):
        """周报指标 (7 天)。"""
        m = generator.calculate_metrics("2026-08-04", "2026-08-10")
        assert m.period == "weekly"
        # 周基线应大于日基线
        daily = generator.calculate_metrics("2026-08-10", "2026-08-10")
        assert m.total_revenue > daily.total_revenue

    def test_monthly_metrics(self, generator):
        """月报指标 (> 7 天)。"""
        m = generator.calculate_metrics("2026-08-01", "2026-08-31")
        assert m.period == "monthly"
        # 月基线应大于周基线
        weekly = generator.calculate_metrics("2026-08-04", "2026-08-10")
        assert m.total_revenue > weekly.total_revenue

    def test_top_games_default(self, generator):
        """默认 top_games 列表。"""
        m = generator.calculate_metrics("2026-08-10", "2026-08-10")
        assert len(m.top_games) == 5
        # 按收入降序
        revenues = [g["revenue"] for g in m.top_games]
        assert revenues == sorted(revenues, reverse=True)
        # 占比总和约 100%
        total_share = sum(g["revenue_share"] for g in m.top_games)
        assert 99.0 < total_share < 101.0

    def test_top_games_custom_ids(self, generator):
        """自定义 game_ids。"""
        m = generator.calculate_metrics(
            "2026-08-10", "2026-08-10",
            game_ids=["g1", "g2"],
        )
        assert len(m.top_games) == 2
        ids = [g["game_id"] for g in m.top_games]
        assert set(ids) == {"g1", "g2"}

    def test_top_creatives_default(self, generator):
        """默认 top_creatives 列表。"""
        m = generator.calculate_metrics("2026-08-10", "2026-08-10")
        assert len(m.top_creatives) == 5
        for c in m.top_creatives:
            assert "creative_id" in c
            assert "name" in c
            assert "ctr" in c
            assert "spend" in c

    def test_alerts_when_low_roas(self, generator):
        """ROAS 偏低时生成告警。"""
        m = generator.calculate_metrics("2026-08-10", "2026-08-10")
        if m.overall_roas < 100.0:
            assert any(a["alert_id"] == "low_roas" for a in m.alerts)

    def test_anomalies_when_revenue_decline(self, generator):
        """收入下降时生成异常。"""
        m = generator.calculate_metrics("2026-08-10", "2026-08-10")
        if m.revenue_trend < -5.0:
            assert any(a["type"] == "revenue_decline" for a in m.anomalies)


# ═══════════════════════════════════════════════════════════════
# 5. 各类型报告生成
# ═══════════════════════════════════════════════════════════════


class TestReportTypes:
    """各报告类型生成测试。"""

    @pytest.mark.parametrize("report_type", ReportType.all())
    def test_generate_report_returns_valid_object(self, generator, report_type):
        """每种 report_type 都能生成报告。"""
        report = generator.generate_report(
            report_type=report_type,
            period="daily",
            end_date="2026-08-10",
        )
        assert isinstance(report, PeriodReport)
        assert report.report_type == report_type
        assert report.period == "daily"
        assert report.report_id.startswith(f"{report_type}_daily_2026-08-10_")

    def test_executive_has_all_sections(self, generator):
        """executive 报告包含全部章节。"""
        report = generator.generate_report("executive", "daily", "2026-08-10")
        titles = [s["title"] for s in report.sections]
        assert "增长分析" in titles
        assert "变现分析" in titles
        assert "用户获取 (UA)" in titles
        assert "创意素材" in titles
        assert "组合俯瞰" in titles

    def test_growth_has_growth_and_ua_sections(self, generator):
        """growth 报告包含 growth + ua 章节。"""
        report = generator.generate_report("growth", "daily", "2026-08-10")
        titles = [s["title"] for s in report.sections]
        assert "增长分析" in titles
        assert "用户获取 (UA)" in titles
        assert "变现分析" not in titles

    def test_monetization_has_monetization_and_portfolio(self, generator):
        """monetization 报告包含 monetization + portfolio 章节。"""
        report = generator.generate_report("monetization", "daily", "2026-08-10")
        titles = [s["title"] for s in report.sections]
        assert "变现分析" in titles
        assert "组合俯瞰" in titles

    def test_ua_has_ua_and_creative(self, generator):
        """ua 报告包含 ua + creative 章节。"""
        report = generator.generate_report("ua", "daily", "2026-08-10")
        titles = [s["title"] for s in report.sections]
        assert "用户获取 (UA)" in titles
        assert "创意素材" in titles

    def test_creative_only_has_creative(self, generator):
        """creative 报告只有 creative 章节。"""
        report = generator.generate_report("creative", "daily", "2026-08-10")
        titles = [s["title"] for s in report.sections]
        assert titles == ["创意素材"]

    def test_portfolio_has_portfolio_growth_monetization(self, generator):
        """portfolio 报告包含 portfolio + growth + monetization。"""
        report = generator.generate_report("portfolio", "daily", "2026-08-10")
        titles = [s["title"] for s in report.sections]
        assert "组合俯瞰" in titles
        assert "增长分析" in titles
        assert "变现分析" in titles

    def test_executive_summary_uses_generate_executive_summary(self, generator):
        """executive 报告 summary 来自 generate_executive_summary。"""
        report = generator.generate_report("executive", "daily", "2026-08-10")
        assert "高管摘要" in report.summary

    def test_non_executive_summary_uses_build_summary(self, generator):
        """非 executive 报告 summary 来自 _build_summary。"""
        report = generator.generate_report("growth", "daily", "2026-08-10")
        assert "增长报告" in report.summary

    def test_recommendations_non_empty(self, generator):
        """recommendations 至少有一条建议。"""
        report = generator.generate_report("executive", "daily", "2026-08-10")
        assert len(report.recommendations) >= 1

    def test_invalid_report_type_raises(self, generator):
        """无效 report_type 抛 ValueError。"""
        with pytest.raises(ValueError, match="无效的 report_type"):
            generator.generate_report("invalid", "daily", "2026-08-10")


# ═══════════════════════════════════════════════════════════════
# 6. 各周期报告生成
# ═══════════════════════════════════════════════════════════════


class TestReportPeriods:
    """各周期报告生成测试。"""

    @pytest.mark.parametrize("period", ReportPeriod.all())
    def test_generate_each_period(self, generator, period):
        """每种 period 都能生成报告。"""
        report = generator.generate_report(
            report_type="executive",
            period=period,
            end_date="2026-08-10",
        )
        assert report.period == period

    def test_daily_start_equals_end(self, generator):
        """日报 start_date == end_date。"""
        report = generator.generate_report("executive", "daily", "2026-08-10")
        assert report.start_date == "2026-08-10"
        assert report.end_date == "2026-08-10"

    def test_weekly_start_is_monday(self, generator):
        """周报 start_date 是周一。"""
        # 2026-08-10 是周一
        report = generator.generate_report("executive", "weekly", "2026-08-10")
        assert report.start_date == "2026-08-10"
        # 2026-08-12 是周三, 周一应该是 2026-08-10
        report2 = generator.generate_report("executive", "weekly", "2026-08-12")
        assert report2.start_date == "2026-08-10"

    def test_monthly_start_is_first_day(self, generator):
        """月报 start_date 是月初。"""
        report = generator.generate_report("executive", "monthly", "2026-08-15")
        assert report.start_date == "2026-08-01"
        assert report.end_date == "2026-08-15"

    def test_end_date_none_uses_today(self, generator):
        """end_date=None 用今天。"""
        from datetime import date
        today_str = date.today().isoformat()
        report = generator.generate_report("executive", "daily", end_date=None)
        assert report.end_date == today_str

    def test_invalid_period_raises(self, generator):
        """无效 period 抛 ValueError。"""
        with pytest.raises(ValueError, match="无效的 period"):
            generator.generate_report("executive", "quarterly", "2026-08-10")


# ═══════════════════════════════════════════════════════════════
# 7. 报告持久化
# ═══════════════════════════════════════════════════════════════


class TestPersistence:
    """报告持久化测试。"""

    def test_md_file_created(self, generator):
        """Markdown 文件被创建。"""
        report = generator.generate_report("executive", "daily", "2026-08-10")
        md_path = Path(report.file_path)
        assert md_path.exists()
        assert md_path.suffix == ".md"

    def test_json_file_created(self, generator):
        """JSON 文件被创建 (同目录)。"""
        report = generator.generate_report("executive", "daily", "2026-08-10")
        md_path = Path(report.file_path)
        json_path = md_path.with_suffix(".json")
        assert json_path.exists()

    def test_md_contains_summary_and_sections(self, generator):
        """Markdown 文件包含摘要和章节内容。"""
        report = generator.generate_report("executive", "daily", "2026-08-10")
        md_text = Path(report.file_path).read_text(encoding="utf-8")
        assert "高管摘要" in md_text
        assert "增长分析" in md_text
        assert "行动建议" in md_text

    def test_json_contains_full_data(self, generator):
        """JSON 文件能反序列化为完整字典。"""
        report = generator.generate_report("executive", "daily", "2026-08-10")
        md_path = Path(report.file_path)
        json_path = md_path.with_suffix(".json")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["report_id"] == report.report_id
        assert data["report_type"] == "executive"
        assert "metrics" in data
        assert "sections" in data
        # file_path 字段已被持久化
        assert data["file_path"] == report.file_path

    def test_persisted_under_period_subdir(self, generator):
        """报告持久化在 {period}/ 子目录下。"""
        report = generator.generate_report("executive", "weekly", "2026-08-10")
        md_path = Path(report.file_path)
        assert md_path.parent.name == "weekly"

    def test_filename_pattern(self, generator):
        """文件名: {end_date}.{report_type}.{ext}。"""
        report = generator.generate_report("growth", "daily", "2026-08-10")
        md_path = Path(report.file_path)
        assert md_path.name == "2026-08-10.growth.md"


# ═══════════════════════════════════════════════════════════════
# 8. 报告查询
# ═══════════════════════════════════════════════════════════════


class TestQuery:
    """报告查询测试。"""

    def test_get_report_from_cache(self, generator):
        """刚生成的报告从缓存读。"""
        report = generator.generate_report("executive", "daily", "2026-08-10")
        got = generator.get_report(report.report_id)
        assert got is not None
        assert got.report_id == report.report_id

    def test_get_report_from_disk(self, generator):
        """新 generator 从磁盘读已生成的报告。"""
        report = generator.generate_report("executive", "daily", "2026-08-10")
        # 新实例, 无缓存
        new_gen = PeriodReportGenerator(data_dir=str(generator.data_dir))
        got = new_gen.get_report(report.report_id)
        assert got is not None
        assert got.report_id == report.report_id
        assert got.report_type == "executive"

    def test_get_report_not_found(self, generator):
        """不存在的 report_id 返回 None。"""
        assert generator.get_report("nonexistent_id") is None

    def test_get_report_with_short_id(self, generator):
        """格式错误的 report_id 返回 None。"""
        assert generator.get_report("ab") is None

    def test_list_reports_empty(self, generator):
        """空时返回空列表。"""
        assert generator.list_reports() == []

    def test_list_reports_all(self, generator):
        """列出所有报告。"""
        generator.generate_report("executive", "daily", "2026-08-10")
        generator.generate_report("growth", "weekly", "2026-08-10")
        generator.generate_report("monetization", "monthly", "2026-08-10")
        reports = generator.list_reports()
        assert len(reports) == 3

    def test_list_reports_by_period(self, generator):
        """按 period 过滤。"""
        generator.generate_report("executive", "daily", "2026-08-10")
        generator.generate_report("executive", "weekly", "2026-08-10")
        generator.generate_report("executive", "monthly", "2026-08-10")
        weekly = generator.list_reports(period="weekly")
        assert len(weekly) == 1
        assert weekly[0].period == "weekly"

    def test_list_reports_by_type(self, generator):
        """按 report_type 过滤。"""
        generator.generate_report("executive", "daily", "2026-08-10")
        generator.generate_report("growth", "daily", "2026-08-10")
        growth = generator.list_reports(report_type="growth")
        assert len(growth) == 1
        assert growth[0].report_type == "growth"

    def test_list_reports_combined_filter(self, generator):
        """组合过滤。"""
        generator.generate_report("executive", "daily", "2026-08-10")
        generator.generate_report("growth", "daily", "2026-08-10")
        generator.generate_report("executive", "weekly", "2026-08-10")
        reports = generator.list_reports(period="daily", report_type="executive")
        assert len(reports) == 1
        assert reports[0].period == "daily"
        assert reports[0].report_type == "executive"


# ═══════════════════════════════════════════════════════════════
# 9. 统计信息
# ═══════════════════════════════════════════════════════════════


class TestStats:
    """统计信息测试。"""

    def test_empty_stats(self, generator):
        """空时统计全为 0。"""
        stats = generator.get_stats()
        assert stats["total_reports"] == 0
        assert stats["by_period"] == {"daily": 0, "weekly": 0, "monthly": 0}
        for t in ReportType.all():
            assert stats["by_type"][t] == 0
        assert stats["latest_generated_at"] == ""

    def test_stats_after_generation(self, generator):
        """生成后统计正确。"""
        generator.generate_report("executive", "daily", "2026-08-10")
        generator.generate_report("growth", "weekly", "2026-08-10")
        generator.generate_report("executive", "monthly", "2026-08-10")
        stats = generator.get_stats()
        assert stats["total_reports"] == 3
        assert stats["by_period"]["daily"] == 1
        assert stats["by_period"]["weekly"] == 1
        assert stats["by_period"]["monthly"] == 1
        assert stats["by_type"]["executive"] == 2
        assert stats["by_type"]["growth"] == 1
        # latest_generated_at 应非空
        assert stats["latest_generated_at"] != ""


# ═══════════════════════════════════════════════════════════════
# 10. 章节生成器
# ═══════════════════════════════════════════════════════════════


class TestSectionBuilders:
    """章节生成器测试。"""

    def test_executive_summary(self, generator, sample_metrics):
        summary = generator.generate_executive_summary(sample_metrics)
        assert "高管摘要" in summary
        assert "总收入" in summary
        assert "ROAS" in summary

    def test_growth_section(self, generator, sample_metrics):
        section = generator.generate_growth_section(sample_metrics)
        assert section["title"] == "增长分析"
        assert "总安装" in section["content"]
        assert "installs_trend" in section["data"]

    def test_monetization_section(self, generator, sample_metrics):
        section = generator.generate_monetization_section(sample_metrics)
        assert section["title"] == "变现分析"
        assert "总收入" in section["content"]
        assert "net_profit" in section["data"]
        assert section["data"]["net_profit"] == sample_metrics.total_revenue - sample_metrics.total_spend

    def test_ua_section(self, generator, sample_metrics):
        section = generator.generate_ua_section(sample_metrics)
        assert section["title"] == "用户获取 (UA)"
        assert "CPI" in section["content"]
        assert "cpi" in section["data"]

    def test_creative_section(self, generator, sample_metrics):
        section = generator.generate_creative_section(sample_metrics)
        assert section["title"] == "创意素材"
        assert "素材" in section["content"]

    def test_portfolio_section(self, generator, sample_metrics):
        section = generator.generate_portfolio_section(sample_metrics)
        assert section["title"] == "组合俯瞰"
        assert "Top 游戏" in section["content"]
        assert "top_games" in section["data"]


# ═══════════════════════════════════════════════════════════════
# 11. API 端点
# ═══════════════════════════════════════════════════════════════


class TestAPIEndpoints:
    """API 端点测试。"""

    def test_generate_report_success(self, client: TestClient):
        """POST /api/reports/generate 成功。"""
        resp = client.post("/api/reports/generate", json={
            "report_type": "executive",
            "period": "daily",
            "end_date": "2026-08-10",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_type"] == "executive"
        assert data["period"] == "daily"
        assert data["end_date"] == "2026-08-10"
        assert "metrics" in data
        assert "sections" in data
        assert "summary" in data

    def test_generate_report_with_game_ids(self, client: TestClient):
        """POST 带 game_ids。"""
        resp = client.post("/api/reports/generate", json={
            "report_type": "growth",
            "period": "weekly",
            "end_date": "2026-08-10",
            "game_ids": ["g1", "g2"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["metrics"]["top_games"]) == 2

    def test_generate_report_invalid_type(self, client: TestClient):
        """无效 report_type → 400。"""
        resp = client.post("/api/reports/generate", json={
            "report_type": "invalid",
            "period": "daily",
        })
        assert resp.status_code == 400

    def test_generate_report_invalid_period(self, client: TestClient):
        """无效 period → 400。"""
        resp = client.post("/api/reports/generate", json={
            "report_type": "executive",
            "period": "quarterly",
        })
        assert resp.status_code == 400

    def test_list_reports_empty(self, client: TestClient):
        """GET /api/reports 空列表。"""
        resp = client.get("/api/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["reports"] == []

    def test_list_reports_after_generation(self, client: TestClient):
        """生成后 GET /api/reports 返回列表。"""
        client.post("/api/reports/generate", json={
            "report_type": "executive",
            "period": "daily",
            "end_date": "2026-08-10",
        })
        resp = client.get("/api/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_list_reports_filter_by_period(self, client: TestClient):
        """按 period 过滤。"""
        client.post("/api/reports/generate", json={
            "report_type": "executive", "period": "daily", "end_date": "2026-08-10",
        })
        client.post("/api/reports/generate", json={
            "report_type": "executive", "period": "weekly", "end_date": "2026-08-10",
        })
        resp = client.get("/api/reports?period=weekly")
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["period"] == "weekly" for r in data["reports"])

    def test_list_reports_filter_by_type(self, client: TestClient):
        """按 report_type 过滤。"""
        client.post("/api/reports/generate", json={
            "report_type": "executive", "period": "daily", "end_date": "2026-08-10",
        })
        client.post("/api/reports/generate", json={
            "report_type": "growth", "period": "daily", "end_date": "2026-08-10",
        })
        resp = client.get("/api/reports?report_type=growth")
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["report_type"] == "growth" for r in data["reports"])

    def test_get_report_found(self, client: TestClient):
        """GET /api/reports/{report_id} 成功。"""
        gen_resp = client.post("/api/reports/generate", json={
            "report_type": "executive", "period": "daily", "end_date": "2026-08-10",
        })
        report_id = gen_resp.json()["report_id"]
        resp = client.get(f"/api/reports/{report_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_id"] == report_id

    def test_get_report_not_found(self, client: TestClient):
        """不存在的 report_id → 404。"""
        resp = client.get("/api/reports/nonexistent_id")
        assert resp.status_code == 404

    def test_reports_stats_empty(self, client: TestClient):
        """GET /api/reports/stats 空时统计。"""
        resp = client.get("/api/reports/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_reports"] == 0
        assert "by_period" in data
        assert "by_type" in data

    def test_reports_stats_after_generation(self, client: TestClient):
        """生成后 stats 正确。"""
        client.post("/api/reports/generate", json={
            "report_type": "executive", "period": "daily", "end_date": "2026-08-10",
        })
        client.post("/api/reports/generate", json={
            "report_type": "growth", "period": "weekly", "end_date": "2026-08-10",
        })
        resp = client.get("/api/reports/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_reports"] == 2
        assert data["by_period"]["daily"] == 1
        assert data["by_period"]["weekly"] == 1

    def test_stats_route_before_id_route(self, client: TestClient):
        """stats 路由不会被 /{report_id} 路由匹配。"""
        # /api/reports/stats 应被识别为 stats 端点, 不是 report_id='stats'
        resp = client.get("/api/reports/stats")
        assert resp.status_code == 200
        # 即使有 report_id 叫 'stats' 也应优先匹配 stats 端点
        data = resp.json()
        assert "total_reports" in data
