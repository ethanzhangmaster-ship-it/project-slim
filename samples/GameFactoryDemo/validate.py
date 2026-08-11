#!/usr/bin/env python3
"""E13.2.6 Integration validation — Python-side checks + report emitter.

Run from the demo folder:  python validate.py
Writes integration_report.json:
  - python-checkable items -> PASS / FAIL
  - runtime items (need Unity Editor) -> PENDING_USER_UNITY

It also (re)generates Assets/Resources/GameFactory/gamefactory_config.json from product.yaml.
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LF = os.path.abspath(os.path.join(HERE, "..", ".."))  # launchforge/
sys.path.insert(0, os.path.join(LF, "src"))

import yaml  # noqa: E402
from config_generator import build_config  # noqa: E402

SDK_PKG = os.path.join(LF, "com.gamefactory.sdk")
RESOURCES = os.path.join(HERE, "Assets", "Resources", "GameFactory")
CONFIG_OUT = os.path.join(RESOURCES, "gamefactory_config.json")

# 1) build config from demo product.yaml
with open(os.path.join(HERE, "product.yaml"), encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
out = build_config(cfg)

os.makedirs(RESOURCES, exist_ok=True)
with open(CONFIG_OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

checks = {}
notes = []

# config_generation
ok = (
    out.get("ads", {}).get("provider") == "MAX"
    and out.get("analytics", {}).get("providers") == ["Firebase", "Adjust"]
    and any(e["key"] == "ads.reward_frequency" and e["value"] == "3"
            for e in out["remote_config"]["entries"])
)
checks["config_generation"] = "PASS" if ok else "FAIL"
if not ok:
    notes.append("config_generation failed: " + json.dumps(out, ensure_ascii=False))

# remote_config_flatten
rc = {e["key"]: e["value"] for e in out["remote_config"]["entries"]}
checks["remote_config_flatten"] = (
    "PASS" if rc.get("ads.reward_frequency") == "3" and "gameplay.level_difficulty" in rc else "FAIL")

# file_structure
expected = [
    "Packages/manifest.json",
    "ProjectSettings/ProjectVersion.txt",
    "Assets/Scenes/Boot.unity",
    "Assets/Scenes/Main.unity",
    "Assets/GameFactoryDemo/Scripts/Boot.cs",
    "Assets/GameFactoryDemo/Scripts/GameLoop.cs",
    "Assets/GameFactoryDemo/Scripts/AdTestController.cs",
    "Assets/GameFactoryDemo/Scripts/AnalyticsTest.cs",
    "Assets/GameFactoryDemo/Scripts/RemoteConfigTest.cs",
    "Assets/Resources/GameFactory/gamefactory_config.json",
]
missing = [p for p in expected if not os.path.exists(os.path.join(HERE, p))]
checks["file_structure"] = "PASS" if not missing else "FAIL"
if missing:
    notes.append("missing files: " + ", ".join(missing))

# sdk_package
checks["sdk_package"] = "PASS" if os.path.exists(os.path.join(SDK_PKG, "package.json")) else "FAIL"

# runtime items — only verifiable inside Unity Editor
for k in ["bootstrap_init", "ads_reward", "ads_interstitial",
          "ad_revenue_loop", "analytics_events", "remote_config_read", "android_build"]:
    checks[k] = "PENDING_USER_UNITY"

report = {
    "sdk_version": "1.0.0",
    "unity": "2022.3",
    "platform": "android",
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "config_summary": {
        "game_name": out.get("game_name"),
        "ads_provider": out.get("ads", {}).get("provider"),
        "analytics_providers": out.get("analytics", {}).get("providers"),
        "remote_config_keys": sorted(rc.keys()),
    },
    "checks": checks,
    "notes": "\n".join(notes) or "python-side checks passed; runtime items require Unity Editor (see README).",
}
with open(os.path.join(HERE, "integration_report.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(json.dumps(report, indent=2, ensure_ascii=False))
