import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from creative_spec import ScoreEngine


class TestScoreEngine(unittest.TestCase):
    def test_can_instantiate(self):
        se = ScoreEngine()
        self.assertIsInstance(se, ScoreEngine)

    def test_score_returns_dict(self):
        se = ScoreEngine()
        result = se.score()
        self.assertIsInstance(result, dict)

    def test_score_contains_overall(self):
        se = ScoreEngine()
        result = se.score()
        self.assertIn("overall_score", result)

    def test_score_contains_dimensions(self):
        se = ScoreEngine()
        result = se.score()
        self.assertIn("dimensions", result)

    def test_score_contains_predictions(self):
        se = ScoreEngine()
        result = se.score()
        self.assertIn("predictions", result)

    def test_perfect_input_gives_100(self):
        se = ScoreEngine()
        result = se.score(subject_center=0.5, contrast=0.2, saturation=0.5, text_density=0.01, motion_change=0.15, reward_surge=0.1, has_cta=True, aspect_ratio="9:16", palette="warm")
        self.assertEqual(result["overall_score"], 100.0)

    def test_higher_score_grade_S(self):
        se = ScoreEngine()
        result = se.score(subject_center=0.5, contrast=0.2, saturation=0.5, text_density=0.01, motion_change=0.15, reward_surge=0.1, has_cta=True, aspect_ratio="9:16", palette="warm")
        self.assertEqual(result["grade"], "S")

    def test_low_score_grade_D(self):
        se = ScoreEngine()
        result = se.score(subject_center=0.0, contrast=0.0, saturation=0.0, text_density=0.1, motion_change=0.0, reward_surge=0.0, has_cta=False, aspect_ratio="1:1", palette="cool")
        self.assertEqual(result["grade"], "D")

    def test_score_1_to_100(self):
        se = ScoreEngine()
        result = se.score(subject_center=0.3, contrast=0.12, saturation=0.35, text_density=0.02, motion_change=0.08, reward_surge=0.04, has_cta=True, aspect_ratio="9:16", palette="neutral")
        score = result["overall_score"]
        self.assertGreaterEqual(score, 1)
        self.assertLessEqual(score, 100)

    def test_predict_includes_ctr(self):
        se = ScoreEngine()
        result = se.score()
        pred = result["predictions"]
        self.assertIn("expected_ctr", pred)

    def test_predict_includes_ipm(self):
        se = ScoreEngine()
        result = se.score()
        pred = result["predictions"]
        self.assertIn("expected_ipm", pred)

    def test_predict_includes_roas(self):
        se = ScoreEngine()
        result = se.score()
        pred = result["predictions"]
        self.assertIn("expected_roas", pred)

    def test_higher_score_gives_higher_prediction(self):
        se = ScoreEngine()
        low = se.score(subject_center=0.1, contrast=0.05, saturation=0.2, text_density=0.05, motion_change=0.02, reward_surge=0.01, has_cta=False, aspect_ratio="1:1", palette="cool")
        high = se.score(subject_center=0.5, contrast=0.2, saturation=0.5, text_density=0.01, motion_change=0.15, reward_surge=0.1, has_cta=True, aspect_ratio="9:16", palette="warm")
        self.assertGreater(high["predictions"]["expected_roas"], low["predictions"]["expected_roas"])

    def test_dimensions_are_numeric(self):
        se = ScoreEngine()
        result = se.score(subject_center=0.4, contrast=0.15, saturation=0.45, text_density=0.015, motion_change=0.10, reward_surge=0.05, has_cta=True, aspect_ratio="9:16", palette="warm")
        for k, v in result["dimensions"].items():
            self.assertIsInstance(v, (int, float))

    def test_no_cta_drops_score(self):
        se = ScoreEngine()
        with_cta = se.score(subject_center=0.5, contrast=0.2, saturation=0.5, text_density=0.01, motion_change=0.15, reward_surge=0.1, has_cta=True)
        without_cta = se.score(subject_center=0.5, contrast=0.2, saturation=0.5, text_density=0.01, motion_change=0.15, reward_surge=0.1, has_cta=False)
        self.assertGreater(with_cta["overall_score"], without_cta["overall_score"])

    def test_wrong_ratio_drops_score(self):
        se = ScoreEngine()
        correct = se.score(subject_center=0.5, contrast=0.2, saturation=0.5, text_density=0.01, motion_change=0.15, reward_surge=0.1, has_cta=True, aspect_ratio="9:16")
        wrong = se.score(subject_center=0.5, contrast=0.2, saturation=0.5, text_density=0.01, motion_change=0.15, reward_surge=0.1, has_cta=True, aspect_ratio="1:1")
        self.assertGreater(correct["overall_score"], wrong["overall_score"])

    def test_get_stats(self):
        se = ScoreEngine()
        stats = se.get_stats()
        self.assertIn("metrics", stats)


if __name__ == "__main__":
    unittest.main()
