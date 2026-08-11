import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from creative_spec import PromptBuilder, VideoPrompt, PROMPT_PLATFORMS


class TestPromptBuilder(unittest.TestCase):
    def test_can_instantiate(self):
        pb = PromptBuilder()
        self.assertIsInstance(pb, PromptBuilder)

    def test_build_returns_video_prompt(self):
        pb = PromptBuilder()
        storyboard = {"scenes": [{"prompt": "s1"}, {"prompt": "s2"}, {"prompt": "s3"}, {"prompt": "s4"}, {"prompt": "s5"}], "total_duration_seconds": 25}
        vp = pb.build(storyboard)
        self.assertIsInstance(vp, VideoPrompt)

    def test_build_default_platform(self):
        pb = PromptBuilder()
        storyboard = {"scenes": [{"prompt": "s1"}]*5, "total_duration_seconds": 25}
        vp = pb.build(storyboard)
        self.assertEqual(vp.platform, "runway")

    def test_build_with_platform(self):
        pb = PromptBuilder()
        storyboard = {"scenes": [{"prompt": "s1"}]*5, "total_duration_seconds": 25}
        vp = pb.build(storyboard, platform="openai")
        self.assertEqual(vp.platform, "openai")

    def test_build_with_collection_hook(self):
        pb = PromptBuilder()
        storyboard = {"scenes": [{"prompt": "s1"}]*5, "total_duration_seconds": 25}
        vp = pb.build(storyboard, hook_type="collection")
        self.assertIn("collection", vp.user_prompt.lower())

    def test_build_with_reward_hook(self):
        pb = PromptBuilder()
        storyboard = {"scenes": [{"prompt": "s1"}]*5, "total_duration_seconds": 25}
        vp = pb.build(storyboard, hook_type="reward")
        self.assertIn("reward", vp.user_prompt.lower())

    def test_video_prompt_has_system_prompt(self):
        pb = PromptBuilder()
        sb = {"scenes": [{"prompt": "s1"}]*5, "total_duration_seconds": 25}
        vp = pb.build(sb)
        self.assertTrue(vp.system_prompt)

    def test_video_prompt_has_negative_prompt(self):
        pb = PromptBuilder()
        sb = {"scenes": [{"prompt": "s1"}]*5, "total_duration_seconds": 25}
        vp = pb.build(sb)
        self.assertTrue(vp.negative_prompt)

    def test_video_prompt_has_style_prompt(self):
        pb = PromptBuilder()
        sb = {"scenes": [{"prompt": "s1"}]*5, "total_duration_seconds": 25}
        vp = pb.build(sb)
        self.assertTrue(vp.style_prompt)

    def test_video_prompt_has_camera_prompt(self):
        pb = PromptBuilder()
        sb = {"scenes": [{"prompt": "s1"}]*5, "total_duration_seconds": 25}
        vp = pb.build(sb)
        self.assertTrue(vp.camera_prompt)

    def test_video_prompt_to_dict(self):
        vp = VideoPrompt(platform="test", user_prompt="hello")
        d = vp.to_dict()
        self.assertEqual(d["platform"], "test")
        self.assertEqual(d["user_prompt"], "hello")

    def test_build_duration_from_storyboard(self):
        pb = PromptBuilder()
        sb = {"scenes": [{"prompt": "s1"}]*5, "total_duration_seconds": 30}
        vp = pb.build(sb)
        self.assertEqual(vp.duration, 30)

    def test_negative_prompt_contains_anti_patterns(self):
        pb = PromptBuilder()
        sb = {"scenes": [{"prompt": "s1"}]*5, "total_duration_seconds": 25}
        vp = pb.build(sb)
        self.assertIn("text overlay", vp.negative_prompt.lower())

    def test_get_platforms(self):
        pb = PromptBuilder()
        platforms = pb.get_platforms()
        self.assertIn("openai", platforms)
        self.assertIn("runway", platforms)

    def test_get_stats(self):
        pb = PromptBuilder()
        stats = pb.get_stats()
        self.assertIn("total_platforms", stats)

    def test_system_prompt_mentions_duration(self):
        pb = PromptBuilder()
        sb = {"scenes": [{"prompt": "s1"}]*5, "total_duration_seconds": 25}
        vp = pb.build(sb)
        self.assertIn("25", vp.system_prompt)

    def test_style_prompt_mentions_3d_cartoon(self):
        pb = PromptBuilder()
        sb = {"scenes": [{"prompt": "s1"}]*5, "total_duration_seconds": 25}
        vp = pb.build(sb, platform="kling")
        self.assertIn("3D cartoon", vp.style_prompt)


if __name__ == "__main__":
    unittest.main()
