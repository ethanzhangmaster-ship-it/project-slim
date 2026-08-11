import unittest, sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from creative_generator import CreativeGenerator, VariantEngine, CreativeConfig


class TestGenerator(unittest.TestCase):
    def test_can_instantiate(self):
        gen = CreativeGenerator()
        self.assertIsInstance(gen, CreativeGenerator)

    def test_generate_returns_dict(self):
        gen = CreativeGenerator()
        result = gen.generate(count=5)
        self.assertIsInstance(result, dict)

    def test_generate_contains_creatives(self):
        gen = CreativeGenerator()
        result = gen.generate(count=10)
        self.assertEqual(len(result["creatives"]), 10)

    def test_generate_contains_project(self):
        gen = CreativeGenerator()
        result = gen.generate(project="P04 Test")
        self.assertEqual(result["project"], "P04 Test")

    def test_generate_contains_direction(self):
        gen = CreativeGenerator()
        result = gen.generate(direction="reward")
        self.assertEqual(result["direction"], "reward")

    def test_generate_count(self):
        gen = CreativeGenerator()
        result = gen.generate(count=20)
        self.assertEqual(result["count"], 20)

    def test_generate_unique_creatives(self):
        gen = CreativeGenerator()
        result = gen.generate(count=50)
        titles = [c["id"] for c in result["creatives"]]
        self.assertEqual(len(titles), len(set(titles)))

    def test_generate_with_curiosity_hook(self):
        gen = CreativeGenerator()
        result = gen.generate(direction="curiosity")
        self.assertEqual(result["direction"], "curiosity")

    def test_generate_batch_dir_created(self):
        gen = CreativeGenerator()
        result = gen.generate(count=3)
        import os
        self.assertTrue(os.path.exists(result["batch_dir"]))

    def test_generate_each_creative_has_id(self):
        gen = CreativeGenerator()
        result = gen.generate(count=10)
        for c in result["creatives"]:
            self.assertIn("id", c)
            self.assertIn("hero", c)

    def test_generate_each_creative_has_title(self):
        gen = CreativeGenerator()
        result = gen.generate(count=5)
        for c in result["creatives"]:
            self.assertTrue(c["title"])

    def test_get_stats(self):
        gen = CreativeGenerator()
        stats = gen.get_stats()
        self.assertIn("total_dna_combinations", stats)


class TestVariantEngine(unittest.TestCase):
    def test_can_instantiate(self):
        ve = VariantEngine()
        self.assertIsInstance(ve, VariantEngine)

    def test_generate_variant(self):
        ve = VariantEngine()
        config = CreativeConfig()
        asset = ve.generate_variant(config, "test_001")
        self.assertEqual(asset.creative_id, "test_001")

    def test_generate_variant_has_hero(self):
        ve = VariantEngine()
        config = CreativeConfig()
        asset = ve.generate_variant(config, "t1")
        self.assertIn("name", asset.hero)

    def test_generate_variant_has_environment(self):
        ve = VariantEngine()
        config = CreativeConfig()
        asset = ve.generate_variant(config, "t1")
        self.assertIn("name", asset.environment)

    def test_generate_variant_has_merge_object(self):
        ve = VariantEngine()
        config = CreativeConfig()
        asset = ve.generate_variant(config, "t1")
        self.assertIn("name", asset.merge_object)

    def test_generate_variant_has_reward(self):
        ve = VariantEngine()
        config = CreativeConfig()
        asset = ve.generate_variant(config, "t1")
        self.assertIn("name", asset.reward)

    def test_generate_variant_has_hook_type(self):
        ve = VariantEngine()
        config = CreativeConfig()
        asset = ve.generate_variant(config, "t1")
        self.assertEqual(asset.hook_type, "collection")

    def test_generate_creates_unique_combinations(self):
        ve = VariantEngine(seed=42)
        config = CreativeConfig()
        count = 20
        assets = ve.generate_variants(config, count)
        self.assertEqual(len(assets), count)

    def test_get_stats(self):
        ve = VariantEngine()
        stats = ve.get_stats()
        self.assertIn("used_combinations", stats)


if __name__ == "__main__":
    unittest.main()
