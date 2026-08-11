"""Adapter Contract Tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.market_ops.video_generation.adapters.registry import registry
from src.market_ops.video_generation.adapters.base_adapter import BaseAdapter
from src.market_ops.video_generation.models.adapter_result import AdapterResult


class TestAdapterContract(unittest.TestCase):
    """测试所有 Adapter 必须实现的契约"""

    def test_all_adapters_inherit_base(self):
        """所有 Adapter 必须继承 BaseAdapter"""
        for adapter in registry.all():
            self.assertIsInstance(adapter, BaseAdapter,
                f"{adapter.platform_name} does not inherit BaseAdapter")

    def test_all_adapters_have_compile(self):
        """所有 Adapter 必须有 compile 方法"""
        for adapter in registry.all():
            self.assertTrue(hasattr(adapter, "compile"),
                f"{adapter.platform_name} missing compile()")
            self.assertTrue(callable(getattr(adapter, "compile")),
                f"{adapter.platform_name}.compile is not callable")

    def test_all_adapters_have_validate(self):
        """所有 Adapter 必须有 validate 方法"""
        for adapter in registry.all():
            self.assertTrue(hasattr(adapter, "validate"),
                f"{adapter.platform_name} missing validate()")
            self.assertTrue(callable(getattr(adapter, "validate")),
                f"{adapter.platform_name}.validate is not callable")

    def test_all_adapters_have_estimate_cost(self):
        """所有 Adapter 必须有 estimate_cost 方法"""
        for adapter in registry.all():
            self.assertTrue(hasattr(adapter, "estimate_cost"),
                f"{adapter.platform_name} missing estimate_cost()")
            self.assertTrue(callable(getattr(adapter, "estimate_cost")),
                f"{adapter.platform_name}.estimate_cost is not callable")

    def test_all_adapters_have_platform_name(self):
        """所有 Adapter 必须有 platform_name"""
        for adapter in registry.all():
            self.assertTrue(hasattr(adapter, "platform_name"),
                f"Adapter missing platform_name")
            self.assertIsInstance(adapter.platform_name, str,
                f"platform_name must be a string")
            self.assertTrue(len(adapter.platform_name) > 0,
                f"platform_name cannot be empty")

    def test_compile_returns_adapter_result(self):
        """compile 必须返回 AdapterResult"""
        test_prompt = {
            "scene_id": "S01",
            "image_prompt": "test prompt",
            "negative_prompt": "negative",
            "duration": 5
        }
        for adapter in registry.all():
            result = adapter.compile(test_prompt)
            self.assertIsInstance(result, AdapterResult,
                f"{adapter.platform_name}.compile must return AdapterResult")

    def test_result_has_required_fields(self):
        """结果必须包含必要字段"""
        test_prompt = {
            "scene_id": "S01",
            "image_prompt": "test prompt",
            "negative_prompt": "negative",
            "duration": 5
        }
        for adapter in registry.all():
            result = adapter.compile(test_prompt)
            self.assertIn("platform", result.to_dict())
            self.assertIn("status", result.to_dict())
            self.assertIn("prompt", result.to_dict())
            self.assertIn("validation", result.to_dict())
            self.assertIn("cost", result.to_dict())


class TestPromptMapper(unittest.TestCase):
    """测试 Prompt Mapper"""

    def test_transform_maps_fields(self):
        from src.market_ops.video_generation.adapters.prompt_mapper import prompt_mapper
        
        master = {
            "image_prompt": "a cat",
            "video_prompt": "zoom in",
            "metadata": {
                "camera": {"lens": "24mm"}
            }
        }
        
        veo_result = prompt_mapper.transform(master, "veo")
        self.assertIn("prompt", veo_result)
        self.assertEqual(veo_result["prompt"], "a cat")

    def test_reverse_map_field(self):
        from src.market_ops.video_generation.adapters.prompt_mapper import prompt_mapper
        
        master_field = prompt_mapper.reverse_map_field("veo", "lens")
        self.assertEqual(master_field, "camera.lens")


class TestCapabilityValidator(unittest.TestCase):
    """测试 Capability Validator"""

    def test_duration_exceeded(self):
        from src.market_ops.video_generation.adapters.capability_validator import CapabilityValidator
        
        validator = CapabilityValidator({"duration": 8})
        result = validator.validate({"duration": 15})
        self.assertFalse(result["passed"])
        self.assertEqual(result["violations"][0]["code"], "duration_exceeded")

    def test_max_length_exceeded(self):
        from src.market_ops.video_generation.adapters.capability_validator import CapabilityValidator
        
        validator = CapabilityValidator({"max_token_length": 10})
        result = validator.validate({"prompt": "this is a very long prompt"})
        self.assertFalse(result["passed"])
        self.assertEqual(result["violations"][0]["code"], "max_length_exceeded")


class TestCostModel(unittest.TestCase):
    """测试 Cost Model"""

    def test_calculate_cost(self):
        from src.market_ops.video_generation.adapters.cost_model import CostModel
        
        model = CostModel(platform="test", price_per_second=0.2)
        result = model.calculate(duration=10)
        self.assertEqual(result["estimated_cost"], 2.0)

    def test_resolution_multiplier(self):
        from src.market_ops.video_generation.adapters.cost_model import CostModel
        
        model = CostModel(platform="test", price_per_second=0.2)
        result = model.calculate(duration=10, resolution="4k")
        self.assertEqual(result["estimated_cost"], 5.0)


if __name__ == "__main__":
    unittest.main()
