# P04 Witch Merge
2026-07-23

## TOP RISKS

### 1. Monetization Aggressive
**Impact:** Medium
- Signal: chosen=monetization_aggressive | prior_mean=0.50 (n=0) | sim_rev=+1.7% sim_ret=+0.00% risk=low sev=0.60 conf=0.50 -> intended=experiment enforced=experiment
- Confidence: 50%, Prior: 50%
- Simulated revenue delta: +167.5%
- Risk: low
**Confidence:** 50%
**Recommended:** Run shadow experiment on monetization_aggressive

### 2. Monetization Aggressive
**Impact:** Medium
- Signal: chosen=monetization_aggressive | prior_mean=0.50 (n=0) | sim_rev=+1.7% sim_ret=+0.00% risk=low sev=0.64 conf=0.50 -> intended=observe enforced=observe
- Confidence: 50%, Prior: 50%
- Simulated revenue delta: +167.5%
- Risk: low
**Confidence:** 50%
**Recommended:** Monitor for 2 more days; if trend continues, escalate to experiment

### 3. Monetization Aggressive
**Impact:** Medium
- Signal: chosen=monetization_aggressive | prior_mean=0.50 (n=0) | sim_rev=+1.7% sim_ret=+0.00% risk=low sev=0.48 conf=0.50 -> intended=experiment enforced=experiment
- Confidence: 50%, Prior: 50%
- Simulated revenue delta: +167.5%
- Risk: low
**Confidence:** 50%
**Recommended:** Run shadow experiment on monetization_aggressive

### 4. No Action
**Impact:** Medium
- Signal: chosen=no_action | prior_mean=0.50 (n=0) | sim_rev=+0.0% sim_ret=+0.00% risk=low sev=0.63 conf=0.55 -> intended=experiment enforced=experiment
- Confidence: 55%, Prior: 50%
- Simulated revenue delta: +0.0%
- Risk: low
**Confidence:** 55%
**Recommended:** Monitor for 2 more days; if trend continues, escalate to experiment

### 5. Bid Floor Adjust
**Impact:** High
- Signal: chosen=bid_floor_adjust | prior_mean=0.50 (n=0) | sim_rev=+1.3% sim_ret=+0.00% risk=low sev=0.81 conf=0.54 -> intended=experiment enforced=experiment
- Confidence: 54%, Prior: 50%
- Simulated revenue delta: +133.6%
- Risk: low
**Confidence:** 54%
**Recommended:** Test bid_floor +10% on reward ad unit

---

## SHADOW DECISIONS

| # | Decision | Action | Confidence | Risk | Final |
|---|---|---|---|---|
| | monetization_aggressive | experiment | 50% | low | exp_completed |
| | monetization_aggressive | observe | 50% | low | observed |
| | monetization_aggressive | experiment | 50% | low | exp_completed |
| | no_action | observe | 55% | low | observed |
| | bid_floor_adjust | experiment | 54% | low | exp_completed |

*Mode: SHADOW — no production writes. All API calls: 3 (real: False)*