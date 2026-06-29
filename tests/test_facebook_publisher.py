"""FacebookPublisher 单元测试 — mock Facebook API

注：daily_runner 集成测试因项目既有的数字前缀导入问题（SyntaxError）
暂时跳过。14_publish/facebook_publisher.py 自身无此问题，可独立测试。
"""
from __future__ import annotations

import importlib
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 使用 importlib 绕过 Python 数字前缀模块名的语法限制
_pub_mod = importlib.import_module(
    "market_ops.creative_growth_loop.14_publish.facebook_publisher"
)
FacebookPublisher = _pub_mod.FacebookPublisher
PublishResult = _pub_mod.PublishResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def publisher():
    return FacebookPublisher(
        access_token="test_token",
        ad_account_id="act_123456",
        api_version="v22.0",
        page_id="123456789",
    )


@pytest.fixture
def temp_image_dir():
    """Create temp dir with 3 fake PNG images."""
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(3):
            path = Path(tmpdir) / f"image_{i+1:03d}.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\nfake_png_content")
        yield tmpdir


# ---------------------------------------------------------------------------
# Test: Image Upload
# ---------------------------------------------------------------------------

def test_upload_images_success(publisher, temp_image_dir):
    import glob
    image_paths = sorted(glob.glob(f"{temp_image_dir}/*.png"))

    with patch("requests.post") as mock_post:
        mock_responses = []
        for path in image_paths:
            img_name = Path(path).name
            resp = MagicMock()
            resp.json.return_value = {
                "images": {img_name: {"hash": f"hash_{img_name.replace('.png', '')}"}}
            }
            resp.raise_for_status = MagicMock()
            mock_responses.append(resp)
        mock_post.side_effect = mock_responses

        hashes = publisher.upload_images(image_paths)

        assert len(hashes) == 3
        assert "hash_image_001" in hashes


def test_upload_images_partial_failure(publisher, temp_image_dir):
    import glob
    image_paths = sorted(glob.glob(f"{temp_image_dir}/*.png"))

    call_count = [0]

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:
            resp = MagicMock()
            resp.raise_for_status.side_effect = Exception("Upload timeout")
            return resp
        resp = MagicMock()
        files = kwargs.get("files", {})
        fname_tuple = files.get("filename", ("img",))
        fname = fname_tuple[0] if isinstance(fname_tuple, tuple) else str(fname_tuple)
        resp.json.return_value = {"images": {fname: {"hash": f"hash_{call_count[0]}"}}}
        resp.raise_for_status = MagicMock()
        return resp

    with patch("requests.post", side_effect=side_effect):
        hashes = publisher.upload_images(image_paths)

    assert len(hashes) == 2


# ---------------------------------------------------------------------------
# Test: Create Ad Creatives
# ---------------------------------------------------------------------------

def test_create_ad_creatives_success(publisher):
    image_hashes = ["hash_a", "hash_b", "hash_c"]
    headlines = ["Headline A", "Headline B", "Headline C"]
    primary_texts = ["Text A", "Text B", "Text C"]

    with patch("requests.post") as mock_post:
        mock_responses = []
        for i in range(3):
            resp = MagicMock()
            resp.json.return_value = {"id": f"creative_{i+1}"}
            resp.raise_for_status = MagicMock()
            mock_responses.append(resp)
        mock_post.side_effect = mock_responses

        creative_ids = publisher.create_ad_creatives(
            image_hashes=image_hashes,
            headlines=headlines,
            primary_texts=primary_texts,
        )

        assert len(creative_ids) == 3
        assert creative_ids == ["creative_1", "creative_2", "creative_3"]


def test_create_ad_creatives_headlines_auto_fill(publisher):
    image_hashes = ["hash_a", "hash_b", "hash_c"]
    headlines = ["Only One Headline"]
    primary_texts = [""]

    with patch("requests.post") as mock_post:
        mock_responses = []
        for i in range(3):
            resp = MagicMock()
            resp.json.return_value = {"id": f"crt_{i}"}
            resp.raise_for_status = MagicMock()
            mock_responses.append(resp)
        mock_post.side_effect = mock_responses

        creative_ids = publisher.create_ad_creatives(
            image_hashes=image_hashes,
            headlines=headlines,
            primary_texts=primary_texts,
        )

        assert len(creative_ids) == 3


def test_create_ad_creatives_empty_hashes(publisher):
    """空 image_hashes → 返回空列表"""
    result = publisher.create_ad_creatives(
        image_hashes=[],
        headlines=[],
        primary_texts=[],
    )
    assert result == []


# ---------------------------------------------------------------------------
# Test: Create Ads
# ---------------------------------------------------------------------------

def test_create_ads_success(publisher):
    creative_ids = ["creative_1", "creative_2", "creative_3"]
    adset_id = "adset_999"
    names = ["Ad A", "Ad B", "Ad C"]

    with patch("requests.post") as mock_post:
        mock_responses = []
        for i in range(3):
            resp = MagicMock()
            resp.json.return_value = {"id": f"ad_{i+1}"}
            resp.raise_for_status = MagicMock()
            mock_responses.append(resp)
        mock_post.side_effect = mock_responses

        ad_ids = publisher.create_ads(
            creative_ids=creative_ids,
            adset_id=adset_id,
            names=names,
        )

        assert len(ad_ids) == 3
        assert ad_ids == ["ad_1", "ad_2", "ad_3"]


