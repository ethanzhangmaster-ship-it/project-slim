"""E13.5 — Listing Experiment Agent (true ASO: listing A/B test).

The ASO surface of the Play Runtime. It proposes and creates store-listing
A/B experiments through the ``PlayConnector`` (inheriting the three-tier
gate — READ never writes, PRODUCTION real create needs auto-pilot + apply),
and monitors running experiments to recommend a winning variant.

Why this is the right ASO primitive: Google Play exposes store-listing
experiments via ``edits.experiments`` (a real, writable androidpublisher v3
endpoint). An experiment compares the CURRENT live listing against one
challenger (a modified title / short / full description for a locale) and
routes a configurable user fraction to each. The live listing is untouched
until you later promote a winner — so creating an experiment is the lowest-
blast-radius, reversible ASO write. This is far more grounded than guessing
listing copy; it *measures* which copy converts.

Lean rule: pure Python, deterministic validation + recommendation, JSONL
audit, no LLM.

Recommendation logic (deterministic):
  * A running experiment stays ``running``.
  * An ended experiment with per-variant conversion results: if the variant
    (challenger) conversion >= the baseline, recommend ``promote_variant``;
    otherwise ``keep_baseline``. Without results we stay ``ended`` (no rec).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.experiment_audit import (
    append as experiment_append,
)
from operation.publishing_factory.play_runtime.experiment_audit import (
    active_experiments as audit_active,
)


# Play store-listing title cap (en/most locales). Local defensive guard.
_TITLE_MAX_CHARS = 50


@dataclass
class ExperimentPolicy:
    """Tunable experiment rules (deterministic, no LLM)."""
    default_user_fraction: float = 0.1   # 10% of users in the test
    title_max_chars: int = _TITLE_MAX_CHARS
    name_max_chars: int = 80
    # Minimum conversion lift (fraction) before we recommend promoting a
    # challenger over the baseline. 0.0 = any non-negative lift wins.
    min_lift_to_promote: float = 0.0


@dataclass
class ListingExperimentProposal:
    """One experiment proposal / state record (persisted to the audit)."""
    package_name: str
    name: str
    locale: str = "en-US"
    variant_title: Optional[str] = None
    variant_short: Optional[str] = None
    variant_full: Optional[str] = None
    baseline_title: Optional[str] = None
    user_fraction: float = 0.1
    status: str = "proposed"        # proposed/created/running/ended/winner
    experiment_id: Optional[str] = None
    recommendation: str = ""        # promote_variant/keep_baseline/""
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_name": self.package_name,
            "name": self.name,
            "locale": self.locale,
            "variant_title": self.variant_title,
            "variant_short": self.variant_short,
            "variant_full": self.variant_full,
            "baseline_title": self.baseline_title,
            "user_fraction": self.user_fraction,
            "status": self.status,
            "experiment_id": self.experiment_id,
            "recommendation": self.recommendation,
            "recorded_at": self.recorded_at,
        }


class ListingExperimentAgent:
    """ASO via controlled store-listing A/B experiments over a
    PlayConnector.
    """

    def __init__(self, connector: PlayConnector,
                 policy: Optional[ExperimentPolicy] = None):
        self.connector = connector
        self.policy = policy or ExperimentPolicy()

    # ------------------------------------------------------------------ #
    # validation + spec build (pure)
    def build_proposal(self, package_name: str, *, name: str, locale: str,
                       variant_title: Optional[str] = None,
                       variant_short: Optional[str] = None,
                       variant_full: Optional[str] = None,
                       baseline_title: Optional[str] = None,
                       user_fraction: Optional[float] = None) \
            -> ListingExperimentProposal:
        """Validate inputs and produce a proposal record (no write)."""
        uf = user_fraction if user_fraction is not None \
            else self.policy.default_user_fraction
        if not package_name:
            raise ValueError("package_name required")
        if not name or not name.strip():
            raise ValueError("experiment name required")
        if len(name) > self.policy.name_max_chars:
            raise ValueError(
                f"name too long ({len(name)} > "
                f"{self.policy.name_max_chars})")
        if variant_title is not None:
            if not variant_title.strip():
                raise ValueError("variant_title must be non-empty")
            if len(variant_title) > self.policy.title_max_chars:
                raise ValueError(
                    f"variant_title too long ({len(variant_title)} > "
                    f"{self.policy.title_max_chars})")
        return ListingExperimentProposal(
            package_name=package_name, name=name, locale=locale,
            variant_title=variant_title, variant_short=variant_short,
            variant_full=variant_full, baseline_title=baseline_title,
            user_fraction=uf, status="proposed")

    # ------------------------------------------------------------------ #
    # propose / create (gated write)
    def propose(self, package_name: str, *, name: str, locale: str = "en-US",
                variant_title: Optional[str] = None,
                variant_short: Optional[str] = None,
                variant_full: Optional[str] = None,
                baseline_title: Optional[str] = None,
                user_fraction: Optional[float] = None,
                apply: bool = False) -> "object":
        """Build a proposal and route it through the connector's three-tier
        gate. With ``apply=False`` (default) it only proposes; with
        ``apply=True`` (and auto-pilot) it creates the real experiment.

        Returns the ``PlayResult`` from the connector.
        """
        self.build_proposal(
            package_name, name=name, locale=locale,
            variant_title=variant_title, variant_short=variant_short,
            variant_full=variant_full, baseline_title=baseline_title,
            user_fraction=user_fraction)  # raises on invalid input
        return self.connector.create_experiment(
            package_name, name=name, locale=locale,
            variant_title=variant_title, variant_short=variant_short,
            variant_full=variant_full, baseline_title=baseline_title,
            user_fraction=(user_fraction
                           if user_fraction is not None
                           else self.policy.default_user_fraction),
            apply=apply)

    def propose_title_test(self, package_name: str, locale: str,
                           new_title: str, *, name: Optional[str] = None,
                           baseline_title: Optional[str] = None,
                           apply: bool = False) -> "object":
        """Convenience ASO helper: test a new store-listing *title* for a
        locale against the current live title. This is the canonical ASO
        action (e.g. test a compliant shortened ``fil``/``ar`` title after a
        'title too long' 403)."""
        nm = name or f"ASO title test {locale} {new_title[:24]}"
        return self.propose(
            package_name, name=nm, locale=locale,
            variant_title=new_title, baseline_title=baseline_title,
            apply=apply)

    # ------------------------------------------------------------------ #
    # read + evaluate (READ radius)
    def read_results(self, package_name: str) -> List[Dict[str, Any]]:
        """READ the experiments for a package (through the connector's READ
        gate). Returns the raw experiment list from Play."""
        res = self.connector.read_experiments(package_name)
        if not res.ok:
            return []
        return (res.data or {}).get("experiments", []) or []

    def _recommend(self, exp: Dict[str, Any]) -> (str, str):
        """Return (status, recommendation) for one raw experiment dict.

        ``status`` is derived from the experiment's ``status`` field
        (RUNNING / ENDED / etc.). ``recommendation`` is only set when the
        experiment has ended AND carries per-variant conversion results.
        """
        raw_status = (exp.get("status") or "UNKNOWN").upper()
        if raw_status == "RUNNING":
            return "running", ""
        if raw_status in ("ENDED", "COMPLETED", "FINISHED"):
            rec = self._pick_winner(exp)
            return "ended", rec
        return raw_status.lower(), ""

    def _pick_winner(self, exp: Dict[str, Any]) -> str:
        """Deterministic winner pick from variant conversion results."""
        variants = exp.get("variants") or []
        base = None
        chal = None
        for v in variants:
            conv = (v.get("results") or {}).get("conversionRate") \
                if isinstance(v.get("results"), dict) else None
            if conv is None:
                conv = v.get("conversionRate")
            if v.get("id") == "default":
                base = conv
            elif v.get("id") == "variant":
                chal = conv
        if base is None or chal is None:
            return ""  # no measurable data yet
        lift = (chal - base) / base if base else 0.0
        if chal >= base and lift >= self.policy.min_lift_to_promote:
            return "promote_variant"
        return "keep_baseline"

    def evaluate(self, package_name: str) -> Dict[str, Any]:
        """READ experiments for a package, classify each, and recommend a
        winner where data exists. Persists a record per experiment to the
        audit log (no write to Play)."""
        exps = self.read_results(package_name)
        records: List[ListingExperimentProposal] = []
        for exp in exps:
            eid = exp.get("experimentId") or exp.get("id")
            name = exp.get("name") or ""
            locale = (exp.get("variants") or [{}])[-1].get(
                "storeListing", {}).get("languageCode") or "en-US"
            status, rec = self._recommend(exp)
            rec_obj = ListingExperimentProposal(
                package_name=package_name, name=name, locale=locale,
                variant_title=(exp.get("variants") or [{}])[-1]
                .get("storeListing", {}).get("title"),
                user_fraction=exp.get("userFraction", 0.1),
                status=status, experiment_id=eid,
                recommendation=rec)
            experiment_append(rec_obj)
            records.append(rec_obj)
        return {
            "package_name": package_name,
            "count": len(records),
            "running": sum(1 for r in records if r.status == "running"),
            "ended": sum(1 for r in records if r.status == "ended"),
            "recommendations": [
                {"experiment_id": r.experiment_id, "name": r.name,
                 "status": r.status, "recommendation": r.recommendation}
                for r in records if r.recommendation],
        }

    def run_daily(self, packages: List[str]) -> Dict[str, Any]:
        """Monitor every package's experiments (READ-only), persist state +
        recommendations to the audit log. Creating an experiment is a
        deliberate, human-triggered action and is NOT auto-fired here — this
        sweep only *observes* and *recommends*.
        """
        per_pkg: Dict[str, Dict[str, int]] = {}
        recs: List[Dict[str, Any]] = []
        for pkg in packages:
            out = self.evaluate(pkg)
            per_pkg[pkg] = {
                "experiments": out["count"],
                "running": out["running"],
                "ended": out["ended"],
                "recommendations": len(out["recommendations"]),
            }
            recs.extend(out["recommendations"])
        return {
            "per_package": per_pkg,
            "recommendations": recs,
            "active": [a for a in audit_active()],
        }


__all__ = ["ListingExperimentAgent", "ExperimentPolicy",
           "ListingExperimentProposal"]
