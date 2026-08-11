import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from creative_spec import QAChecker, QAReport, QACheck, QAResult


class TestQAChecker(unittest.TestCase):
    def test_can_instantiate(self):
        qa = QAChecker()
        self.assertIsInstance(qa, QAChecker)

    def test_check_returns_report(self):
        qa = QAChecker()
        data = {"name": "test_video", "subject_center_score": 0.5, "first_frame_contrast": 0.2, "first_frame_saturation": 0.5, "text_density_0_3s": 0.01, "motion_change_0_3s": 0.15, "reward_visual_surge": 0.1, "cta_present": True, "aspect_ratio": "9:16", "palette": "warm"}
        report = qa.check(data)
        self.assertIsInstance(report, QAReport)

    def test_report_has_name(self):
        qa = QAChecker()
        data = {"name": "my_video"}
        report = qa.check(data)
        self.assertEqual(report.video_name, "my_video")

    def test_report_has_checks(self):
        qa = QAChecker()
        report = qa.check({"name": "test"})
        self.assertTrue(len(report.checks) > 0)

    def test_perfect_video_passes(self):
        qa = QAChecker()
        perfect = {"name": "perfect", "subject_center_score": 0.5, "first_frame_contrast": 0.2, "first_frame_saturation": 0.5, "text_density_0_3s": 0.01, "motion_change_0_3s": 0.15, "reward_visual_surge": 0.1, "cta_present": True, "aspect_ratio": "9:16", "palette": "warm"}
        report = qa.check(perfect)
        self.assertEqual(report.passed, report.total_checks)

    def test_bad_contrast_fails(self):
        qa = QAChecker()
        bad = {"name": "bad", "subject_center_score": 0.5, "first_frame_contrast": 0.05, "first_frame_saturation": 0.5, "text_density_0_3s": 0.01, "motion_change_0_3s": 0.15, "reward_visual_surge": 0.1, "cta_present": True, "aspect_ratio": "9:16", "palette": "warm"}
        report = qa.check(bad)
        self.assertTrue(report.failed > 0)

    def test_report_to_dict(self):
        qa = QAChecker()
        report = qa.check({"name": "test"})
        d = report.to_dict()
        self.assertIn("video_name", d)
        self.assertIn("score", d)

    def test_check_result_enum_values(self):
        self.assertEqual(QAResult.PASS.value, "PASS")
        self.assertEqual(QAResult.WARNING.value, "WARNING")
        self.assertEqual(QAResult.FAIL.value, "FAIL")

    def test_qacheck_to_dict(self):
        check = QACheck("V1", "Test", "framing", QAResult.PASS, 1.0, "OK", "Good job")
        d = check.to_dict()
        self.assertEqual(d["check_id"], "V1")
        self.assertEqual(d["result"], "PASS")

    def test_missing_cta_fails(self):
        qa = QAChecker()
        no_cta = {"name": "no_cta", "subject_center_score": 0.5, "first_frame_contrast": 0.2, "first_frame_saturation": 0.5, "text_density_0_3s": 0.01, "motion_change_0_3s": 0.15, "reward_visual_surge": 0.1, "cta_present": False, "aspect_ratio": "9:16", "palette": "warm"}
        report = qa.check(no_cta)
        cta_check = [c for c in report.checks if c.check_id == "V7"][0]
        self.assertEqual(cta_check.result, QAResult.FAIL)

    def test_wrong_aspect_ratio_warns(self):
        qa = QAChecker()
        wrong = {"name": "wrong_ratio", "aspect_ratio": "1:1"}
        report = qa.check(wrong)
        ratio_check = [c for c in report.checks if c.check_id == "V8"][0]
        self.assertEqual(ratio_check.result, QAResult.WARNING)

    def test_motion_below_threshold_fails(self):
        qa = QAChecker()
        no_motion = {"name": "static", "motion_change_0_3s": 0.03}
        report = qa.check(no_motion)
        motion_check = [c for c in report.checks if c.check_id == "V5"][0]
        self.assertEqual(motion_check.result, QAResult.FAIL)

    def test_reward_below_threshold_fails(self):
        qa = QAChecker()
        no_reward = {"name": "no_reward", "reward_visual_surge": 0.02}
        report = qa.check(no_reward)
        reward_check = [c for c in report.checks if c.check_id == "V6"][0]
        self.assertEqual(reward_check.result, QAResult.FAIL)

    def test_get_stats(self):
        qa = QAChecker()
        stats = qa.get_stats()
        self.assertIn("total_check_types", stats)


if __name__ == "__main__":
    unittest.main()
