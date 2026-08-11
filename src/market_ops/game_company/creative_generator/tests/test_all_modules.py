import unittest, sys, os, json, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from creative_generator import (
    ScriptGenerator, PromptGenerator, ThumbnailGenerator,
    SubtitleGenerator, MusicSelector, CTAGenerator,
    PredictionEngine, CreativeExporter, VariantEngine, CreativeConfig,
)


class TestScriptGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = ScriptGenerator()
        self.ve = VariantEngine()
        self.asset = self.ve.generate_variant(CreativeConfig(), "test")

    def test_can_instantiate(self):
        self.assertIsInstance(self.gen, ScriptGenerator)

    def test_generate_returns_dict(self):
        script = self.gen.generate(self.asset)
        self.assertIsInstance(script, dict)

    def test_script_contains_8_scenes(self):
        script = self.gen.generate(self.asset)
        self.assertEqual(len(script["scenes"]), 8)

    def test_script_contains_title(self):
        script = self.gen.generate(self.asset)
        self.assertIn("title", script)

    def test_each_scene_has_all_fields(self):
        script = self.gen.generate(self.asset)
        for scene in script["scenes"]:
            for key in ["scene", "time", "category", "action", "narration", "subtitles", "effects", "transition"]:
                self.assertIn(key, scene)

    def test_to_markdown_returns_string(self):
        script = self.gen.generate(self.asset)
        md = self.gen.to_markdown(script)
        self.assertIsInstance(md, str)

    def test_markdown_contains_scene_headers(self):
        script = self.gen.generate(self.asset)
        md = self.gen.to_markdown(script)
        self.assertIn("Scene 1", md)
        self.assertIn("Scene 8", md)


class TestPromptGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = PromptGenerator()
        self.ve = VariantEngine()
        self.asset = self.ve.generate_variant(CreativeConfig(), "test")

    def test_can_instantiate(self):
        self.assertIsInstance(self.gen, PromptGenerator)

    def test_generate_returns_dict(self):
        result = self.gen.generate(self.asset, "runway")
        self.assertIsInstance(result, dict)

    def test_generate_has_key_fields(self):
        result = self.gen.generate(self.asset, "runway")
        for key in ["system_prompt", "user_prompt", "negative_prompt", "style_prompt", "camera_prompt"]:
            self.assertIn(key, result)

    def test_generate_all_returns_8_platforms(self):
        result = self.gen.generate_all(self.asset)
        self.assertEqual(len(result), 8)

    def test_different_platforms_have_different_prompts(self):
        rw = self.gen.generate(self.asset, "runway")
        ok = self.gen.generate(self.asset, "kling")
        self.assertNotEqual(rw["user_prompt"], ok["user_prompt"])

    def test_get_platforms(self):
        platforms = self.gen.get_platforms()
        self.assertIn("runway", platforms)

    def test_get_stats(self):
        stats = self.gen.get_stats()
        self.assertIn("total_platforms", stats)


class TestThumbnailGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = ThumbnailGenerator()
        self.ve = VariantEngine()
        self.asset = self.ve.generate_variant(CreativeConfig(), "test")

    def test_can_instantiate(self):
        self.assertIsInstance(self.gen, ThumbnailGenerator)

    def test_generate_returns_dict(self):
        result = self.gen.generate(self.asset)
        self.assertIsInstance(result, dict)

    def test_generate_has_prompts(self):
        result = self.gen.generate(self.asset)
        for key in ["flux_prompt", "midjourney_prompt", "ideogram_prompt"]:
            self.assertIn(key, result)


class TestSubtitleGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = SubtitleGenerator()

    def test_can_instantiate(self):
        self.assertIsInstance(self.gen, SubtitleGenerator)

    def test_generate_returns_dict(self):
        result = self.gen.generate("collection")
        self.assertIn("timestamps", result)

    def test_generate_has_multiple_timestamps(self):
        result = self.gen.generate("collection")
        self.assertTrue(len(result["timestamps"]) >= 3)

    def test_generate_srt_returns_string(self):
        srt = self.gen.generate_srt("collection")
        self.assertIn("00:00:", srt)

    def test_get_animation_suggestions(self):
        anims = self.gen.get_animation_suggestions("collection")
        self.assertTrue(len(anims) >= 1)


