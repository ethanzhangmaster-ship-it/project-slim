"""ASO 优化循环器 + 自然量监控器.

自动定期扫描所有 Google Play 游戏, 生成/更新 ASO 部署包, 追踪自然量增长.

核心能力:
  1. ASOOptimizationLoop — 定期扫描 game_registry, 自动优化所有 Google Play 游戏
  2. OrganicGrowthMonitor — 追踪 organic installs/revenue/DAU, 计算增长趋势
  3. GrowthDashboard — 汇总面板, 展示整体自然量增长状况

设计原则:
  - 完全自动: 无需人工干预, 定期运行
  - 数据驱动: 基于指标变化自动决定是否需要重新优化
  - 可追踪: 每次优化和指标变化都有记录
  - 可视化: Dashboard 展示增长趋势

用法:
  loop = ASOOptimizationLoop()
  loop.run_cycle()  # 跑一次优化循环

  monitor = OrganicGrowthMonitor()
  monitor.record_metrics("Bible Quiz", organic_installs=2000, organic_revenue=1000)
  trend = monitor.get_growth_trend("Bible Quiz")
"""

from __future__ import annotations

import json
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .aso_auto_optimizer import (
    ASOAutoOptimizer,
    ASOMetrics,
    get_aso_auto_optimizer,
)
from .organic_growth_engine import (
    GooglePlayASOEngine,
    OrganicGrowthReport,
    get_google_play_aso_engine,
)

logger = logging.getLogger(__name__)


# ── 数据模型 ──────────────────────────────────────────────────

@dataclass
class GameRecord:
    """游戏记录 — 从 game_registry.json 加载."""

    game_id: str
    package_name: str = ""
    genre: str = "casual"
    platform: str = "google_play"
    country: str = "US"
    account: str = ""

    @classmethod
    def from_registry(cls, data: Dict[str, Any]) -> "GameRecord":
        return cls(
            game_id=data.get("game_id", ""),
            package_name=data.get("package_name", ""),
            genre=(data.get("genre", "") or "casual").lower(),
            platform=data.get("platform", "google_play"),
            country=data.get("country", "US"),
            account=data.get("account", ""),
        )


@dataclass
class GrowthTrend:
    """自然量增长趋势."""

    game_id: str
    period_days: int = 30
    # 变化率
    organic_installs_change: float = 0.0
    organic_revenue_change: float = 0.0
    organic_dau_change: float = 0.0
    store_conversion_change: float = 0.0
    # 当前值
    current_organic_installs: int = 0
    current_organic_revenue: float = 0.0
    current_organic_dau: int = 0
    # 优化次数
    optimization_count: int = 0
    # 状态
    status: str = "stable"  # growing / stable / declining
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "period_days": self.period_days,
            "organic_installs_change_pct": round(self.organic_installs_change * 100, 1),
            "organic_revenue_change_pct": round(self.organic_revenue_change * 100, 1),
            "organic_dau_change_pct": round(self.organic_dau_change * 100, 1),
            "store_conversion_change_pct": round(self.store_conversion_change * 100, 1),
            "current_organic_installs": self.current_organic_installs,
            "current_organic_revenue": round(self.current_organic_revenue, 2),
            "current_organic_dau": self.current_organic_dau,
            "optimization_count": self.optimization_count,
            "status": self.status,
            "recommendation": self.recommendation,
        }


@dataclass
class DashboardSummary:
    """Dashboard 汇总."""

    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_games: int = 0
    total_optimizations: int = 0
    total_organic_installs: int = 0
    total_organic_revenue: float = 0.0
    total_organic_dau: int = 0
    growing_games: int = 0
    stable_games: int = 0
    declining_games: int = 0
    top_performers: List[Dict[str, Any]] = field(default_factory=list)
    needs_optimization: List[Dict[str, Any]] = field(default_factory=list)
    overall_status: str = "init"
    overall_recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "total_games": self.total_games,
            "total_optimizations": self.total_optimizations,
            "total_organic_installs": self.total_organic_installs,
            "total_organic_revenue": round(self.total_organic_revenue, 2),
            "total_organic_dau": self.total_organic_dau,
            "growing_games": self.growing_games,
            "stable_games": self.stable_games,
            "declining_games": self.declining_games,
            "top_performers": self.top_performers,
            "needs_optimization": self.needs_optimization,
            "overall_status": self.overall_status,
            "overall_recommendation": self.overall_recommendation,
        }


# ── ASO 优化循环器 ────────────────────────────────────────────

