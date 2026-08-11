"""E9.6: Creative → Archetype Matching Engine — Orchestrator + Ranking + Export.

Full pipeline:
  1. Load creative DNA from master JSON
  2. Load historical archetype profiles from E9.5
  3. Encode DNA → feature vectors
  4. Predict archetype distribution per creative
  5. Compute LTV / D30 / payer_rate predictions
  6. Rank creatives by archetype affinity
  7. Export creative_prediction.json + creative_archetype_rank.json

Usage:
    engine = MatchingEngine()
    result = engine.run()
    # or step by step:
    engine.load_creative_dna()
    engine.load_historical_profiles()
    engine.encode_features()
    engine.predict_all()
    engine.rank_and_export()
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from market_ops.creative_matching.schemas import (
    DNAFeatureVector, CreativePrediction, CreativeArchetypeRank,
)
from market_ops.creative_matching.dna_feature_encoder import DNAFeatureEncoder
from market_ops.creative_matching.creative_archetype_profile import CreativeArchetypeProfileDB
from market_ops.creative_matching.archetype_predictor import ArchetypePredictor


# ═══════════════════════════════════════════════════════════
# Matching Engine
# ═══════════════════════════════════════════════════════════

class MatchingEngine:
    """Orchestrates the full Creative → Archetype matching pipeline.

    Usage:
        engine = MatchingEngine()
        engine.load_creative_dna()
        engine.load_historical_profiles()
        engine.encode_features()
        engine.predict_all()
        paths = engine.export_all()
        summary = engine.get_summary()
    """

    def __init__(self) -> None:
        # Inputs
        self._creative_dna_list: list[dict[str, Any]] = []
        self._creative_dna_map: dict[str, dict[str, Any]] = {}

        # Components
        self._profile_db = CreativeArchetypeProfileDB()
        self._encoder = DNAFeatureEncoder()
        self._predictor: ArchetypePredictor | None = None

        # Outputs
        self._features: dict[str, DNAFeatureVector] = {}
        self._predictions: dict[str, CreativePrediction] = {}
        self._rankings: list[CreativeArchetypeRank] = []

        # Paths
        self._dna_master_path = Path("output/active/creative_dna_master.json")
        self._output_dir = Path("output/creative_matching")

    # ── Loading ────────────────────────────────────────────

    def load_creative_dna(self, path: str | Path | None = None) -> int:
        """Load creative DNA from master JSON.

        Returns: number of creative DNA records loaded.
        """
        p = Path(path) if path else self._dna_master_path
        if not p.exists():
            return 0

        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self._creative_dna_list = data if isinstance(data, list) else []
        self._creative_dna_map = {}
        for item in self._creative_dna_list:
            cid = item.get("creative_id", "")
            if cid:
                self._creative_dna_map[cid] = item

        return len(self._creative_dna_list)

    def load_historical_profiles(self, path: str | Path | None = None) -> int:
        """Load historical archetype profiles from E9.5 output.

        Returns: number of profile entries loaded.
        """
        return self._profile_db.load(path)

    # ── Processing ─────────────────────────────────────────

    def encode_features(self) -> dict[str, DNAFeatureVector]:
        """Encode all creative DNA into feature vectors."""
        self._features = self._encoder.encode_all(self._creative_dna_list)
        return self._features

    def predict_all(self) -> dict[str, CreativePrediction]:
        """Predict archetype distribution for all creatives."""
        if not self._features:
            self.encode_features()

        self._predictor = ArchetypePredictor(self._profile_db)
        self._predictions = self._predictor.predict_all(self._features)
        return self._predictions

    # ── Ranking ────────────────────────────────────────────

    def rank_by_archetype(
        self,
        target_archetype: str,
        top_n: int = 20,
    ) -> list[CreativeArchetypeRank]:
        """Rank creatives by affinity to a target archetype.

        Rank score = probability × IAP_potential
        """
        rankings = []
        for cid, pred in self._predictions.items():
            if target_archetype not in pred.archetypes:
                continue
            affinity = pred.archetypes[target_archetype]
            rank_score = (
                affinity.adjusted_probability * 0.6
                + pred.expected_iap_potential * 0.4
            )
            rankings.append(CreativeArchetypeRank(
                creative_id=cid,
                creative_genome_name=pred.creative_genome_name,
                target_archetype=target_archetype,
                probability=affinity.adjusted_probability,
                expected_ltv=pred.expected_ltv,
                expected_payer_rate=pred.expected_payer_rate,
                expected_retention=pred.expected_d30_retention,
                iap_potential=pred.expected_iap_potential,
                rank_score=round(rank_score, 4),
            ))

        rankings.sort(key=lambda r: -r.rank_score)
        return rankings[:top_n]

    def rank_all_archetypes(self, top_n: int = 20) -> dict[str, list[CreativeArchetypeRank]]:
        """Rank creatives for all 5 archetypes."""
        result = {}
        for arch in ["power", "collector", "explorer", "progression"]:
            result[arch] = self.rank_by_archetype(arch, top_n)
        return result

    def rank_by_ltv(self, top_n: int = 20) -> list[CreativeArchetypeRank]:
        """Rank creatives by expected LTV."""
        rankings = []
        for cid, pred in self._predictions.items():
            rankings.append(CreativeArchetypeRank(
                creative_id=cid,
                creative_genome_name=pred.creative_genome_name,
                target_archetype=pred.primary_archetype,
                probability=pred.primary_confidence,
                expected_ltv=pred.expected_ltv,
                expected_payer_rate=pred.expected_payer_rate,
                expected_retention=pred.expected_d30_retention,
                iap_potential=pred.expected_iap_potential,
                rank_score=pred.expected_ltv,
            ))
        rankings.sort(key=lambda r: -r.rank_score)
        return rankings[:top_n]

    def rank_by_iap(self, top_n: int = 20) -> list[CreativeArchetypeRank]:
        """Rank creatives by IAP potential."""
        rankings = []
        for cid, pred in self._predictions.items():
            rankings.append(CreativeArchetypeRank(
                creative_id=cid,
                creative_genome_name=pred.creative_genome_name,
                target_archetype=pred.primary_archetype,
                probability=pred.primary_confidence,
                expected_ltv=pred.expected_ltv,
                expected_payer_rate=pred.expected_payer_rate,
                expected_retention=pred.expected_d30_retention,
                iap_potential=pred.expected_iap_potential,
                rank_score=pred.expected_iap_potential,
            ))
        rankings.sort(key=lambda r: -r.rank_score)
        return rankings[:top_n]

    # ── Export ─────────────────────────────────────────────

    def export_predictions(
        self, output_dir: str | Path | None = None,
    ) -> str:
        """Export creative_prediction.json."""
        p = Path(output_dir) if output_dir else self._output_dir
        p.mkdir(parents=True, exist_ok=True)

        out_file = p / "creative_prediction.json"
        data = [
            pred.to_dict()
            for pred in sorted(
                self._predictions.values(),
                key=lambda x: -x.expected_iap_potential,
            )
        ]
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(out_file)

    def export_rankings(
        self, output_dir: str | Path | None = None,
    ) -> str:
        """Export creative_archetype_rank.json."""
        p = Path(output_dir) if output_dir else self._output_dir
        p.mkdir(parents=True, exist_ok=True)

        out_file = p / "creative_archetype_rank.json"
        all_ranks = self.rank_all_archetypes()
        ltv_ranks = self.rank_by_ltv()
        iap_ranks = self.rank_by_iap()

        data = {
            "top_power_creatives": [r.to_dict() for r in all_ranks.get("power", [])],
            "top_collector_creatives": [r.to_dict() for r in all_ranks.get("collector", [])],
            "top_explorer_creatives": [r.to_dict() for r in all_ranks.get("explorer", [])],
            "top_progression_creatives": [r.to_dict() for r in all_ranks.get("progression", [])],
            "top_ltv_creatives": [r.to_dict() for r in ltv_ranks],
            "top_iap_creatives": [r.to_dict() for r in iap_ranks],
        }
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(out_file)

    def export_all(self, output_dir: str | Path | None = None) -> dict[str, str]:
        """Export all output files."""
        return {
            "creative_prediction": self.export_predictions(output_dir),
            "creative_archetype_rank": self.export_rankings(output_dir),
        }

    # ── Summary ────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        """Get matching engine summary."""
        if not self._predictions:
            return {"status": "no_predictions"}

        n = len(self._predictions)

        # Average expected metrics
        avg_ltv = sum(p.expected_ltv for p in self._predictions.values()) / n
        avg_payer = sum(p.expected_payer_rate for p in self._predictions.values()) / n
        avg_ret = sum(p.expected_d30_retention for p in self._predictions.values()) / n
        avg_iap = sum(p.expected_iap_potential for p in self._predictions.values()) / n

        # Primary archetype distribution
        primary_counts: dict[str, int] = defaultdict(int)
        for p in self._predictions.values():
            primary_counts[p.primary_archetype] += 1

        # Top predictions
        top_ltv = sorted(
            self._predictions.values(),
            key=lambda p: -p.expected_ltv,
        )[:5]
        top_iap = sorted(
            self._predictions.values(),
            key=lambda p: -p.expected_iap_potential,
        )[:5]

        return {
            "total_creatives": n,
            "avg_expected_ltv": round(avg_ltv, 2),
            "avg_expected_payer_rate": round(avg_payer, 3),
            "avg_expected_d30_retention": round(avg_ret, 3),
            "avg_iap_potential": round(avg_iap, 3),
            "primary_archetype_distribution": dict(primary_counts),
            "top_ltv_creatives": [
                {
                    "creative_id": p.creative_id,
                    "genome": p.creative_genome_name,
                    "primary_archetype": p.primary_archetype,
                    "expected_ltv": round(p.expected_ltv, 2),
                    "expected_payer_rate": round(p.expected_payer_rate, 3),
                }
                for p in top_ltv
            ],
            "top_iap_creatives": [
                {
                    "creative_id": p.creative_id,
                    "genome": p.creative_genome_name,
                    "primary_archetype": p.primary_archetype,
                    "iap_potential": round(p.expected_iap_potential, 3),
                    "expected_ltv": round(p.expected_ltv, 2),
                }
                for p in top_iap
            ],
            "profile_db": self._profile_db.get_summary(),
        }

    # ── Full Pipeline ──────────────────────────────────────

    def run(self, output_dir: str | Path | None = None) -> dict[str, Any]:
        """Run the complete matching pipeline.

        Returns: full pipeline report.
        """
        n_dna = self.load_creative_dna()
        n_profiles = self.load_historical_profiles()

        if n_dna == 0:
            return {"status": "error", "message": "No creative DNA data loaded"}

        self.encode_features()
        self.predict_all()

        export_paths = self.export_all(output_dir)

        return {
            "summary": self.get_summary(),
            "export_paths": export_paths,
            "data_loaded": {
                "creative_dna": n_dna,
                "historical_profiles": n_profiles,
            },
        }


# ═══════════════════════════════════════════════════════════
# Convenience function
# ═══════════════════════════════════════════════════════════

def run_e96_pipeline(
    dna_path: str | Path | None = None,
    profiles_path: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the complete E9.6 pipeline."""
    engine = MatchingEngine()

    if dna_path:
        engine._dna_master_path = Path(dna_path)

    return engine.run(output_dir)