class TestMusicSelector(unittest.TestCase):
    def setUp(self):
        self.gen = MusicSelector()
        self.ve = VariantEngine()
        self.asset = self.ve.generate_variant(CreativeConfig(), "test")

    def test_can_instantiate(self):
        self.assertIsInstance(self.gen, MusicSelector)

    def test_select_returns_dict(self):
        result = self.gen.select(self.asset)
        self.assertIn("music", result)
        self.assertIn("sound_effects", result)

    def test_select_has_bpm(self):
        result = self.gen.select(self.asset)
        self.assertIn("bpm", result["music"])


class TestCTAGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = CTAGenerator()

    def test_can_instantiate(self):
        self.assertIsInstance(self.gen, CTAGenerator)

    def test_generate_returns_dict(self):
        result = self.gen.generate()
        self.assertIn("primary_text", result)

    def test_get_variants(self):
        variants = self.gen.get_variants("collection")
        self.assertTrue(len(variants) >= 3)


class TestPredictionEngine(unittest.TestCase):
    def setUp(self):
        self.gen = PredictionEngine()
        self.ve = VariantEngine()
        self.asset = self.ve.generate_variant(CreativeConfig(), "test")

    def test_can_instantiate(self):
        self.assertIsInstance(self.gen, PredictionEngine)

    def test_predict_returns_dict(self):
        result = self.gen.predict(self.asset)
        self.assertIn("predicted_roas", result)
        self.assertIn("predicted_ctr", result)

    def test_predict_has_reasons(self):
        result = self.gen.predict(self.asset)
        self.assertTrue(len(result["reasons"]) >= 1)

    def test_predict_has_confidence(self):
        result = self.gen.predict(self.asset)
        self.assertGreater(result["confidence"], 0)
        self.assertLessEqual(result["confidence"], 1)

    def test_predict_has_grade(self):
        result = self.gen.predict(self.asset)
        self.assertIn(result["grade"], ["S", "A", "B", "C", "D"])

    def test_collection_hook_grades_higher(self):
        coll_asset = self.ve.generate_variant(CreativeConfig(hook_type="collection"), "c1")
        coll = self.gen.predict(coll_asset)

        crisis_asset = self.ve.generate_variant(CreativeConfig(hook_type="crisis"), "c2")
        crisis = self.gen.predict(crisis_asset)

        self.assertGreaterEqual(coll["predicted_roas"], crisis["predicted_roas"] * 0.5)


class TestExporter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gen = CreativeExporter(base_dir=self.tmpdir)
        self.ve = VariantEngine()

    def test_export_creative_creates_dir(self):
        asset = self.ve.generate_variant(CreativeConfig(), "test_001")
        export_dir = os.path.join(self.tmpdir, "test_001")
        self.gen.export_creative(asset, export_dir)
        self.assertTrue(os.path.exists(export_dir))

    def test_export_creative_has_all_files(self):
        asset = self.ve.generate_variant(CreativeConfig(), "test_002")
        export_dir = os.path.join(self.tmpdir, "test_002")
        self.gen.export_creative(asset, export_dir)
        for f in ["script.json", "thumbnail.json", "subtitles.json", "subtitles.srt",
                   "music.json", "cta.json", "prediction.json", "script.md",
                   "creative_brief.md", "creative_checklist.md"]:
            self.assertTrue(os.path.exists(os.path.join(export_dir, f)),
                            f"Missing file: {f} in {export_dir}")

    def test_export_creative_has_prompts_dir(self):
        asset = self.ve.generate_variant(CreativeConfig(), "test_003")
        export_dir = os.path.join(self.tmpdir, "test_003")
        self.gen.export_creative(asset, export_dir)
        prompts_dir = os.path.join(export_dir, "prompts")
        self.assertTrue(os.path.exists(prompts_dir))

    def test_export_batch_creates_batch_dir(self):
        assets = self.ve.generate_variants(CreativeConfig(), 5)
        batch_dir = self.gen.export_batch(assets)
        self.assertTrue(os.path.exists(batch_dir))
        self.assertTrue(os.path.exists(os.path.join(batch_dir, "batch_summary.json")))

    def test_export_batch_has_all_creatives(self):
        assets = self.ve.generate_variants(CreativeConfig(), 10)
        batch_dir = self.gen.export_batch(assets)
        for asset in assets:
            self.assertTrue(os.path.exists(os.path.join(batch_dir, asset.creative_id)))

    def test_get_stats(self):
        stats = self.gen.get_stats()
        self.assertIn("base_dir", stats)


if __name__ == "__main__":
    unittest.main()
