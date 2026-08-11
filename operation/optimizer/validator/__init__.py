"""
E15.2.5 — Action validation layer.

The intelligence rules answer "what's wrong?". This layer answers the
harder, operationally-critical question the user asked for: "which of
these recommendations is actually WORTH executing, and how?"

It scores every ActionItem on execution value
(confidence x impact x safety x reversibility) and sorts each into one
of three layers:

    SAFE       (🔥 Execute Today)  — high-confidence, safe, reversible,
                                     concrete monetization lever;
                                     auto-execute *candidate* (Phase 3).
    EXPERIMENT (🧪 A/B first)      — real revenue/fill impact; validate
                                     with a controlled experiment.
    OBSERVE    (👀 Monitor)        — advisory / out-of-scope / watch-only;
                                     never an automated write.
"""
from operation.optimizer.validator.action_validator import (
    ActionValidator, ValidatedAction, Layer,
)

__all__ = ["ActionValidator", "ValidatedAction", "Layer"]
