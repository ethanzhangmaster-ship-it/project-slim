"""Creative Intelligence Layer Phase 3 - 持续学习闭环测试

跑通: M7 Prediction + M8 Feedback Learning + Dashboard

Usage:
    python scripts/test_phase3.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Load .env
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from market_ops.creative_intelligence import (
    CreativeDashboard,
    CreativePlanner,
    CreativePredictionEngine,
    FeedbackLearning,
)


def main():
    project = "P04"

    # ==============================
    # M7: Creative Prediction
    # ==============================
    print(f"\n{'='*60}")
    print("  M7: Creative Prediction")
    print(f"{'='*60}")

    # 先用M6生成prompts
    planner = CreativePlanner()
    prompts = planner.plan(project=project, count=6, strategy="balanced")

    # 对每个prompt做预测
    pred_engine = CreativePredictionEngine()
    predictions = pred_engine.predict_for_planner_output(prompts)

    print(f"\n[M7] 预测 {len(predictions)} 个prompt的效果:")
    for p in predictions:
        pred = p["prediction"]
        print(f"\n  [{p['type']}] {p['prompt_id']}")
        print(f"    预测CTR: {pred.get('predicted_ctr', 0)}% (基准: {pred.get('baseline_ctr', 0)}%)")
        print(f"    预测CPI: ${pred.get('predicted_cpi', 0)} | IPM: {pred.get('predicted_ipm', 0)}")
        print(f"    置信度: {pred.get('confidence', 0):.0%} | 匹配样本: {pred.get('matched_samples', 0)}")
        print(f"    贡献规则: {len(pred.get('contributing_rules', []))} 条")
        for r in pred.get("contributing_rules", [])[:3]:
            print(f"      - {r['pattern']} ({r['effect']}, lift={r['lift_pct']}%)")

    pred_engine.close()

    # ==============================
    # M8: Feedback Learning (skip_facebook_sync=True, 用现有数据)
    # ==============================
    print(f"\n{'='*60}")
    print("  M8: Feedback Learning (Daily)")
    print(f"{'='*60}")

    learner = FeedbackLearning()
    result = learner.run_daily(project=project, skip_facebook_sync=True)

    print(f"\n[M8] 学习循环完成:")
    print(f"  耗时: {result['elapsed_sec']}s")
    for step, info in result["steps"].items():
        status = info["status"]
        detail = ""
        if "records" in info:
            detail = f" ({info['records']} records)"
        elif "new_features" in info:
            detail = f" ({info['new_features']} new)"
        elif "samples" in info:
            detail = f" ({info['samples']} samples)"
        elif "rules_updated" in info:
            detail = f" ({info['rules_updated']} rules)"
        print(f"  {step}: {status}{detail}")

    # ==============================
    # Dashboard
    # ==============================
    print(f"\n{'='*60}")
    print("  Dashboard")
    print(f"{'='*60}")

    dash = CreativeDashboard()
    dashboard_path = dash.generate(project=project)
    dash.close()

    print(f"\n[Dashboard] 已生成: {dashboard_path}")
    print(f"  打开: file:///{dashboard_path}".replace("\\", "/"))

    print(f"\n{'='*60}")
    print("  Phase 3 闭环测试完成")
    print(f"  M7 Prediction → M8 Feedback → Dashboard")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
