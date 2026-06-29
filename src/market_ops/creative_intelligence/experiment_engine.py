"""Experimentation Engine - Production v2.0 (FinalBandit 接入)

Spec §13 Final Architecture 封版接入。
唯一 Bandit: FinalBandit (theta/sigma/trials)。
所有 v1-v4 旧 Bandit 调用已 deprecated。

数据流 (Spec §13.9):
    Facebook API → Observation → Reward → FinalBandit Update(theta,sigma) → Policy(theta DESC) → Sampling → Facebook

唯一写路径 (Spec §6):
    log_experiment(experiment)     — experiment + variant 表
    backfill_results(experiment_id) — metrics 表
"""
from __future__ import annotations

import importlib
import json
import os
import random
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "src"))

_ENV = _ROOT / ".env"
if _ENV.exists():
    for _line in _ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


# ===========================================================================
# Core Objects (Spec §2)
# ===========================================================================

@dataclass
class FeatureSpace:
    """Spec §2 FeatureSpace"""
    feature_id: str
    name: str
    domain: str
    values: list[str]


@dataclass
class ExperimentVariant:
    """Spec §2 ExperimentVariant"""
    variant_id: str
    experiment_id: str
    features: dict[str, str] = field(default_factory=dict)
    weight: float = 1.0
    creative_id: str = ""
    ad_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Experiment:
    """Spec §2 Experiment"""
    experiment_id: str
    project: str
    type: str  # CREATIVE | AUDIENCE | STRUCTURAL
    status: str  # RUNNING | STOPPED | WON | LOST
    variants: list[ExperimentVariant] = field(default_factory=list)
    hypothesis: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ===========================================================================
# Engine (Spec §3-§6)
# ===========================================================================

