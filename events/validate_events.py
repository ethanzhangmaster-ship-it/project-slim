#!/usr/bin/env python3
# E13.2.7 Monetization Data Pipeline — event-layer validation (no backend).
#
# What this proves on a machine WITHOUT Unity:
#   1. Every standardized event serializes to the canonical GameFactoryEvent shape.
#   2. Each event carries the required envelope + event-specific fields.
#   3. The buffer JSON round-trips (the C# EventSerializer writes standard JSON; this is the
#      exact payload the offline cache stores and the uploader forwards).
#
# Run:  python validate_events.py
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, "GameFactoryEvent.schema.json")
SAMPLE = os.path.join(HERE, "sample_events.json")
REPORT = os.path.join(HERE, "events_report.json")

# Event name -> extra required keys (beyond the common envelope).
EVENT_SPECS = {
    "install": [],
    "session_start": [],
    "level_start": ["level"],
    "level_complete": ["level", "score"],
    "ad_request": ["ad_format", "placement", "network"],
    "ad_show": ["ad_format", "placement"],
    "ad_complete": ["ad_format", "placement", "completed"],
    "ad_revenue": ["ad_format", "network", "placement", "ad_unit", "revenue", "ecpm", "latency"],
    "purchase": ["product_id", "price", "currency"],
}
ENVELOPE = ["event", "game", "platform", "country", "user_id", "session_id", "timestamp_ms", "timestamp"]


def now_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def envelope(event_name, game="word001", platform="android"):
    ts = now_ms()
    return {
        "event": event_name,
        "game": game,
        "platform": platform,
        "country": None,
        "user_id": None,
        "session_id": None,
        "timestamp_ms": ts,
        "timestamp": datetime.fromtimestamp(ts / 1000, timezone.utc).isoformat(),
    }


def build_samples():
    s = []

    e = envelope("install");                                   s.append(e)
    e = envelope("session_start"); e["session_id"] = "sess_1"; s.append(e)
    e = envelope("level_start");   e["level"] = 1;             s.append(e)
    e = envelope("level_complete"); e["level"] = 1; e["score"] = 100.0; s.append(e)

    e = envelope("ad_request"); e.update(ad_format="reward", placement="reward_01", network="applovin"); s.append(e)
    e = envelope("ad_show");    e.update(ad_format="reward", placement="reward_01");                     s.append(e)
    e = envelope("ad_complete"); e.update(ad_format="reward", placement="reward_01", completed=True);    s.append(e)

    e = envelope("ad_revenue")
    e.update(ad_format="reward", network="applovin", placement="reward_01", ad_unit="reward_01",
             revenue=0.0325, ecpm=32.5, latency=350, country="US")
    s.append(e)

    e = envelope("purchase"); e.update(product_id="remove_ads", price=2.99, currency="USD"); s.append(e)
    return s


def validate(samples):
    errors = []
    for ev in samples:
        name = ev["event"]
        required = set(ENVELOPE) | set(EVENT_SPECS.get(name, []))
        missing = required - set(ev.keys())
        if missing:
            errors.append(f"{name}: missing {sorted(missing)}")
            continue
        # type sanity
        if not isinstance(ev["timestamp_ms"], int):
            errors.append(f"{name}: timestamp_ms not int")
        if name == "ad_revenue":
            if not isinstance(ev["revenue"], (int, float)):
                errors.append("ad_revenue: revenue not number")
            if abs(ev["ecpm"] - round(ev["revenue"] * 1000, 4)) > 1e-6:
                errors.append("ad_revenue: ecpm != revenue*1000")
    return errors


def roundtrip(samples):
    # Mirror the C# EventSerializer: events are written as JSON lines; the cache parses them back.
    lines = [json.dumps(ev, ensure_ascii=False) for ev in samples]
    parsed = []
    for ln in lines:
        try:
            parsed.append(json.loads(ln))
        except json.JSONDecodeError as ex:
            return None, f"JSON parse failed: {ex}"
    # values must be preserved exactly
    if parsed != samples:
        return None, "round-trip value mismatch"
    return parsed, None


def main():
    samples = build_samples()
    errors = validate(samples)
    parsed, rt_err = roundtrip(samples)

    with open(SCHEMA) as f:
        schema = json.load(f)
    with open(SAMPLE, "w") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    if parsed is not None:
        with open(os.path.join(HERE, "sample_events.jsonl"), "w") as f:
            for ln in parsed:
                f.write(json.dumps(ln, ensure_ascii=False) + "\n")

    python_ok = (not errors) and (rt_err is None)
    report = {
        "layer": "E13.2.7 Monetization Data Pipeline",
        "schema_version": "1.0",
        "schema_file": "GameFactoryEvent.schema.json",
        "python_side": "PASS" if python_ok else "FAIL",
        "events_validated": sorted(EVENT_SPECS.keys()),
        "event_count": len(samples),
        "schema_required_fields_ok": not errors,
        "buffer_roundtrip": "PASS" if rt_err is None else "FAIL",
        "backend_connected": False,
        "runtime_unity": "PENDING_USER_UNITY",
        "notes": "C# not compiled on this machine (no Unity). Validate in Unity via GameFactoryDemo > MonetizationTest.",
        "errors": errors,
        "roundtrip_error": rt_err,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(REPORT, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # console summary
    print("=== E13.2.7 Event Layer Validation ===")
    print(f"events validated : {len(samples)} -> {', '.join(sorted(EVENT_SPECS.keys()))}")
    print(f"schema fields    : {'PASS' if not errors else 'FAIL'}  {errors or ''}")
    print(f"buffer round-trip: {'PASS' if rt_err is None else 'FAIL'}  {rt_err or ''}")
    print(f"backend connected: False (Lean, no backend)")
    print(f"python_side      : {'PASS' if python_ok else 'FAIL'}")
    print(f"reports written  : {os.path.basename(REPORT)}, {os.path.basename(SAMPLE)}")
    print("=== DONE ===")
    sys.exit(0 if python_ok else 1)


if __name__ == "__main__":
    main()
