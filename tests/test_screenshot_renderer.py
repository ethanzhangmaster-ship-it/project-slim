"""ScreenshotRenderer 测试套件 — 截图自动渲染闭环 (Spec → 像素图片).

测试覆盖:
  1. ScreenshotSpec 创建与默认值
  2. 设备尺寸预设
  3. 配色方案预设
  4. create_spec 辅助方法 (含错误校验)
  5. 单个截图渲染 (文件生成 / 尺寸 / 元信息)
  6. 批量渲染
  7. 多种布局渲染 (top_text_bottom_image / center_text / full_image_overlay)
  8. 多种配色方案渲染 (像素颜色校验)
  9. 可选背景图叠加
 10. 列出已渲染截图 (含 game_id 过滤)
 11. 统计信息
 12. API 端点 (6 个)
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

# 确保项目根目录在 path 中
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.market_ops.workspace.screenshot_renderer import (
    RenderedScreenshot,
    ScreenshotRenderer,
    ScreenshotSpec,
)


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def renderer(tmp_path: Path) -> ScreenshotRenderer:
    """使用临时输出目录的渲染器，避免污染真实 data/screenshots/."""
    return ScreenshotRenderer(output_dir=str(tmp_path / "screenshots"))


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """创建一张临时素材图用于背景图叠加测试."""
    img = Image.new("RGB", (800, 800), color=(90, 180, 60))
    # 画几条色块让图片非纯色
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.rectangle((100, 100, 700, 700), fill=(30, 60, 200))
    path = tmp_path / "sample_bg.png"
    img.save(path)
    return path


# ── 1. ScreenshotSpec 创建与默认值 ────────────────────────


class TestScreenshotSpec:
    def test_default_values(self) -> None:
        spec = ScreenshotSpec(game_id="g1", device_type="iphone_6.7", headline="Hi")
        assert spec.game_id == "g1"
        assert spec.device_type == "iphone_6.7"
        assert spec.headline == "Hi"
        assert spec.subheadline == ""
        assert spec.layout == "top_text_bottom_image"
        assert spec.palette == "vibrant"
        assert spec.background_color == "#1a1a2e"
        assert spec.text_color == "#ffffff"
        assert spec.accent_color == "#e94560"
        assert spec.image_path == ""
        assert spec.dimensions == (1290, 2796)

    def test_custom_values(self) -> None:
        spec = ScreenshotSpec(
            game_id="g2", device_type="ipad", headline="Title",
            subheadline="Sub", layout="center_text", palette="dark",
            background_color="#000000", text_color="#ffffff",
            accent_color="#ff0000", image_path="/tmp/x.png",
            dimensions=(100, 200),
        )
        assert spec.layout == "center_text"
        assert spec.dimensions == (100, 200)

    def test_to_dict_serializable(self) -> None:
        spec = ScreenshotSpec(game_id="g1", device_type="iphone_6.7", headline="Hi")
        d = spec.to_dict()
        assert d["game_id"] == "g1"
        assert d["dimensions"] == [1290, 2796]  # tuple → list
        assert d["palette"] == "vibrant"


# ── 2. 设备尺寸预设 ───────────────────────────────────────


class TestDeviceDimensions:
    def test_preset_keys(self) -> None:
        keys = set(ScreenshotRenderer.DEVICE_DIMENSIONS.keys())
        assert keys == {"iphone_6.7", "iphone_6.5", "iphone_5.5", "ipad", "google_play"}

    def test_iphone_6_7_size(self) -> None:
        assert ScreenshotRenderer.DEVICE_DIMENSIONS["iphone_6.7"] == (1290, 2796)

    def test_ipad_size(self) -> None:
        assert ScreenshotRenderer.DEVICE_DIMENSIONS["ipad"] == (2048, 2732)

    def test_google_play_size(self) -> None:
        assert ScreenshotRenderer.DEVICE_DIMENSIONS["google_play"] == (1080, 1920)

    def test_all_dimensions_positive(self) -> None:
        for name, (w, h) in ScreenshotRenderer.DEVICE_DIMENSIONS.items():
            assert w > 0 and h > 0, f"{name} 尺寸非法"


# ── 3. 配色方案预设 ───────────────────────────────────────


class TestPalettes:
    def test_preset_keys(self) -> None:
        keys = set(ScreenshotRenderer.PALETTES.keys())
        assert keys == {"vibrant", "dark", "light", "gaming", "pastel"}

    def test_palette_structure(self) -> None:
        for name, pal in ScreenshotRenderer.PALETTES.items():
            assert {"bg", "text", "accent"} <= set(pal.keys()), f"{name} 缺字段"
            for key in ("bg", "text", "accent"):
                assert pal[key].startswith("#"), f"{name}.{key} 应为 hex"
                assert len(pal[key]) == 7

    def test_vibrant_palette(self) -> None:
        assert ScreenshotRenderer.PALETTES["vibrant"] == {
            "bg": "#1a1a2e", "text": "#ffffff", "accent": "#e94560",
        }


# ── 4. create_spec 辅助方法 ───────────────────────────────


class TestCreateSpec:
    def test_creates_spec_with_palette_colors(self, renderer: ScreenshotRenderer) -> None:
        spec = renderer.create_spec(
            game_id="g1", device_type="ipad", headline="Title",
            palette="gaming", layout="center_text",
        )
        assert spec.palette == "gaming"
        assert spec.background_color == "#16213e"
        assert spec.text_color == "#ffffff"
        assert spec.accent_color == "#fbb034"
        assert spec.dimensions == (2048, 2732)
        assert spec.layout == "center_text"

    def test_default_device_and_palette(self, renderer: ScreenshotRenderer) -> None:
        spec = renderer.create_spec(game_id="g1", headline="Hi")
        assert spec.device_type == "iphone_6.7"
        assert spec.palette == "vibrant"
        assert spec.dimensions == (1290, 2796)

    def test_invalid_device_raises(self, renderer: ScreenshotRenderer) -> None:
        with pytest.raises(ValueError, match="device_type"):
            renderer.create_spec(game_id="g1", device_type="unknown_device")

    def test_invalid_palette_raises(self, renderer: ScreenshotRenderer) -> None:
        with pytest.raises(ValueError, match="palette"):
            renderer.create_spec(game_id="g1", palette="unknown_palette")


# ── 5. 单个截图渲染 ───────────────────────────────────────


class TestRender:
    def test_render_produces_file(self, renderer: ScreenshotRenderer) -> None:
        spec = renderer.create_spec(
            game_id="game_a", headline="EPIC ADVENTURE",
            subheadline="Explore the world", cta="Download Now",
        )
        rendered = renderer.render(spec)
        assert isinstance(rendered, RenderedScreenshot)
        assert Path(rendered.image_path).exists()
        assert rendered.width == 1290
        assert rendered.height == 2796
        assert rendered.file_size > 0
        assert rendered.rendered_at

    def test_rendered_image_dimensions_match(self, renderer: ScreenshotRenderer) -> None:
        spec = renderer.create_spec(game_id="g1", device_type="google_play", headline="Hi")
        rendered = renderer.render(spec)
        with Image.open(rendered.image_path) as img:
            assert img.size == (1080, 1920)

    def test_rendered_is_png(self, renderer: ScreenshotRenderer) -> None:
        spec = renderer.create_spec(game_id="g1", headline="Hi")
        rendered = renderer.render(spec)
        with Image.open(rendered.image_path) as img:
            assert img.format == "PNG"

    def test_sidecar_manifest_saved(self, renderer: ScreenshotRenderer) -> None:
        spec = renderer.create_spec(game_id="g1", headline="Hi")
        rendered = renderer.render(spec)
        manifest = Path(rendered.image_path).with_suffix(".json")
        assert manifest.exists()
        import json
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["width"] == rendered.width
        assert data["spec"]["game_id"] == "g1"

    def test_render_to_dict(self, renderer: ScreenshotRenderer) -> None:
        spec = renderer.create_spec(game_id="g1", headline="Hi", cta="Play")
        rendered = renderer.render(spec)
        d = rendered.to_dict()
        assert d["spec"]["game_id"] == "g1"
        assert d["width"] == 1290
        assert "image_path" in d


# ── 6. 批量渲染 ───────────────────────────────────────────


class TestRenderBatch:
    def test_batch_renders_all(self, renderer: ScreenshotRenderer) -> None:
        specs = [
            renderer.create_spec(game_id="g1", headline="A"),
            renderer.create_spec(game_id="g2", headline="B"),
            renderer.create_spec(game_id="g3", headline="C"),
        ]
        results = renderer.render_batch(specs)
        assert len(results) == 3
        for r in results:
            assert Path(r.image_path).exists()

    def test_batch_empty(self, renderer: ScreenshotRenderer) -> None:
        assert renderer.render_batch([]) == []

    def test_batch_resilient_to_failure(self, renderer: ScreenshotRenderer) -> None:
        # 一张合法 + 一张指向不存在目录的 spec (依然能渲染, 只是没背景图)
        specs = [
            renderer.create_spec(game_id="g1", headline="A"),
            ScreenshotSpec(
                game_id="g2", device_type="iphone_6.7", headline="B",
                image_path="nonexistent.png",
            ),
        ]
        results = renderer.render_batch(specs)
        assert len(results) == 2  # 两张都应成功 (缺失背景图不影响)


# ── 7. 多种布局渲染 ───────────────────────────────────────


class TestLayouts:
    @pytest.mark.parametrize("layout", [
        "top_text_bottom_image", "center_text", "full_image_overlay",
    ])
    def test_each_layout_renders(
        self, renderer: ScreenshotRenderer, layout: str,
    ) -> None:
        spec = renderer.create_spec(
            game_id="g1", headline="Big Title", subheadline="Subtitle",
            cta="Play", layout=layout,
        )
        rendered = renderer.render(spec)
        assert Path(rendered.image_path).exists()
        assert rendered.width > 0 and rendered.height > 0

    def test_layout_with_background_image(
        self, renderer: ScreenshotRenderer, sample_image: Path,
    ) -> None:
        for layout in ("top_text_bottom_image", "center_text", "full_image_overlay"):
            spec = renderer.create_spec(
                game_id="g1", headline="With BG", layout=layout,
            )
            spec.image_path = str(sample_image)
            rendered = renderer.render(spec)
            assert Path(rendered.image_path).exists()

    def test_unknown_layout_falls_back(
        self, renderer: ScreenshotRenderer,
    ) -> None:
        spec = ScreenshotSpec(
            game_id="g1", device_type="google_play", headline="Hi",
            layout="nonexistent_layout",
        )
        # 未知布局回退到 top_text_bottom_image, 不报错
        rendered = renderer.render(spec)
        assert Path(rendered.image_path).exists()


# ── 8. 多种配色方案渲染 (像素颜色校验) ────────────────────


class TestPalettesRendering:
    def test_palette_applies_background_color(
        self, renderer: ScreenshotRenderer,
    ) -> None:
        for name, pal in ScreenshotRenderer.PALETTES.items():
            spec = renderer.create_spec(
                game_id="g1", headline="Title", palette=name,
            )
            rendered = renderer.render(spec)
            with Image.open(rendered.image_path) as img:
                # 左上角应为背景色 (top_text_bottom_image 布局顶部留白)
                pixel = img.getpixel((2, 2))
            expected = (
                int(pal["bg"][1:3], 16),
                int(pal["bg"][3:5], 16),
                int(pal["bg"][5:7], 16),
            )
            assert pixel == expected, f"palette {name} 背景色不匹配: {pixel} != {expected}"

    def test_gaming_palette_colors(self, renderer: ScreenshotRenderer) -> None:
        spec = renderer.create_spec(game_id="g1", headline="Hi", palette="gaming")
        assert spec.background_color == "#16213e"
        assert spec.accent_color == "#fbb034"


# ── 9. 可选背景图叠加 ────────────────────────────────────


class TestBackgroundImage:
    def test_top_text_with_bg_image(
        self, renderer: ScreenshotRenderer, sample_image: Path,
    ) -> None:
        spec = renderer.create_spec(
            game_id="g1", headline="Title", layout="top_text_bottom_image",
        )
        spec.image_path = str(sample_image)
        rendered = renderer.render(spec)
        assert Path(rendered.image_path).exists()
        # 图片卡区域应包含素材色 (蓝块 30,60,200)
        with Image.open(rendered.image_path) as img:
            # 卡片中心
            cx = img.width // 2
            cy = int(img.height * 0.64)
            pixel = img.getpixel((cx, cy))
        assert pixel[2] > pixel[0], "背景图蓝色块应被绘制到卡片中"

    def test_invalid_image_path_ignored(self, renderer: ScreenshotRenderer) -> None:
        spec = renderer.create_spec(game_id="g1", headline="Hi")
        spec.image_path = "does_not_exist.png"
        rendered = renderer.render(spec)
        assert Path(rendered.image_path).exists()


# ── 10. 列出已渲染截图 ────────────────────────────────────


class TestListRendered:
    def test_list_empty(self, renderer: ScreenshotRenderer) -> None:
        assert renderer.list_rendered() == []

    def test_list_all(self, renderer: ScreenshotRenderer) -> None:
        for i in range(3):
            renderer.render(renderer.create_spec(game_id=f"g{i}", headline="Hi"))
        items = renderer.list_rendered()
        assert len(items) == 3
        assert all(isinstance(i, RenderedScreenshot) for i in items)

    def test_list_filter_by_game_id(self, renderer: ScreenshotRenderer) -> None:
        renderer.render(renderer.create_spec(game_id="alpha", headline="A"))
        renderer.render(renderer.create_spec(game_id="beta", headline="B"))
        renderer.render(renderer.create_spec(game_id="alpha", headline="A2"))
        items = renderer.list_rendered(game_id="alpha")
        assert len(items) == 2
        assert all(i.spec.game_id == "alpha" for i in items)


# ── 11. 统计信息 ─────────────────────────────────────────


class TestStats:
    def test_stats_empty(self, renderer: ScreenshotRenderer) -> None:
        stats = renderer.get_stats()
        assert stats["count"] == 0
        assert stats["total_size"] == 0
        assert stats["by_game"] == {}

    def test_stats_after_renders(self, renderer: ScreenshotRenderer) -> None:
        renderer.render(renderer.create_spec(
            game_id="g1", device_type="iphone_6.7", headline="A", palette="gaming",
        ))
        renderer.render(renderer.create_spec(
            game_id="g1", device_type="ipad", headline="B", palette="dark",
        ))
        renderer.render(renderer.create_spec(
            game_id="g2", device_type="google_play", headline="C", palette="vibrant",
        ))
        stats = renderer.get_stats()
        assert stats["count"] == 3
        assert stats["total_size"] > 0
        assert stats["by_game"] == {"g1": 2, "g2": 1}
        assert stats["by_device"]["ipad"] == 1
        assert stats["by_palette"]["gaming"] == 1
        assert "output_dir" in stats


# ── 12. API 端点测试 ─────────────────────────────────────


class TestAPI:
    @pytest.fixture
    def client(self, tmp_path: Path):
        """构造使用临时输出目录的 TestClient."""
        from fastapi.testclient import TestClient
        tmp_renderer = ScreenshotRenderer(output_dir=str(tmp_path / "screenshots"))
        with patch(
            "src.market_ops.workspace.app._get_screenshot_renderer",
            return_value=tmp_renderer,
        ):
            from src.market_ops.workspace.app import app
            yield TestClient(app)

    def test_render_endpoint(self, client) -> None:
        resp = client.post("/api/screenshots/render", json={
            "game_id": "api_g1",
            "device_type": "google_play",
            "headline": "API Title",
            "subheadline": "Subtitle",
            "cta": "Play",
            "palette": "gaming",
            "layout": "center_text",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["spec"]["game_id"] == "api_g1"
        assert data["width"] == 1080
        assert data["height"] == 1920
        assert Path(data["image_path"]).exists()

    def test_render_endpoint_missing_game_id(self, client) -> None:
        resp = client.post("/api/screenshots/render", json={"headline": "Hi"})
        assert resp.status_code == 400

    def test_render_endpoint_invalid_device(self, client) -> None:
        resp = client.post("/api/screenshots/render", json={
            "game_id": "g1", "device_type": "unknown",
        })
        assert resp.status_code == 400

    def test_render_endpoint_custom_colors(self, client) -> None:
        resp = client.post("/api/screenshots/render", json={
            "game_id": "g1",
            "headline": "Hi",
            "background_color": "#112233",
            "text_color": "#aabbcc",
            "accent_color": "#ff00ff",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["spec"]["background_color"] == "#112233"
        assert data["spec"]["accent_color"] == "#ff00ff"

    def test_render_endpoint_custom_dimensions(self, client) -> None:
        resp = client.post("/api/screenshots/render", json={
            "game_id": "g1",
            "headline": "Hi",
            "dimensions": [640, 480],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["width"] == 640
        assert data["height"] == 480

    def test_render_batch_endpoint(self, client) -> None:
        resp = client.post("/api/screenshots/render-batch", json={
            "specs": [
                {"game_id": "b1", "headline": "A"},
                {"game_id": "b2", "headline": "B", "palette": "dark"},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["results"]) == 2

    def test_render_batch_empty(self, client) -> None:
        resp = client.post("/api/screenshots/render-batch", json={"specs": []})
        assert resp.status_code == 400

    def test_list_endpoint(self, client) -> None:
        client.post("/api/screenshots/render", json={
            "game_id": "list_g1", "headline": "A",
        })
        client.post("/api/screenshots/render", json={
            "game_id": "list_g2", "headline": "B",
        })
        resp = client.get("/api/screenshots")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2

    def test_list_endpoint_with_filter(self, client) -> None:
        client.post("/api/screenshots/render", json={
            "game_id": "filter_a", "headline": "A",
        })
        client.post("/api/screenshots/render", json={
            "game_id": "filter_b", "headline": "B",
        })
        resp = client.get("/api/screenshots?game_id=filter_a")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["spec"]["game_id"] == "filter_a"

    def test_stats_endpoint(self, client) -> None:
        client.post("/api/screenshots/render", json={
            "game_id": "stat_g1", "headline": "A",
        })
        resp = client.get("/api/screenshots/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["by_game"]["stat_g1"] == 1

    def test_devices_endpoint(self, client) -> None:
        resp = client.get("/api/screenshots/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert data["iphone_6.7"] == [1290, 2796]
        assert "ipad" in data

    def test_palettes_endpoint(self, client) -> None:
        resp = client.get("/api/screenshots/palettes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["vibrant"]["bg"] == "#1a1a2e"
        assert "gaming" in data
