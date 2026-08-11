"""Experiments module — A/B validation and creative testing

V3.8.1: Real UA Validation Layer
V3.9: Creative Remix Evolution
"""

from .v38_1_real_ua import V381ABTest, run_v381_ab_test, V381ReportGenerator, generate_v381_report
from .v39_remix_evolution import V39ABTest, run_v39_ab_test, V39ReportGenerator, generate_v39_report

__all__ = [
    "V381ABTest",
    "run_v381_ab_test",
    "V381ReportGenerator",
    "generate_v381_report",
    "V39ABTest",
    "run_v39_ab_test",
    "V39ReportGenerator",
    "generate_v39_report",
]
