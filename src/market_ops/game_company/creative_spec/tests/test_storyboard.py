import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from creative_spec import StoryboardGenerator, Storyboard, Scene, SCENE_TEMPLATES


class TestStoryboard(unittest.TestCase):
    def test_generator_can_instantiate(self):
        gen = StoryboardGenerator()
        self.assertIsInstance(gen, StoryboardGenerator)

    def test_generate_returns_storyboard(self):
        gen = StoryboardGenerator()
        sb = gen.generate()
        self.assertIsInstance(sb, Storyboard)

    def test_storyboard_contains_5_scenes(self):
        gen = StoryboardGenerator()
        sb = gen.generate()
        self.assertEqual(len(sb.scenes), 5)

    def test_scene_has_required_fields(self):
        gen = StoryboardGenerator()
        sb = gen.generate()
        for scene in sb.scenes:
            self.assertTrue(scene.scene_id)
            self.assertTrue(scene.time_range)
            self.assertTrue(scene.category)
            self.assertTrue(scene.prompt)

    def test_hook_scene_first_frame(self):
        gen = StoryboardGenerator()
        sb = gen.generate()
        first = sb.scenes[0]
        self.assertEqual(first.category, "hook")

    def test_reward_scene_at_position_3(self):
        gen = StoryboardGenerator()
        sb = gen.generate()
        reward = sb.scenes[3]
        self.assertEqual(reward.category, "reward")

    def test_cta_scene_last(self):
        gen = StoryboardGenerator()
        sb = gen.generate()
        last = sb.scenes[-1]
        self.assertEqual(last.category, "cta")

    def test_generate_with_collection_hook(self):
        gen = StoryboardGenerator()
        sb = gen.generate(hook_type="collection")
        self.assertEqual(sb.hook_type, "collection")

    def test_generate_with_reward_hook(self):
        gen = StoryboardGenerator()
        sb = gen.generate(hook_type="reward")
        self.assertEqual(sb.hook_type, "reward")

    def test_generate_with_duration(self):
        gen = StoryboardGenerator()
        sb = gen.generate(duration=30)
        self.assertEqual(sb.total_duration, 30.0)

    def test_storyboard_to_dict(self):
        gen = StoryboardGenerator()
        sb = gen.generate()
        d = sb.to_dict()
        self.assertIn("scenes", d)
        self.assertIn("hook_type", d)

    def test_scene_to_dict(self):
        scene = Scene(scene_id="test", time_range="0-1s", category="hook", duration=1.0, prompt="test prompt")
        d = scene.to_dict()
        self.assertEqual(d["scene_id"], "test")
        self.assertEqual(d["duration_seconds"], 1.0)

    def test_storyboard_total_scenes(self):
        gen = StoryboardGenerator()
        sb = gen.generate()
        self.assertEqual(sb.total_scenes, 5)

    def test_generator_get_stats(self):
        gen = StoryboardGenerator()
        stats = gen.get_stats()
        self.assertIn("total_scene_templates", stats)

    def test_scene_camera_field(self):
        scene = Scene(scene_id="s1", time_range="0-0.8s", category="hook", duration=0.8, prompt="p", camera="centered")
        self.assertEqual(scene.camera, "centered")

    def test_scene_transition_field(self):
        scene = Scene(scene_id="s1", time_range="0-0.8s", category="hook", duration=0.8, prompt="p", transition="cut")
        self.assertEqual(scene.transition, "cut")

    def test_scene_to_dict_transition(self):
        scene = Scene(scene_id="s1", time_range="0-0.8s", category="hook", duration=0.8, prompt="p", transition="cut")
        d = scene.to_dict()
        self.assertEqual(d["transition"], "cut")


if __name__ == "__main__":
    unittest.main()
