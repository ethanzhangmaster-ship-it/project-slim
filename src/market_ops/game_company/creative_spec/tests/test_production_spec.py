import unittest
import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from creative_spec import ProductionSpec


class TestProductionSpec(unittest.TestCase):
    def test_can_instantiate(self):
        spec = ProductionSpec()
        self.assertIsInstance(spec, ProductionSpec)

    def test_default_project(self):
        spec = ProductionSpec()
        self.assertEqual(spec.project, "P04 Witch")

    def test_to_dict_returns_dict(self):
        spec = ProductionSpec()
        d = spec.to_dict()
        self.assertIsInstance(d, dict)

    def test_to_dict_contains_project(self):
        spec = ProductionSpec()
        d = spec.to_dict()
        self.assertIn("project", d)

    def test_to_dict_contains_metadata(self):
        spec = ProductionSpec()
        d = spec.to_dict()
        self.assertIn("metadata", d)

    def test_save_load_json(self):
        spec = ProductionSpec(project="test", hook={"type": "collection"})
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.close()
            try:
                spec.save_json(f.name)
                loaded = ProductionSpec.load_json(f.name)
                self.assertEqual(loaded.project, "test")
                self.assertEqual(loaded.hook["type"], "collection")
            finally:
                os.unlink(f.name)

    def test_load_json_returns_production_spec(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump({"project": "P04 Test", "hook": {}, "storyboard": [], "visual": {}, "reward": {}, "cta": {}, "rules": [], "score": {}, "metadata": {}}, f)
            f.close()
            try:
                spec = ProductionSpec.load_json(f.name)
                self.assertIsInstance(spec, ProductionSpec)
                self.assertEqual(spec.project, "P04 Test")
            finally:
                os.unlink(f.name)

    def test_get_rule_existing(self):
        spec = ProductionSpec(rules=[{"id": "V1", "rule": "test"}])
        rule = spec.get_rule("V1")
        self.assertIsNotNone(rule)
        self.assertEqual(rule["rule"], "test")

    def test_get_rule_missing(self):
        spec = ProductionSpec()
        rule = spec.get_rule("NONEXISTENT")
        self.assertIsNone(rule)

    def test_add_rule_new(self):
        spec = ProductionSpec()
        spec.add_rule({"id": "NEW", "rule": "new rule"})
        self.assertEqual(len(spec.rules), 1)

    def test_add_rule_duplicate(self):
        spec = ProductionSpec(rules=[{"id": "DUP", "rule": "original"}])
        spec.add_rule({"id": "DUP", "rule": "duplicate"})
        self.assertEqual(len(spec.rules), 1)

    def test_update_score(self):
        spec = ProductionSpec()
        spec.update_score({"overall": 85})
        self.assertEqual(spec.score["overall"], 85)

    def test_update_score_merges(self):
        spec = ProductionSpec(score={"existing": 50})
        spec.update_score({"new_key": 90})
        self.assertIn("existing", spec.score)
        self.assertIn("new_key", spec.score)

    def test_save_returns_path(self):
        spec = ProductionSpec()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.close()
            try:
                path = spec.save_json(f.name)
                self.assertEqual(path, f.name)
            finally:
                os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
