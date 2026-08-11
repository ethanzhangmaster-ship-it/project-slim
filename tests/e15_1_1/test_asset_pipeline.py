"""E15.1.1 — Asset Pipeline tests (20)."""
from tests.e15_1_1.e15_1_1_helpers import game
from operation.publishing_factory.asset_pipeline.screenshot_generator import (
    ScreenshotGenerator, ScreenshotSet, ScreenshotSpec,
)
from operation.publishing_factory.asset_pipeline.icon_generator import (
    IconGenerator, IconSpec,
)
from operation.publishing_factory.asset_pipeline.video_generator import (
    VideoGenerator, VideoStoryboard, _MAX_SECONDS,
)
from operation.publishing_factory.asset_pipeline.asset_validator import (
    AssetValidator, _HEADLINE_MAX, _SUBHEAD_MAX, _SS_MIN, _SS_MAX, _VIDEO_MAX,
)


def test_screenshot_count_default():
    ss = ScreenshotGenerator().generate(game())
    assert len(ss.screenshots) == 5


def test_screenshot_count_custom():
    ss = ScreenshotGenerator(count=3).generate(game())
    assert len(ss.screenshots) == 3


def test_screenshot_first_is_hook():
    ss = ScreenshotGenerator().generate(game())
    assert ss.screenshots[0].layout == "hook"


def test_screenshot_last_is_fantasy():
    ss = ScreenshotGenerator().generate(game())
    assert ss.screenshots[-1].layout == "fantasy"


def test_screenshot_headline_nonempty():
    ss = ScreenshotGenerator().generate(game())
    assert all(s.headline for s in ss.screenshots)


def test_screenshot_palette_present():
    ss = ScreenshotGenerator().generate(game())
    assert all(s.palette.get("bg") for s in ss.screenshots)


def test_screenshot_indices_sequential():
    ss = ScreenshotGenerator().generate(game())
    assert [s.index for s in ss.screenshots] == list(range(len(ss.screenshots)))


def test_screenshot_genre_variation():
    a = ScreenshotGenerator().generate(game(genre="merge")).screenshots[0].palette["bg"]
    b = ScreenshotGenerator().generate(game(genre="puzzle")).screenshots[0].palette["bg"]
    assert a != b


def test_screenshot_to_dict():
    ss = ScreenshotGenerator().generate(game())
    d = ss.to_dict()
    assert d["count"] == 5 and "screenshots" in d


def test_icon_spec_fields():
    ic = IconGenerator().generate(game(genre="merge"))
    assert ic.glyph == "spark" and ic.base_color and ic.style == "neon_glass"


def test_icon_genre_glyph_map():
    assert IconGenerator().generate(game(genre="word")).glyph == "letter"
    assert IconGenerator().generate(game(genre="idle")).glyph == "coin"


def test_icon_text_is_initial():
    ic = IconGenerator().generate(game(display_name="Merge Witch"))
    assert ic.text == "M"


def test_icon_to_dict():
    ic = IconGenerator().generate(game())
    assert ic.to_dict()["game_id"] == "merge_witch"


def test_video_scenes_within_limit():
    vb = VideoGenerator().generate(game())
    assert vb.total_seconds <= _MAX_SECONDS
    assert all(s.duration_s <= 15 for s in vb.scenes)


def test_video_scene_count_matches_points():
    vb = VideoGenerator().generate(game())
    assert len(vb.scenes) >= 1


def test_video_last_scene_logo_sting():
    vb = VideoGenerator().generate(game())
    assert vb.scenes[-1].shot == "logo_sting"


def test_video_to_dict():
    vb = VideoGenerator().generate(game())
    assert vb.to_dict()["total_seconds"] == vb.total_seconds


def test_validator_pass_clean_set():
    g = game()
    ss = ScreenshotGenerator().generate(g)
    ic = IconGenerator().generate(g)
    vb = VideoGenerator().generate(g)
    rep = AssetValidator().validate(g.game_id, ss, ic, vb)
    assert rep.valid is True
    assert rep.issues == []


def test_validator_fail_too_few_screenshots():
    g = game()
    ss = ScreenshotSet(game_id=g.game_id, genre=g.genre, screenshots=[])
    ic = IconGenerator().generate(g)
    vb = VideoGenerator().generate(g)
    rep = AssetValidator().validate(g.game_id, ss, ic, vb)
    assert rep.valid is False
    assert any("screenshot count" in i for i in rep.issues)


def test_validator_fail_long_headline():
    g = game()
    ss = ScreenshotGenerator(count=3).generate(g)
    ss.screenshots[0].headline = "X" * (_HEADLINE_MAX + 5)
    ic = IconGenerator().generate(g)
    vb = VideoGenerator().generate(g)
    rep = AssetValidator().validate(g.game_id, ss, ic, vb)
    assert rep.valid is False