class ExperimentEngine:
    """实验控制引擎 — Spec §13 Final Architecture

    FinalBandit 接入 (Spec §13.9):
        Facebook API → Observation → Reward → FinalBandit Update(theta,sigma)
        → Policy(theta DESC) → Sampling → Facebook
    """

    # FinalBandit memory 路径
    FINAL_BANDIT_MEMORY = "memory/final_bandit.json"

    # v2 Reward Shaping (Spec §9) — reward 计算层, 非算法层
    REWARD_WEIGHT_CTR = 0.6
    REWARD_WEIGHT_ROAS = 0.4
    SAMPLE_GATE_IMPRESSIONS = 500

    # 三张表 (Spec §4: 不允许新增数据表)
    T_EXPERIMENT = "experiment"
    T_VARIANT = "variant"
    T_METRICS = "metrics"

    def __init__(
        self,
        feature_spaces: dict[str, FeatureSpace] | None = None,
        bandit_memory_path: str | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        self._features = feature_spaces or self._default_features()
        self._bandit_memory_path = bandit_memory_path or str(_ROOT / self.FINAL_BANDIT_MEMORY)
        self._db_path = db_path or (_ROOT / "db" / "facebook_performance.duckdb")
        self._final_bandit = None
        self._conn = None
        # Patch-3 (Spec §8.3): in-process 去重 cache,防 backfill 重复学习
        self._seen_updates: set[str] = set()
        self._ensure_db_schema()

    @staticmethod
    def _default_features() -> dict[str, FeatureSpace]:
        """默认 FeatureSpace — creative domain (Spec §4: 固定枚举值)"""
        return {
            "hook_type": FeatureSpace("hook_type", "Hook Type", "creative",
                ["mystery", "progress", "collection", "crisis", "curiosity"]),
            "layout": FeatureSpace("layout", "Layout", "creative",
                ["left_right", "center", "top_bottom"]),
            "color_tone": FeatureSpace("color_tone", "Color Tone", "creative",
                ["warm", "neutral", "cool"]),
            "subject": FeatureSpace("subject", "Subject", "creative",
                ["witch_character", "creature", "merge_board", "scene"]),
            "game_element": FeatureSpace("game_element", "Game Element", "creative",
                ["merge", "progress", "collection", "reward"]),
        }

    # ----- Schema (Spec §4: 只允许 experiment/variant/metrics 三表) -----

    def _ensure_db_schema(self) -> None:
        import duckdb
        conn = duckdb.connect(str(self._db_path), read_only=False)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.T_EXPERIMENT} (
                experiment_id VARCHAR PRIMARY KEY,
                project VARCHAR,
                type VARCHAR,
                status VARCHAR,
                hypothesis VARCHAR,
                created_at VARCHAR
            );
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.T_VARIANT} (
                variant_id VARCHAR PRIMARY KEY,
                experiment_id VARCHAR,
                features VARCHAR,
                weight DOUBLE,
                creative_id VARCHAR,
                ad_id VARCHAR
            );
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.T_METRICS} (
                variant_id VARCHAR,
                experiment_id VARCHAR,
                backfilled_date VARCHAR DEFAULT '',
                spend DOUBLE,
                impressions INTEGER,
                clicks INTEGER,
                installs INTEGER,
                ctr DOUBLE,
                cpi DOUBLE,
                roas_d7 DOUBLE,
                is_win BOOLEAN,
                backfilled_at VARCHAR,
                PRIMARY KEY (variant_id, backfilled_date)
            );
        """)
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_var_exp ON {self.T_VARIANT}(experiment_id);")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_var_creative ON {self.T_VARIANT}(creative_id);")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_met_exp ON {self.T_METRICS}(experiment_id);")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_met_date ON {self.T_METRICS}(backfilled_date);")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_exp_status ON {self.T_EXPERIMENT}(status);")
        conn.close()

    def _get_conn(self):
        if self._conn is None:
            import duckdb
            self._conn = duckdb.connect(str(self._db_path), read_only=False)
        return self._conn

    # ----- FinalBandit 接入 (Spec §13 — 唯一 Bandit) -----

    def _get_final_bandit(self):
        """Lazy-load FinalBandit (Spec §13 封版)

        双存储: JSON (memory_path) + DuckDB (db_backup_path)
        优先从 DB 恢复, JSON 作为 fallback。
        """
        if self._final_bandit is None:
            try:
                from market_ops.creative_intelligence.final_bandit import FinalBandit
                self._final_bandit = FinalBandit(
                    memory_path=self._bandit_memory_path,
                    db_backup_path=self._db_path,
                )
            except Exception as e:
                print(f"[Engine] FinalBandit 加载失败: {e}")
                self._final_bandit = None
        return self._final_bandit

    def _bandit_select(self, gene_type: str, rng: random.Random) -> str:
        """Spec §13.5: FinalBandit.sample(gene_type) — Softmax(theta/tau + gamma*sigma)

        Exploration 从 sigma (uncertainty) 自然涌现, 不进 ranking。
        """
        bandit = self._get_final_bandit()
        if bandit:
            try:
                return bandit.sample(gene_type)
            except Exception:
                pass
        return "unknown"

    def _bandit_select_features(self, rng: random.Random) -> dict[str, str]:
        """逐 feature 用 FinalBandit.sample() 选择, 组装 variant。

        返回值必须在 FeatureSpace.values 内, 否则回退随机 (Spec §4 硬约束)。
        """
        features: dict[str, str] = {}
        bandit = self._get_final_bandit()
        for fid, fs in self._features.items():
            val = None
            if bandit:
                try:
                    val = bandit.sample(fid)
                except Exception:
                    pass
            if not val or val not in fs.values:
                val = rng.choice(fs.values)
            features[fid] = val
        return features

    def _update_final_bandit(self, variant: ExperimentVariant, reward: float) -> None:
        """[DEPRECATED] 使用 _update_final_bandit_dedup 替代"""
        self._update_final_bandit_dedup(
            variant, reward, datetime.now().strftime("%Y-%m-%d"),
        )

    def _update_final_bandit_dedup(
        self, variant: ExperimentVariant, reward: float, backfill_date: str,
    ) -> bool:
        """Spec §13.2: FinalBandit.update(gene_type, gene_value, reward)

        双层去重:
        - 内存层: in-process _seen_updates (同进程防 cron 重复)
        - 持久层: FinalBandit 内存中检查 (gene_type, gene_value, date) 是否已学

        Returns: True 表示新学习, False 表示去重跳过
        """
        dedup_key = f"final:{variant.experiment_id}:{variant.variant_id}:{backfill_date}"
        if dedup_key in self._seen_updates:
            return False
        self._seen_updates.add(dedup_key)

        bandit = self._get_final_bandit()
        if not bandit:
            return False

        learned = False
        try:
            for fname, fval in variant.features.items():
                # FinalBandit 持久层去重: 检查是否同一 date 已学过
                if not bandit.has_learned_on_date(fname, fval, backfill_date):
                    bandit.update(fname, fval, reward)
                    bandit.mark_learned_on_date(fname, fval, backfill_date)
                    learned = True
        except Exception:
            pass
        return learned

    # ----- Generate (Spec §3 step 1, Spec §13.5 sampling) -----

    def generate_experiments(
        self,
        project: str = "P04",
        count: int = 4,
        seed: int | None = None,
        exp_type: str = "CREATIVE",
    ) -> list[Experiment]:
        """生成 A/B 实验。Spec §13.5: FinalBandit.sample() 选择 variant。

        - Variant A: FinalBandit.sample() 选择 (Spec §13.5)
        - Variant B: 在 A 基础上扰动 1-2 个 feature
        """
        rng = random.Random(seed) if seed is not None else random
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        experiments: list[Experiment] = []

        for i in range(count):
            exp_id = f"exp_{timestamp}_{i:03d}"

            # Variant A: FinalBandit sample
            features_a = self._bandit_select_features(rng)
            variant_a = ExperimentVariant(
                variant_id=f"{exp_id}_A",
                experiment_id=exp_id,
                features=features_a,
                weight=1.0,
            )

            # Variant B: perturb 1-2 features
            features_b = dict(features_a)
            feature_ids = list(self._features.keys())
            n_change = min(2, len(feature_ids))
            vars_to_change = rng.sample(feature_ids, k=n_change)
            for fid in vars_to_change:
                fs = self._features[fid]
                options = [v for v in fs.values if v != features_b[fid]]
                if options:
                    features_b[fid] = rng.choice(options)
            variant_b = ExperimentVariant(
                variant_id=f"{exp_id}_B",
                experiment_id=exp_id,
                features=features_b,
                weight=1.0,
            )

            hypothesis = self._build_hypothesis(features_a, features_b, vars_to_change)

            exp = Experiment(
                experiment_id=exp_id,
                project=project,
                type=exp_type,
                status="RUNNING",
                variants=[variant_a, variant_b],
                hypothesis=hypothesis,
                created_at=datetime.now().isoformat(),
            )
            experiments.append(exp)

        return experiments

    def _build_hypothesis(
        self,
        fa: dict[str, str],
        fb: dict[str, str],
        changed: list[str],
    ) -> str:
        if not changed:
            return "无变量差异(对照组)"
        parts = [f"{v}: {fa[v]} vs {fb[v]}" for v in changed]
        if "layout" in changed and (
            fa.get("layout") == "left_right" or fb.get("layout") == "left_right"
        ):
            return f"假设: left_right布局CTR更高 (测试: {', '.join(parts)})"
        if "color_tone" in changed and "cool" in (
            fa.get("color_tone"), fb.get("color_tone")
        ):
            return f"假设: cool色调CTR更低 (测试: {', '.join(parts)})"
        return f"假设: 测试 {', '.join(parts)} 对CTR的影响"

    # ----- Log (Spec §6 唯一写路径) -----

    def log_experiment(self, experiment: Experiment) -> None:
        """Spec §6: 所有 experiment 写入必须通过 log_experiment()。

        写入 experiment + variant 两张表 (INSERT OR REPLACE)。
        """
        conn = self._get_conn()
        conn.execute(
            f"""INSERT OR REPLACE INTO {self.T_EXPERIMENT}
                (experiment_id, project, type, status, hypothesis, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
            [experiment.experiment_id, experiment.project, experiment.type,
             experiment.status, experiment.hypothesis, experiment.created_at],
        )
        for v in experiment.variants:
            conn.execute(
                f"""INSERT OR REPLACE INTO {self.T_VARIANT}
                    (variant_id, experiment_id, features, weight, creative_id, ad_id)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                [v.variant_id, v.experiment_id, json.dumps(v.features, ensure_ascii=False),
                 v.weight, v.creative_id, v.ad_id],
            )
        conn.commit()

    # ----- Backfill (Spec §6 唯一 performance 写路径) -----

    def backfill_results(self, experiment_id: str | None = None) -> dict[str, Any]:
        """Spec §6: 所有 performance 写入必须通过 backfill_results()。
        Spec §13.2: FinalBandit.update() 唯一学习路径。

        读 creative_performance → rolling SUM → compute_reward_v2
        → 写 metrics 表 (PRIMARY KEY: variant_id + backfilled_date)
        → FinalBandit.update(gene_type, gene_value, reward)

        去重: DB 层 UNIQUE(variant_id, backfilled_date) + in-process cache。
        """
        conn = self._get_conn()
        today = datetime.now().strftime("%Y-%m-%d")

        if experiment_id:
            experiments = conn.execute(
                f"SELECT experiment_id, project FROM {self.T_EXPERIMENT} WHERE experiment_id = ?",
                [experiment_id],
            ).fetchall()
        else:
            experiments = conn.execute(
                f"SELECT experiment_id, project FROM {self.T_EXPERIMENT} WHERE status = 'RUNNING'"
            ).fetchall()

        if not experiments:
            return {"backfilled": 0, "won": 0, "lost": 0}

        updated = 0
        won = 0
        skipped = 0
        attribution_warnings: list[str] = []
        for exp_id, project in experiments:
            baseline_ctr, baseline_roas = self._get_baseline(project)

            variants = conn.execute(
                f"SELECT variant_id, features, creative_id FROM {self.T_VARIANT} WHERE experiment_id = ?",
                [exp_id],
            ).fetchall()

            # Creative Attribution 检测: 同一 creative 在同一 experiment 中不应被多个 variant 引用
            creative_variant_map: dict[str, list[str]] = {}
            for vid, _, cid in variants:
                if cid:
                    creative_variant_map.setdefault(cid, []).append(vid)
            dup_creatives = {c: vs for c, vs in creative_variant_map.items() if len(vs) > 1}
            if dup_creatives:
                for cid, vids in dup_creatives.items():
                    msg = f"[Attribution] creative={cid} 被 {len(vids)} 个 variants 引用: {vids}"
                    attribution_warnings.append(msg)
                    print(f"  ⚠️  {msg}")

            variant_rewards: list[tuple[str, float, float]] = []
            for vid, features_json, creative_id in variants:
                if not creative_id:
                    continue
                perf = conn.execute(
                    """SELECT
                        COALESCE(SUM(impression), 0),
                        COALESCE(SUM(click), 0),
                        COALESCE(SUM(spend), 0),
                        COALESCE(SUM(install), 0),
                        COALESCE(SUM(roas_d7 * spend) / NULLIF(SUM(spend), 0), 0)
                    FROM creative_performance
                    WHERE creative_id = ?
                      AND CAST(date AS DATE) >= CURRENT_DATE - 7""",
                    [creative_id],
                ).fetchall()
                if not perf:
                    continue

                impressions, clicks, spend, installs, roas_d7 = perf[0]
                if impressions == 0:
                    continue

                ctr = clicks / impressions * 100 if impressions > 0 else 0
                cpi = spend / installs if installs > 0 else 0
                reward = self._compute_reward_v2(
                    ctr, roas_d7, impressions, baseline_ctr, baseline_roas,
                )
                is_win = reward > 0.5

                # DB 层去重: INSERT OR REPLACE 按 (variant_id, backfilled_date)
                conn.execute(
                    f"""INSERT OR REPLACE INTO {self.T_METRICS}
                        (variant_id, experiment_id, backfilled_date,
                         spend, impressions, clicks, installs,
                         ctr, cpi, roas_d7, is_win, backfilled_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [vid, exp_id, today,
                     spend, impressions, clicks, installs,
                     ctr, cpi, roas_d7, is_win, datetime.now().isoformat()],
                )
                updated += 1
                if is_win:
                    won += 1
                variant_rewards.append((vid, reward, roas_d7))

                # Spec §13.2: FinalBandit.update() — 唯一学习路径
                # 去重: 同 variant 同天只学一次 (in-process + DB 双层)
                variant = ExperimentVariant(
                    variant_id=vid, experiment_id=exp_id,
                    features=json.loads(features_json),
                )
                if self._update_final_bandit_dedup(variant, reward, today):
                    pass  # 新学习
                else:
                    skipped += 1  # 去重跳过

            # 更新 experiment status
            if variant_rewards:
                best_vid, best_reward, _ = max(variant_rewards, key=lambda x: x[1])
                if best_reward > 0.5:
                    status = "WON"
                elif best_reward < 0.3:
                    status = "LOST"
                else:
                    status = "RUNNING"
                conn.execute(
                    f"UPDATE {self.T_EXPERIMENT} SET status = ? WHERE experiment_id = ?",
                    [status, exp_id],
                )

        conn.commit()
        result = {"backfilled": updated, "won": won, "lost": updated - won,
                   "skipped_dedup": skipped}
        if attribution_warnings:
            result["attribution_warnings"] = attribution_warnings
        return result

    # ----- v2 Reward Shaping (Spec §9) -----

    @staticmethod
    def _sigmoid(x: float) -> float:
        """固定 sigmoid (Spec §9.1): x/(1+|x|), 比 exp 稳定"""
        return x / (1.0 + abs(x))

    def _get_baseline(self, project: str) -> tuple[float, float]:
        """Spec §9.1 Step 1: project-level rolling 7 天 baseline

        Returns: (baseline_ctr, baseline_roas)
        """
        conn = self._get_conn()
        row = conn.execute(
            """SELECT
                COALESCE(MEDIAN(ctr), 1.0),
                COALESCE(MEDIAN(roas_d7), 0.3)
            FROM creative_performance
            WHERE project = ?
              AND CAST(date AS DATE) >= CURRENT_DATE - 7
              AND impression > 0""",
            [project],
        ).fetchone()
        return (float(row[0]), float(row[1]))

    def _compute_reward_v2(
        self,
        ctr: float,
        roas_d7: float,
        impressions: int,
        baseline_ctr: float,
        baseline_roas: float,
    ) -> float:
        """[DEPRECATED] 旧 reward — 已被 IAP Observation Layer 替代

        保留用于兼容。新代码应使用 _compute_quality_score()。
        """
        if impressions < self.SAMPLE_GATE_IMPRESSIONS:
            return 0.5
        ctr_norm = (ctr - baseline_ctr) / (baseline_ctr + 1e-6)
        roas_norm = (roas_d7 - baseline_roas) / (baseline_roas + 1e-6)
        reward = (
            self.REWARD_WEIGHT_CTR * self._sigmoid(ctr_norm) +
            self.REWARD_WEIGHT_ROAS * self._sigmoid(roas_norm)
        )
        return reward

    # ----- IAP Observation Layer (内购产品) -----

    def _compute_quality_score(
        self,
        creative_id: str,
        ctr: float,
        roas_d7: float,
        impressions: int,
        clicks: int,
        installs: int,
        spend: float,
        date: str = "",
    ) -> float:
        """IAP Quality Score → FinalBandit

        通过 QualityScoreBuilder 将原始指标转为 0~1 quality_score。
        FinalBandit 只接收 quality_score, 不知道 CTR/ROAS/Purchase。

        流程: raw metrics → CreativeObservation → QualityScoreBuilder → quality_score → FinalBandit
        """
        from market_ops.creative_intelligence.iap_observation import (
            CreativeObservation,
            QualityScoreBuilder,
        )

        obs = CreativeObservation(
            creative_id=creative_id,
            date=date or datetime.now().strftime("%Y-%m-%d"),
            impression=impressions,
            click=clicks,
            ctr=ctr,
            install=installs,
            spend=spend,
            roas_d7=roas_d7,
        )
        obs.cvr = installs / max(clicks, 1)
        obs.cpi = spend / max(installs, 1)
        obs.ipm = installs / max(impressions, 1) * 1000

        builder = QualityScoreBuilder()
        qs = builder.build(obs)

        if not qs.sufficient_data:
            return -1.0  # 标记: 不进入 Bandit

        return qs.score

    # ----- Publish (Spec §3 step 3) -----

    def publish_experiments(
        self,
        experiments: list[Experiment],
        adset_id: str,
        image_dir_map: dict[str, str] | None = None,
        access_token: str = "",
        ad_account_id: str = "",
    ) -> dict[str, Any]:
        """Spec §5: FacebookPublisher.publish(experiment)"""
        if not adset_id:
            return {"error": "adset_id required"}

        try:
            pub_mod = importlib.import_module(
                "market_ops.creative_growth_loop.14_publish.facebook_publisher"
            )
        except Exception as e:
            return {"error": f"Publisher加载失败: {e}"}

        token = access_token or os.environ.get("META_ACCESS_TOKEN", "")
        account = ad_account_id or os.environ.get("META_AD_ACCOUNT_ID", "")
        if not token or not account:
            return {"error": "需要 META_ACCESS_TOKEN 和 META_AD_ACCOUNT_ID"}

        publisher = pub_mod.FacebookPublisher(access_token=token, ad_account_id=account)
        results = []
        for exp in experiments:
            img_dir = (image_dir_map or {}).get(exp.experiment_id, "")
            if not img_dir:
                continue
            try:
                result = publisher.publish_and_monitor(
                    image_dir=img_dir,
                    campaign_config={
                        "adset_id": adset_id,
                        "ad_names": [v.variant_id for v in exp.variants],
                        "auto_activate": False,
                    },
                )
                ad_ids = result.ad_ids
                for i, v in enumerate(exp.variants):
                    if i < len(ad_ids):
                        v.ad_id = ad_ids[i]
                self.log_experiment(exp)
                results.append({"experiment_id": exp.experiment_id,
                                "status": "published", "ad_ids": ad_ids})
            except Exception as e:
                results.append({"experiment_id": exp.experiment_id,
                                "status": "failed", "error": str(e)})

        return {"published": len([r for r in results if r["status"] == "published"]),
                "results": results}

    # ----- Query (只读) -----

    def query_experiments(
        self,
        status: str | None = None,
        project: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        sql = f"SELECT * FROM {self.T_EXPERIMENT} WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if project:
            sql += " AND project = ?"
            params.append(project)
        sql += f" LIMIT {limit}"
        rows = conn.execute(sql, params).fetchall()
        cols = [d[0] for d in conn.description]
        return [dict(zip(cols, r)) for r in rows]

    def query_variants(self, experiment_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            f"SELECT * FROM {self.T_VARIANT} WHERE experiment_id = ?",
            [experiment_id],
        ).fetchall()
        cols = [d[0] for d in conn.description]
        return [dict(zip(cols, r)) for r in rows]

    def query_metrics(self, experiment_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            f"SELECT * FROM {self.T_METRICS} WHERE experiment_id = ?",
            [experiment_id],
        ).fetchall()
        cols = [d[0] for d in conn.description]
        return [dict(zip(cols, r)) for r in rows]

    def get_summary(self) -> dict[str, Any]:
        conn = self._get_conn()
        total = conn.execute(f"SELECT COUNT(*) FROM {self.T_EXPERIMENT}").fetchone()[0]
        by_status = conn.execute(
            f"SELECT status, COUNT(*) FROM {self.T_EXPERIMENT} GROUP BY status"
        ).fetchall()
        by_type = conn.execute(
            f"SELECT type, COUNT(*) FROM {self.T_EXPERIMENT} GROUP BY type"
        ).fetchall()
        won = conn.execute(
            f"SELECT COUNT(*) FROM {self.T_EXPERIMENT} WHERE status = 'WON'"
        ).fetchone()[0]
        return {
            "total": total,
            "by_status": dict(by_status),
            "by_type": dict(by_type),
            "won": won,
        }

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
