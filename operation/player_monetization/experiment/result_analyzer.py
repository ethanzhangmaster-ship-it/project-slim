"""E15.2.7 §7 — Experiment result analyzer.
Compares control vs variant group ARPDAU and retention deltas."""
from __future__ import annotations
from typing import Any, Dict, List

class ResultAnalyzer:
    def analyze(self, control: List[Dict[str, Any]],
                variant: List[Dict[str, Any]]) -> Dict[str, Any]:
        def avg(grp, k):
            vs = [r[k] for r in grp if k in r]
            return sum(vs)/len(vs) if vs else 0
        c_arpdau = avg(control, "arpdau")
        v_arpdau = avg(variant, "arpdau")
        c_ret = avg(control, "retention")
        v_ret = avg(variant, "retention")
        arpdau_delta = round((v_arpdau/c_arpdau - 1)*100, 2) if c_arpdau else 0
        ret_delta = round((v_ret - c_ret)*100, 2)
        winner = (arpdau_delta > 0 and ret_delta > -3)
        return {"control_arpdau": c_arpdau, "variant_arpdau": v_arpdau,
                "arpdau_delta_pct": arpdau_delta,
                "control_retention": c_ret, "variant_retention": v_ret,
                "retention_delta_pct": ret_delta,
                "decision": "WINNER" if winner else "LOSER",
                "control_n": len(control), "variant_n": len(variant)}
