"""P4.3 product portfolio lifecycle with deterministic promotion gates."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class ProductStage(str, Enum):
    IDEA = "idea"
    PROTOTYPE = "prototype"
    MARKET_TEST = "market_test"
    LIVE = "live"
    RETIRED = "retired"


@dataclass(frozen=True)
class ProductGate:
    max_cpi: float = 1.0
    min_d1_retention: float = 0.25
    min_roas: float = 0.8
    min_installs: int = 100


@dataclass
class ProductAsset:
    product_id: str
    stage: ProductStage = ProductStage.IDEA
    metrics: Dict[str, float] = field(default_factory=dict)
    history: List[str] = field(default_factory=list)
    reason: str = ""


class ProductFactory:
    def __init__(self, gate: ProductGate = ProductGate()): self.gate = gate

    def advance(self, asset: ProductAsset) -> ProductAsset:
        if asset.stage == ProductStage.RETIRED: return asset
        if asset.stage == ProductStage.IDEA:
            return self._move(asset, ProductStage.PROTOTYPE, "idea accepted for prototype")
        if asset.stage == ProductStage.PROTOTYPE:
            if not asset.metrics.get("build_passed", 0):
                return self._move(asset, ProductStage.RETIRED, "prototype build failed")
            return self._move(asset, ProductStage.MARKET_TEST, "prototype build passed")
        if asset.stage == ProductStage.MARKET_TEST:
            m = asset.metrics
            if int(m.get("installs", 0)) < self.gate.min_installs:
                asset.reason = "insufficient market-test sample"; return asset
            passed = (float(m.get("cpi", 999)) <= self.gate.max_cpi and
                      float(m.get("d1_retention", 0)) >= self.gate.min_d1_retention and
                      float(m.get("roas", 0)) >= self.gate.min_roas)
            return self._move(asset, ProductStage.LIVE if passed else ProductStage.RETIRED,
                              "market gates passed" if passed else "market gates failed")
        return asset

    @staticmethod
    def _move(asset, stage, reason):
        asset.history.append(f"{asset.stage.value}->{stage.value}:{reason}")
        asset.stage, asset.reason = stage, reason
        return asset


__all__ = ["ProductStage", "ProductGate", "ProductAsset", "ProductFactory"]