class ASOOptimizationLoop:
    """自动 ASO 优化循环器.

    定期扫描 game_registry, 为所有 Google Play 游戏生成/更新 ASO 部署包.
    基于指标变化决定是否需要重新优化.

    线程安全: 单实例可并发调用.
    """

    def __init__(
        self,
        data_dir: str = "data",
        project_root: str = ".",
    ) -> None:
        self._data_dir = Path(data_dir)
        self._project_root = Path(project_root)
        self._optimizer = get_aso_auto_optimizer(
            data_dir=str(self._data_dir / "aso_deploy")
        )
        self._engine = get_google_play_aso_engine()
        self._monitor: Optional[OrganicGrowthMonitor] = None
        self._lock = threading.Lock()
        self._games: List[GameRecord] = []
        self._last_cycle_at: Optional[str] = None

    def _load_games_from_registry(self) -> List[GameRecord]:
        """从 game_registry.json 加载所有 Google Play 游戏.

        支持两种结构:
          1. 新结构 (P1.4): ``{"games": [...]}``  — 每项含 game_id/package_name/genre/platform/max_account
          2. 旧结构 (兼容): ``{"accounts": {name: {"apps": [...]}}}``
        """
        registry_path = self._data_dir / "game_registry.json"
        if not registry_path.exists():
            logger.warning("game_registry.json 不存在: %s", registry_path)
            return []

        with registry_path.open(encoding="utf-8") as f:
            data = json.load(f)

        games: List[GameRecord] = []

        # ── 新结构: games 数组 ──
        raw_games = data.get("games") or []
        for app in raw_games:
            if not isinstance(app, dict):
                continue
            game_id = (app.get("game_id") or "").strip()
            package_name = (app.get("package_name") or "").strip()
            platform_raw = (app.get("platform") or "").lower()
            genre = (app.get("genre") or "").lower().strip()

            # 判断是否为 Google Play 游戏
            is_google_play = self._is_google_play(platform_raw, package_name, game_id)
            if not is_google_play:
                continue

            # 品类: 基于 game_id 关键词猜测更精准的品类
            # registry 中的 genre 很多是泛化的 "puzzle"/"casual",
            # 但 game_id 可能含更具体的品类信号 (bible/quiz/trivia/merge/word 等)
            guessed_genre = self._guess_genre(game_id or package_name)
            if not genre or genre == "unknown":
                genre = guessed_genre
            elif guessed_genre and guessed_genre not in ("casual", "puzzle", genre):
                # 猜测到更具体的品类 (非泛化, 非当前值) — 用猜测值覆盖
                # 例: registry=puzzle, game_id 含 "bible"+"quiz" → guessed=trivia
                genre = guessed_genre

            account = ""
            max_apps = app.get("max_apps") or []
            if isinstance(max_apps, list) and max_apps:
                account = str(max_apps[0])
            if not account:
                account = app.get("max_account") or ""

            games.append(GameRecord(
                game_id=game_id or package_name,
                package_name=package_name,
                genre=genre or "casual",
                platform="google_play",
                country=app.get("country", "US"),
                account=account,
            ))

        # ── 旧结构兼容: accounts ──
        if not games:
            accounts = data.get("accounts") or {}
            for acct_name, acct_data in accounts.items():
                if not isinstance(acct_data, dict):
                    continue
                for app in acct_data.get("apps", []) or []:
                    platform_raw = (app.get("platform", "") or "").lower()
                    pkg = (app.get("package_name") or "").strip()
                    gid = (app.get("game_id") or "").strip()
                    if not self._is_google_play(platform_raw, pkg, gid):
                        continue
                    games.append(GameRecord(
                        game_id=gid or pkg,
                        package_name=pkg,
                        genre=self._guess_genre(gid or pkg),
                        platform="google_play",
                        country=app.get("country", "US"),
                        account=acct_name,
                    ))

        logger.info("从 game_registry.json 加载了 %d 个 Google Play 游戏", len(games))
        return games

    @staticmethod
    def _is_google_play(platform: str, package_name: str, game_id: str) -> bool:
        """判断是否为 Google Play (Android) 游戏.

        判断优先级:
          1. platform 字段明确为 android/google_play
          2. platform 为 unknown 但 package_name 或 game_id 符合 Android 包名格式
        """
        if platform in ("android", "google_play"):
            return True
        if platform and platform not in ("unknown", ""):
            return False
        # platform 为 unknown / 空 — 用包名格式判断
        candidate = package_name or game_id
        if not candidate:
            return False
        # Android 包名通常含至少一个点, 且不含斜杠
        return "." in candidate and "/" not in candidate and not candidate.endswith(".ios")

    @staticmethod
    def _guess_genre(game_id: str) -> str:
        """根据 game_id 猜测品类 — 优先匹配更精准的子品类."""
        gid = game_id.lower()
        # 精准子品类优先 (顺序很重要)
        if any(w in gid for w in ("bible", "bibbia", "biblia", "biblique", "bíblica", "bíblico")):
            return "bible"
        if "merge" in gid:
            return "merge"
        if any(w in gid for w in ("quiz", "trivia")):
            return "trivia"
        if any(w in gid for w in ("hospital", "salon", "chef", "model", "makeover")):
            return "simulation"
        if any(w in gid for w in ("word", "crossword", "spelling", "tile")):
            return "puzzle"
        if "monster" in gid:
            return "merge"
        return "casual"

    def get_games(self) -> List[GameRecord]:
        """获取所有待优化的游戏."""
        if not self._games:
            self._games = self._load_games_from_registry()
        return self._games

    def run_cycle(
        self,
        force: bool = False,
        only_game_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """运行一次优化循环.

        Args:
            force: 是否强制重新优化 (即使指标没变化)
            only_game_ids: 只优化指定游戏 (可选)

        Returns:
            循环结果汇总
        """
        started_at = datetime.now(timezone.utc)
        games = self.get_games()
        if only_game_ids:
            games = [g for g in games if g.game_id in only_game_ids]

        results: List[Dict[str, Any]] = []
        optimized = 0
        skipped = 0
        failed = 0

        for game in games:
            if not game.game_id:
                continue
            try:
                # 检查是否需要重新优化
                needs_opt = force or self._needs_optimization(game.game_id)

                if needs_opt:
                    pkg = self._optimizer.generate_deploy_package(
                        game_id=game.game_id,
                        package_name=game.package_name,
                        genre=game.genre,
                    )
                    self._optimizer.save_package(pkg)
                    self._optimizer.record_optimization(
                        game_id=game.game_id,
                        optimization_type="listing_update",
                        description=f"自动循环优化 v{pkg.version} (genre={game.genre})",
                    )
                    optimized += 1
                    results.append({
                        "game_id": game.game_id,
                        "status": "optimized",
                        "publish_status": "generated_not_published",
                        "title": pkg.title,
                        "keywords": len(pkg.keywords),
                        "localizations": len(pkg.localizations),
                    })
                else:
                    skipped += 1
                    history = self._optimizer.get_optimization_history(game.game_id)
                    latest = history[-1] if history else {}
                    latest_status = latest.get("status")
                    if latest_status == "generated":
                        skip_reason = "部署包已生成, 尚未确认发布到 Google Play"
                    elif latest_status in ("published", "deployed") \
                            and not latest.get("after_metrics"):
                        skip_reason = "已确认发布, 等待真实效果数据"
                    else:
                        skip_reason = "指标稳定, 无需重新优化"
                    results.append({
                        "game_id": game.game_id,
                        "status": "skipped",
                        "reason": skip_reason,
                    })
            except Exception as exc:
                failed += 1
                logger.error("优化失败 %s: %s", game.game_id, exc)
                results.append({
                    "game_id": game.game_id,
                    "status": "failed",
                    "error": str(exc)[:100],
                })

        finished_at = datetime.now(timezone.utc)
        self._last_cycle_at = finished_at.isoformat()

        summary = {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": (finished_at - started_at).total_seconds(),
            "total_games": len(games),
            "optimized": optimized,
            "skipped": skipped,
            "failed": failed,
            "results": results,
        }

        # 保存循环记录
        self._save_cycle_record(summary)

        return summary

    def _needs_optimization(self, game_id: str) -> bool:
        """判断是否需要重新优化."""
        history = self._optimizer.get_optimization_history(game_id)
        if not history:
            return True  # 从未优化过

        latest = history[-1]
        if latest.get("status") in ("generated", "published", "deployed") \
                and not latest.get("after_metrics"):
            # generated: 等待真实发布；published/deployed: 等待效果数据。
            # 两种情况都不应每天盲目覆盖同一部署包。
            return False

        # 如果有 after_metrics, 检查是否在下降
        after = latest.get("after_metrics")
        if after and after.get("organic_installs", 0) > 0:
            # 如果有指标但超过 7 天没更新, 重新优化
            return False

        return True  # 默认重新优化

    def run_single_game_auto_cycle(
        self,
        game_id: str,
        force_new_variant: bool = False,
    ) -> Dict[str, Any]:
        """单产品自动优化循环 — 检查指标并决定是否需要新变体.

        决策逻辑:
          1. 从未优化 → 生成 v1
          2. 已优化但无指标数据 → 等待 (不生成新变体)
          3. 指标下降 → 立即生成新变体
          4. 指标稳定/增长 → 保持当前策略
          5. force_new_variant=True → 强制生成新变体 (A/B 测试)

        Args:
            game_id: 游戏 ID (如 com.born2play.biblequiz)
            force_new_variant: 强制生成新变体

        Returns:
            循环结果
        """
        started_at = datetime.now(timezone.utc)
        monitor = self.get_monitor()

        # 获取游戏信息
        games = self.get_games()
        game = next((g for g in games if g.game_id == game_id), None)
        if game is None:
            return {
                "game_id": game_id,
                "status": "not_found",
                "error": f"游戏 {game_id} 不在 registry 中",
            }

        # 检查优化历史
        history = self._optimizer.get_optimization_history(game_id)
        latest_metrics = monitor.get_latest_metrics(game_id)
        trend = monitor.get_growth_trend(game_id)

        # 决策
        action = "skip"
        reason = ""

        if not history:
            action = "optimize"
            reason = "首次优化"
        elif force_new_variant:
            action = "optimize"
            reason = "强制生成新变体 (A/B 测试)"
        elif history[-1].get("status") == "generated":
            action = "skip"
            reason = "部署包已生成但尚未确认发布, 等待 Google Play 发布"
        elif not latest_metrics or latest_metrics.organic_installs == 0:
            # 无指标数据 — 检查上次优化距今多久
            latest_record = history[-1]
            opt_time = latest_record.get("timestamp", "")
            if opt_time:
                try:
                    opt_dt = datetime.fromisoformat(opt_time.replace("Z", "+00:00"))
                    days_since = (started_at - opt_dt).days
                    if days_since >= 7:
                        action = "optimize"
                        reason = f"已部署 {days_since} 天仍无指标数据, 生成新变体尝试不同策略"
                    else:
                        action = "skip"
                        reason = f"已部署 {days_since} 天, 等待指标数据 (最多等 7 天)"
                except (ValueError, TypeError):
                    action = "optimize"
                    reason = "无法解析上次优化时间, 生成新变体"
            else:
                action = "optimize"
                reason = "无优化时间记录, 生成新变体"
        elif trend.status == "declining":
            action = "optimize"
            reason = f"自然量下降 {trend.organic_installs_change*100:.1f}%, 生成新变体"
        elif trend.status == "growing":
            action = "skip"
            reason = f"自然量增长 {trend.organic_installs_change*100:.1f}%, 保持当前策略"
        else:
            # stable — 如果超过 14 天没优化, 尝试新变体
            latest_record = history[-1]
            opt_time = latest_record.get("timestamp", "")
            if opt_time:
                try:
                    opt_dt = datetime.fromisoformat(opt_time.replace("Z", "+00:00"))
                    days_since = (started_at - opt_dt).days
                    if days_since >= 14:
                        action = "optimize"
                        reason = f"指标稳定但 {days_since} 天未优化, 尝试新变体突破"
                    else:
                        action = "skip"
                        reason = "指标稳定, 保持当前策略"
                except (ValueError, TypeError):
                    action = "skip"
                    reason = "指标稳定, 保持当前策略"
            else:
                action = "skip"
                reason = "指标稳定, 保持当前策略"

        result: Dict[str, Any] = {
            "game_id": game_id,
            "started_at": started_at.isoformat(),
            "action": action,
            "reason": reason,
            "current_version": len(history),
            "current_status": trend.status,
            "current_installs": trend.current_organic_installs,
            "current_revenue": trend.current_organic_revenue,
        }

        if action == "optimize":
            try:
                pkg = self._optimizer.generate_deploy_package(
                    game_id=game.game_id,
                    package_name=game.package_name,
                    genre=game.genre,
                )
                self._optimizer.save_package(pkg)
                self._optimizer.record_optimization(
                    game_id=game.game_id,
                    optimization_type="listing_update",
                    description=f"自动循环优化 v{pkg.version} (genre={game.genre}) — {reason}",
                )
                result["status"] = "optimized"
                result["publish_status"] = "generated_not_published"
                result["new_version"] = pkg.version
                result["title"] = pkg.title
                result["keywords"] = len(pkg.keywords)
                result["localizations"] = len(pkg.localizations)
            except Exception as exc:
                logger.error("单产品自动优化失败 %s: %s", game_id, exc)
                result["status"] = "failed"
                result["error"] = str(exc)[:200]
        else:
            result["status"] = "skipped"

        finished_at = datetime.now(timezone.utc)
        result["finished_at"] = finished_at.isoformat()
        result["duration_seconds"] = (finished_at - started_at).total_seconds()

        # 保存循环记录
        self._save_cycle_record(result)

        return result

    def _save_cycle_record(self, summary: Dict[str, Any]) -> None:
        """保存循环记录."""
        path = self._data_dir / "aso_deploy" / "cycle_history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(summary, ensure_ascii=False, default=str) + "\n")

    def get_monitor(self) -> "OrganicGrowthMonitor":
        """获取关联的监控器."""
        if self._monitor is None:
            self._monitor = OrganicGrowthMonitor(
                data_dir=str(self._data_dir / "aso_deploy")
            )
        return self._monitor


# ── 自然量监控器 ──────────────────────────────────────────────

class OrganicGrowthMonitor:
    """自然量增长监控器.

    追踪每个游戏的 organic installs/revenue/DAU, 计算增长趋势.
    """

    def __init__(self, data_dir: str = "data/aso_deploy") -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._metrics_history: Dict[str, List[ASOMetrics]] = defaultdict(list)
        self._lock = threading.Lock()
        self._load_history()

    def record_metrics(self, game_id: str, **kwargs: Any) -> ASOMetrics:
        """记录一次指标快照."""
        metrics = ASOMetrics(game_id=game_id, **kwargs)
        with self._lock:
            self._metrics_history[game_id].append(metrics)
            if len(self._metrics_history[game_id]) > 90:  # 保留最近 90 条
                self._metrics_history[game_id] = self._metrics_history[game_id][-90:]
        self._save_history()
        return metrics

    def get_latest_metrics(self, game_id: str) -> Optional[ASOMetrics]:
        """获取最新的指标."""
        with self._lock:
            history = self._metrics_history.get(game_id, [])
            return history[-1] if history else None

    def get_growth_trend(self, game_id: str, period_days: int = 30) -> GrowthTrend:
        """计算增长趋势."""
        with self._lock:
            history = list(self._metrics_history.get(game_id, []))

        trend = GrowthTrend(game_id=game_id, period_days=period_days)

        if not history:
            trend.status = "no_data"
            trend.recommendation = "无指标数据, 请先部署 ASO 优化方案并录入指标"
            return trend

        latest = history[-1]
        trend.current_organic_installs = latest.organic_installs
        trend.current_organic_revenue = latest.organic_revenue
        trend.current_organic_dau = latest.organic_dau

        if len(history) >= 2:
            # 对比最早和最新的指标
            baseline = history[0]
            if baseline.organic_installs > 0:
                trend.organic_installs_change = (
                    (latest.organic_installs - baseline.organic_installs)
                    / baseline.organic_installs
                )
            if baseline.organic_revenue > 0:
                trend.organic_revenue_change = (
                    (latest.organic_revenue - baseline.organic_revenue)
                    / baseline.organic_revenue
                )
            if baseline.organic_dau > 0:
                trend.organic_dau_change = (
                    (latest.organic_dau - baseline.organic_dau)
                    / baseline.organic_dau
                )
            if baseline.store_conversion_rate > 0:
                trend.store_conversion_change = (
                    (latest.store_conversion_rate - baseline.store_conversion_rate)
                    / baseline.store_conversion_rate
                )

        # 判断状态
        if trend.organic_installs_change > 0.1:
            trend.status = "growing"
            trend.recommendation = "自然量增长中, 继续当前策略, 可考虑扩展到更多本地化语言"
        elif trend.organic_installs_change < -0.1:
            trend.status = "declining"
            trend.recommendation = "自然量下降, 需要重新优化标题/描述/关键词, 检查竞品动态"
        else:
            trend.status = "stable"
            trend.recommendation = "自然量稳定, 建议尝试新的关键词和内容营销策略"

        return trend

    def get_all_trends(self) -> List[GrowthTrend]:
        """获取所有游戏的增长趋势."""
        with self._lock:
            game_ids = list(self._metrics_history.keys())
        return [self.get_growth_trend(gid) for gid in game_ids]

    def get_dashboard(self) -> DashboardSummary:
        """生成 Dashboard 汇总."""
        trends = self.get_all_trends()
        summary = DashboardSummary()
        summary.total_games = len(trends)

        for trend in trends:
            summary.total_organic_installs += trend.current_organic_installs
            summary.total_organic_revenue += trend.current_organic_revenue
            summary.total_organic_dau += trend.current_organic_dau

            if trend.status == "growing":
                summary.growing_games += 1
            elif trend.status == "declining":
                summary.declining_games += 1
            else:
                summary.stable_games += 1

        # Top performers (按 organic installs 排序)
        sorted_trends = sorted(
            trends,
            key=lambda t: t.current_organic_installs,
            reverse=True,
        )
        summary.top_performers = [
            t.to_dict() for t in sorted_trends[:5]
            if t.current_organic_installs > 0
        ]

        # 需要优化的游戏
        summary.needs_optimization = [
            t.to_dict() for t in trends
            if t.status in ("declining", "no_data")
        ]

        # 整体状态
        if summary.declining_games > summary.growing_games:
            summary.overall_status = "needs_attention"
            summary.overall_recommendation = (
                f"{summary.declining_games} 个游戏自然量下降, "
                f"需要立即重新优化 ASO 策略"
            )
        elif summary.growing_games > 0:
            summary.overall_status = "growing"
            summary.overall_recommendation = (
                f"{summary.growing_games} 个游戏自然量增长中, "
                f"保持当前策略并扩展到更多市场"
            )
        else:
            summary.overall_status = "init"
            summary.overall_recommendation = (
                "系统已就绪, 等待指标数据录入. "
                "请定期录入 organic installs/revenue/DAU 指标"
            )

        return summary

    def _save_history(self) -> None:
        """保存指标历史."""
        path = self._data_dir / "metrics_history.json"
        data: Dict[str, List[Dict[str, Any]]] = {}
        for gid, metrics_list in self._metrics_history.items():
            data[gid] = [m.to_dict() for m in metrics_list]
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    def _load_history(self) -> None:
        """加载指标历史."""
        path = self._data_dir / "metrics_history.json"
        if not path.exists():
            return
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            for gid, metrics_list in data.items():
                for m in metrics_list:
                    self._metrics_history[gid].append(ASOMetrics(
                        game_id=gid,
                        store_impressions=m.get("store_impressions", 0),
                        store_conversion_rate=m.get("store_conversion_rate", 0.0),
                        organic_installs=m.get("organic_installs", 0),
                        organic_revenue=m.get("organic_revenue", 0.0),
                        organic_dau=m.get("organic_dau", 0),
                        average_rating=m.get("average_rating", 0.0),
                        rating_count=m.get("rating_count", 0),
                    ))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("加载指标历史失败: %s", exc)


# ── 单例 ──────────────────────────────────────────────────────

_loop_instance: Optional[ASOOptimizationLoop] = None
_loop_lock = threading.Lock()


def get_aso_optimization_loop(
    data_dir: str = "data",
    project_root: str = ".",
) -> ASOOptimizationLoop:
    """获取 ASO 优化循环器单例."""
    global _loop_instance
    if _loop_instance is None:
        with _loop_lock:
            if _loop_instance is None:
                _loop_instance = ASOOptimizationLoop(
                    data_dir=data_dir,
                    project_root=project_root,
                )
    return _loop_instance


def reset_aso_optimization_loop() -> None:
    """重置单例 (用于测试)."""
    global _loop_instance
    with _loop_lock:
        _loop_instance = None


_monitor_instance: Optional[OrganicGrowthMonitor] = None
_monitor_lock = threading.Lock()


def get_organic_growth_monitor(
    data_dir: str = "data/aso_deploy",
) -> OrganicGrowthMonitor:
    """获取自然量监控器单例."""
    global _monitor_instance
    if _monitor_instance is None:
        with _monitor_lock:
            if _monitor_instance is None:
                _monitor_instance = OrganicGrowthMonitor(data_dir=data_dir)
    return _monitor_instance


def reset_organic_growth_monitor() -> None:
    """重置单例 (用于测试)."""
    global _monitor_instance
    with _monitor_lock:
        _monitor_instance = None


__all__ = [
    "GameRecord",
    "GrowthTrend",
    "DashboardSummary",
    "ASOOptimizationLoop",
    "OrganicGrowthMonitor",
    "get_aso_optimization_loop",
    "reset_aso_optimization_loop",
    "get_organic_growth_monitor",
    "reset_organic_growth_monitor",
]