def test_create_ads_default_paused(publisher):
    creative_ids = ["cr1"]
    adset_id = "as1"

    with patch("requests.post") as mock_post:
        resp = MagicMock()
        resp.json.return_value = {"id": "ad_1"}
        resp.raise_for_status = MagicMock()
        mock_post.return_value = resp

        publisher.create_ads(
            creative_ids=creative_ids,
            adset_id=adset_id,
            names=["Test Ad"],
        )

        call_kwargs = mock_post.call_args
        data = call_kwargs[1]["data"]
        assert "PAUSED" in str(data)


def test_create_ads_active_status(publisher):
    """status=ACTIVE 时广告直接生效"""
    creative_ids = ["cr1"]
    adset_id = "as1"

    with patch("requests.post") as mock_post:
        resp = MagicMock()
        resp.json.return_value = {"id": "ad_1"}
        resp.raise_for_status = MagicMock()
        mock_post.return_value = resp

        publisher.create_ads(
            creative_ids=creative_ids,
            adset_id=adset_id,
            names=["Test Ad"],
            status="ACTIVE",
        )

        call_kwargs = mock_post.call_args
        data = call_kwargs[1]["data"]
        assert "ACTIVE" in str(data)


def test_create_ads_empty_creatives(publisher):
    """空 creative_ids → 返回空列表"""
    result = publisher.create_ads(
        creative_ids=[],
        adset_id="as1",
        names=[],
    )
    assert result == []


# ---------------------------------------------------------------------------
# Test: End-to-End publish_and_monitor
# ---------------------------------------------------------------------------

def test_publish_and_monitor_missing_adset(publisher, temp_image_dir):
    result = publisher.publish_and_monitor(
        image_dir=temp_image_dir,
        campaign_config={},
    )

    assert not result.success
    assert len(result.errors) == 1
    assert "adset_id" in result.errors[0]


def test_publish_and_monitor_empty_dir(publisher):
    with tempfile.TemporaryDirectory() as empty_dir:
        result = publisher.publish_and_monitor(
            image_dir=empty_dir,
            campaign_config={"adset_id": "as_123"},
        )

        assert not result.success
        assert "No PNG images found" in result.errors[0]


def test_publish_and_monitor_full_flow(publisher, temp_image_dir):
    campaign_config = {
        "adset_id": "adset_888",
        "headlines": ["Test Headline"],
        "primary_texts": ["Test Body"],
        "page_id": "999",
    }

    with patch.object(publisher, "upload_images") as mock_upload, \
         patch.object(publisher, "create_ad_creatives") as mock_creatives, \
         patch.object(publisher, "create_ads") as mock_ads:

        mock_upload.return_value = ["h1", "h2", "h3"]
        mock_creatives.return_value = ["c1", "c2", "c3"]
        mock_ads.return_value = ["a1", "a2", "a3"]

        result = publisher.publish_and_monitor(
            image_dir=temp_image_dir,
            campaign_config=campaign_config,
        )

        assert result.success
        assert result.uploaded_count == 3
        assert result.creative_count == 3
        assert result.ad_count == 3
        mock_upload.assert_called_once()
        mock_creatives.assert_called_once()
        mock_ads.assert_called_once()


def test_publish_and_monitor_upload_failure(publisher, temp_image_dir):
    """上传全部失败时提前终止"""
    campaign_config = {"adset_id": "adset_888"}

    with patch.object(publisher, "upload_images") as mock_upload, \
         patch.object(publisher, "create_ad_creatives") as mock_creatives:

        mock_upload.return_value = []  # all uploads fail

        result = publisher.publish_and_monitor(
            image_dir=temp_image_dir,
            campaign_config=campaign_config,
        )

        assert not result.success
        assert "All image uploads failed" in result.errors[0]
        mock_creatives.assert_not_called()


def test_publish_and_monitor_auto_activate(publisher, temp_image_dir):
    """auto_activate=True → ads 以 ACTIVE 状态创建"""
    campaign_config = {
        "adset_id": "adset_888",
        "auto_activate": True,
    }

    with patch.object(publisher, "upload_images") as mock_upload, \
         patch.object(publisher, "create_ad_creatives") as mock_creatives, \
         patch.object(publisher, "create_ads") as mock_ads:

        mock_upload.return_value = ["h1", "h2"]
        mock_creatives.return_value = ["c1", "c2"]
        mock_ads.return_value = ["a1", "a2"]

        result = publisher.publish_and_monitor(
            image_dir=temp_image_dir,
            campaign_config=campaign_config,
        )

        assert result.success
        # create_ads should have been called with status="ACTIVE"
        call_kwargs = mock_ads.call_args
        assert call_kwargs[1]["status"] == "ACTIVE"


# ---------------------------------------------------------------------------
# Test: PublishResult dataclass
# ---------------------------------------------------------------------------

def test_publishresult_serialize():
    result = PublishResult(
        run_id="test_001",
        ad_account_id="123",
        uploaded_count=5,
        creative_count=5,
        ad_count=3,
        image_hashes=["h1", "h2"],
        creative_ids=["c1", "c2"],
        ad_ids=["a1", "a2"],
        errors=["creative_3 failed"],
        published_at="2026-06-23T12:00:00",
    )

    d = result.to_dict()
    assert d["run_id"] == "test_001"
    assert d["uploaded_count"] == 5
    assert not result.success  # errors exist


def test_publishresult_success_no_errors():
    result = PublishResult(
        run_id="ok",
        ad_account_id="123",
        uploaded_count=2,
        creative_count=2,
        ad_count=2,
        image_hashes=["h1"],
        creative_ids=["c1"],
        ad_ids=["a1"],
    )
    assert result.success


def test_publishresult_success_zero_ads():
    """ad_count=0 即使无错误也不算成功"""
    result = PublishResult(
        run_id="zero",
        ad_account_id="123",
        uploaded_count=1,
        creative_count=0,
        ad_count=0,
    )
    assert not result.success
