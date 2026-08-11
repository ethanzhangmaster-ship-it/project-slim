import unittest
import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from creative_spec import CreativeExporter


class TestExporter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.exporter = CreativeExporter(output_dir=self.tmpdir)
        self.test_data = {
            "project": "P04 Witch",
            "hook_type": "collection",
            "hero": "witch",
            "score": {"overall_score": 85.0, "grade": "A", "predictions": {"expected_roas": 0.32, "expected_ctr": 0.018}},
            "storyboard": {
                "scenes": [
                    {"time_range": "0-0.8s", "category": "hook", "prompt": "High contrast witch", "camera": "centered", "duration_seconds": 0.8},
                    {"time_range": "0.8-3s", "category": "motion", "prompt": "Motion transition", "camera": "dynamic", "duration_seconds": 2.2},
                ]
            },
        }

    def test_can_instantiate(self):
        self.assertIsInstance(self.exporter, CreativeExporter)

    def test_export_production_spec_json(self):
        path = self.exporter.export_production_spec_json(self.test_data)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith(".json"))

    def test_export_storyboard_json(self):
        path = self.exporter.export_storyboard_json(self.test_data)
        self.assertTrue(os.path.exists(path))

    def test_export_prompt_json(self):
        path = self.exporter.export_prompt_json(self.test_data)
        self.assertTrue(os.path.exists(path))

    def test_export_creative_brief_md(self):
        path = self.exporter.export_creative_brief_md(self.test_data)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith(".md"))

    def test_export_creative_checklist_md(self):
        path = self.exporter.export_creative_checklist_md(self.test_data)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith(".md"))

    def test_exported_json_is_valid(self):
        path = self.exporter.export_production_spec_json({"key": "value"})
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["key"], "value")

    def test_brief_contains_project_name(self):
        path = self.exporter.export_creative_brief_md(self.test_data)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("P04 Witch", content)

    def test_checklist_contains_section_headers(self):
        path = self.exporter.export_creative_checklist_md(self.test_data)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Pre-Production", content)
        self.assertIn("Production", content)
        self.assertIn("Post-Production", content)

    def test_brief_contains_storyboard(self):
        path = self.exporter.export_creative_brief_md(self.test_data)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Scene 1", content)

    def test_get_stats(self):
        stats = self.exporter.get_stats()
        self.assertIn("output_dir", stats)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
