"""Release Gate V4.5.1"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.market_ops.video_generation.adapters.registry import registry
from src.market_ops.video_generation.adapters.base_adapter import BaseAdapter
from src.market_ops.video_generation.models.adapter_result import AdapterResult
from src.market_ops.video_generation.adapters.prompt_mapper import prompt_mapper
from src.market_ops.video_generation.adapters.capability_validator import CapabilityValidator
from src.market_ops.video_generation.adapters.cost_model import CostModel


def print_header():
    print("=" * 60)
    print("Blueprint Engine V4.5.1 Platform Adapter Gate")
    print("=" * 60)
    print()


def print_result(name: str, passed: bool):
    status = "PASS" if passed else "FAIL"
    symbol = "✓" if passed else "✗"
    print(f"  {symbol} {name:<30} {status}")


def check_adapter_contract() -> bool:
    try:
        for adapter in registry.all():
            assert isinstance(adapter, BaseAdapter)
            assert hasattr(adapter, "compile")
            assert hasattr(adapter, "validate")
            assert hasattr(adapter, "estimate_cost")
            assert hasattr(adapter, "platform_name")
            assert adapter.platform_name != ""
        return True
    except AssertionError:
        return False


def check_registry_discovery() -> bool:
    try:
        platforms = registry.list_platforms()
        assert len(platforms) >= 7
        assert "veo" in platforms
        assert "kling" in platforms
        assert "runway" in platforms
        assert "pika" in platforms
        assert "luma" in platforms
        assert "hailuo" in platforms
        assert "comfyui" in platforms
        return True
    except AssertionError:
        return False


def check_capability_validation() -> bool:
    try:
        validator = CapabilityValidator({"duration": 8, "max_token_length": 10})
        result = validator.validate({"duration": 15})
        assert not result["passed"]
        assert result["violations"][0]["code"] == "duration_exceeded"
        return True
    except (AssertionError, IndexError):
        return False


def check_prompt_mapping() -> bool:
    try:
        master = {"image_prompt": "test", "metadata": {"camera": {"lens": "24mm"}}}
        veo = prompt_mapper.transform(master, "veo")
        assert "prompt" in veo
        assert veo["prompt"] == "test"
        assert "lens" in veo
        return True
    except AssertionError:
        return False


def check_adapter_compile(platform: str) -> bool:
    try:
        adapter = registry.create(platform)
        test_prompt = {
            "scene_id": "S01",
            "image_prompt": "test prompt",
            "negative_prompt": "negative",
            "duration": 5
        }
        result = adapter.compile(test_prompt)
        assert isinstance(result, AdapterResult)
        assert result.platform == platform
        assert "status" in result.to_dict()
        return True
    except (AssertionError, Exception):
        return False


def check_cost_model() -> bool:
    try:
        model = CostModel(platform="test", price_per_second=0.2)
        result = model.calculate(duration=10)
        assert result["estimated_cost"] == 2.0
        return True
    except AssertionError:
        return False


def check_result_schema() -> bool:
    try:
        result = AdapterResult(
            platform="test",
            status="success",
            prompt={"key": "value"},
            validation={"passed": True},
            cost={"price": 1.0}
        )
        data = result.to_dict()
        assert "platform" in data
        assert "status" in data
        assert "prompt" in data
        assert "validation" in data
        assert "cost" in data
        assert "metadata" in data
        return True
    except AssertionError:
        return False


def check_ci_entry() -> bool:
    try:
        from src.market_ops.video_generation.video_generation_api import generate, generate_all
        assert callable(generate)
        assert callable(generate_all)
        return True
    except ImportError:
        return False


def main():
    print_header()

    results = []

    checks = [
        ("Adapter Contract", check_adapter_contract),
        ("Registry Discovery", check_registry_discovery),
        ("Capability Validation", check_capability_validation),
        ("Prompt Mapping", check_prompt_mapping),
        ("Veo Adapter", lambda: check_adapter_compile("veo")),
        ("Kling Adapter", lambda: check_adapter_compile("kling")),
        ("Runway Adapter", lambda: check_adapter_compile("runway")),
        ("Pika Adapter", lambda: check_adapter_compile("pika")),
        ("Luma Adapter", lambda: check_adapter_compile("luma")),
        ("Hailuo Adapter", lambda: check_adapter_compile("hailuo")),
        ("ComfyUI Adapter", lambda: check_adapter_compile("comfyui")),
        ("Cost Model", check_cost_model),
        ("Result Schema", check_result_schema),
        ("CI Entry", check_ci_entry),
    ]

    for name, check_func in checks:
        passed = check_func()
        print_result(name, passed)
        results.append(passed)

    total = len(results)
    passed = sum(results)

    print()
    print("=" * 60)
    print(f"TOTAL  {passed} / {total} PASS")
    print("=" * 60)

    if passed == total:
        print()
        print("V4.5.1 Production Ready")
        print()
        return 0
    else:
        print()
        print(f"FAILED: {total - passed} check(s) failed")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
