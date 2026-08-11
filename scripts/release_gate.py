"""Blueprint Engine V4.4.1 RC1 Release Gate 验证脚本

自动校验所有 Release Gate 项，确保 Blueprint 达到 Production Ready。
"""
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "video_blueprint"
VARIANT_DIR = OUTPUT_DIR / "V001"

SHAKE_VALUES = {"none", "light", "medium", "heavy"}
CAMERA_SPEC_KEYS = {"lens", "move", "move_speed", "zoom", "focus", "depth", "shake", "frame_rate", "fov"}
PROMPT_KEYS = {"image_prompt", "video_prompt", "motion_prompt", "character_prompt", "lighting_prompt", "negative_prompt"}
OLD_PROMPT_KEYS = {"scene_prompt", "camera_prompt", "style_prompt"}
SUBTITLE_KEYS = {"caption", "voice", "popup", "reward_text", "cta_overlay", "font", "color", "animation", "timing"}
EDITING_KEYS = {"exposure", "contrast", "highlight", "shadow", "temperature", "tint", "saturation", "sharpness", "film_grain", "bloom", "chromatic", "motion_blur", "particles", "lut"}
CREATIVE_REVIEW_KEYS = {"facebook_score", "hook_score", "story_score", "emotion_score", "camera_score", "editing_score", "visual_score", "predicted_ctr", "predicted_ipm", "predicted_roas", "overall_score"}
RESOURCE_KEYS = {"background", "character", "creature", "fx", "particles", "music", "ui", "lut", "environment"}
REQUIRED_FILES = [
    "shot_list.json",
    "asset_spec.json",
    "camera_spec.json",
    "editing_spec.json",
    "subtitle_spec.json",
    "music_spec.json",
    "prompt_package.json",
    "creative_review.json",
    "quality_report.json",
    "creative_blueprint.md",
]


class ValidationError:
    def __init__(self, schema: str, file: str, field: str, reason: str):
        self.schema = schema
        self.file = file
        self.field = field
        self.reason = reason


class Validator:
    def __init__(self):
        self.errors: List[ValidationError] = []
    
    def check(self, condition: bool, schema: str, file: str, field: str, reason: str) -> None:
        if not condition:
            self.errors.append(ValidationError(schema, file, field, reason))
    
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    def get_errors_by_schema(self, schema: str) -> List[ValidationError]:
        return [e for e in self.errors if e.schema == schema]


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_camera_schema(v: Validator) -> None:
    file = "camera_spec.json"
    path = VARIANT_DIR / file
    if not path.exists():
        v.check(False, "Camera Schema", file, "file", "File not found")
        return
    try:
        data = load_json(path)
        for spec in data.get("specs", []):
            for key in CAMERA_SPEC_KEYS:
                v.check(key in spec, "Camera Schema", file, key, "Expected field present | Got missing")
            shake = spec.get("shake")
            v.check(isinstance(shake, str), "Camera Schema", file, "shake", f"Expected String (none/light/medium/heavy) | Got: {shake!r}")
            if isinstance(shake, str):
                v.check(shake in SHAKE_VALUES, "Camera Schema", file, "shake", f"Expected one of {SHAKE_VALUES} | Got: {shake!r}")
            fr = spec.get("frame_rate")
            v.check(isinstance(fr, int) and fr == 60, "Camera Schema", file, "frame_rate", f"Expected Integer 60 | Got: {fr!r}")
    except Exception as e:
        v.check(False, "Camera Schema", file, "parse", f"Parse Error: {str(e)}")


def validate_shot_schema(v: Validator) -> None:
    file = "shot_list.json"
    path = VARIANT_DIR / file
    if not path.exists():
        v.check(False, "Shot Schema", file, "file", "File not found")
        return
    try:
        data = load_json(path)
        for shot in data.get("shots", []):
            shot_id = shot.get("shot_id", "")
            v.check(re.match(r"^S\d+$", shot_id), "Shot Schema", file, "shot_id", f"Expected ^S\\d+$ | Got: {shot_id!r}")
            camera = shot.get("camera")
            v.check(isinstance(camera, dict), "Shot Schema", file, "camera", f"Expected CameraSpec Object | Got: {type(camera).__name__}")
            if isinstance(camera, dict):
                for key in CAMERA_SPEC_KEYS:
                    v.check(key in camera, "Shot Schema", file, f"camera.{key}", "Expected field present | Got missing")
            fx = shot.get("fx")
            v.check(isinstance(fx, list), "Shot Schema", file, "fx", f"Expected Array | Got: {type(fx).__name__}")
            ar = shot.get("asset_reference")
            v.check(ar, "Shot Schema", file, "asset_reference", "Expected non-empty | Got: empty")
    except Exception as e:
        v.check(False, "Shot Schema", file, "parse", f"Parse Error: {str(e)}")


def validate_asset_schema(v: Validator) -> None:
    file = "asset_spec.json"
    path = VARIANT_DIR / file
    if not path.exists():
        v.check(False, "Asset Schema", file, "file", "File not found")
        return
    try:
        data = load_json(path)
        for mapping in data.get("mappings", []):
            ar = mapping.get("asset_reference")
            v.check(ar, "Asset Schema", file, "asset_reference", "Expected non-empty | Got: empty")
            for key in RESOURCE_KEYS:
                val = mapping.get(key)
                v.check(val, "Asset Schema", file, key, "Expected non-empty | Got: empty")
    except Exception as e:
        v.check(False, "Asset Schema", file, "parse", f"Parse Error: {str(e)}")


def validate_prompt_schema(v: Validator) -> None:
    file = "prompt_package.json"
    path = VARIANT_DIR / file
    if not path.exists():
        v.check(False, "Prompt Schema", file, "file", "File not found")
        return
    try:
        data = load_json(path)
        for pkg in data.get("packages", []):
            pkg_keys = set(pkg.keys())
            for old_key in OLD_PROMPT_KEYS:
                v.check(old_key not in pkg_keys, "Prompt Schema", file, old_key, "Forbidden field | Present")
            for key in PROMPT_KEYS:
                v.check(key in pkg_keys, "Prompt Schema", file, key, "Expected field present | Got missing")
                val = pkg.get(key)
                v.check(val, "Prompt Schema", file, key, "Expected non-empty | Got: empty")
    except Exception as e:
        v.check(False, "Prompt Schema", file, "parse", f"Parse Error: {str(e)}")


def validate_editing_schema(v: Validator) -> None:
    file = "editing_spec.json"
    path = VARIANT_DIR / file
    if not path.exists():
        v.check(False, "Editing Schema", file, "file", "File not found")
        return
    try:
        data = load_json(path)
        for scene in data.get("scenes", []):
            for key in EDITING_KEYS:
                v.check(key in scene, "Editing Schema", file, key, "Expected field present | Got missing")
            mb = scene.get("motion_blur")
            v.check(isinstance(mb, float), "Editing Schema", file, "motion_blur", f"Expected Float | Got: {type(mb).__name__}")
            if isinstance(mb, float):
                v.check(0 <= mb <= 1, "Editing Schema", file, "motion_blur", f"Expected 0~1 | Got: {mb}")
    except Exception as e:
        v.check(False, "Editing Schema", file, "parse", f"Parse Error: {str(e)}")


def validate_subtitle_schema(v: Validator) -> None:
    file = "subtitle_spec.json"
    path = VARIANT_DIR / file
    if not path.exists():
        v.check(False, "Subtitle Schema", file, "file", "File not found")
        return
    try:
        data = load_json(path)
        for scene in data.get("scenes", []):
            for key in SUBTITLE_KEYS:
                val = scene.get(key)
                v.check(key in scene, "Subtitle Schema", file, key, "Expected field present | Got missing")
                v.check(val, "Subtitle Schema", file, key, "Expected non-empty | Got: empty")
    except Exception as e:
        v.check(False, "Subtitle Schema", file, "parse", f"Parse Error: {str(e)}")


def validate_music_schema(v: Validator) -> None:
    file = "music_spec.json"
    path = VARIANT_DIR / file
    if not path.exists():
        v.check(False, "Music Schema", file, "file", "File not found")
        return
    try:
        data = load_json(path)
        segments = data.get("segments", [])
        for i, segment in enumerate(segments):
            for key in ["genre", "mood", "energy", "bpm"]:
                val = segment.get(key)
                v.check(val, "Music Schema", file, key, "Expected non-empty | Got: empty")
            bm = segment.get("beat_marker", [])
            v.check(isinstance(bm, list), "Music Schema", file, "beat_marker", f"Expected Array | Got: {type(bm).__name__}")
            if isinstance(bm, list):
                v.check(len(bm) > 0, "Music Schema", file, "beat_marker", "Expected non-empty | Got: empty")
                v.check(bm == sorted(bm), "Music Schema", file, "beat_marker", "Expected sorted | Got: unsorted")
                start = segment.get("start", 0)
                end = segment.get("end", float("inf"))
                for marker in bm:
                    v.check(start <= marker <= end, "Music Schema", file, "beat_marker", f"Expected in [{start},{end}] | Got: {marker}")
        if len(segments) > 1:
            for i in range(len(segments) - 1):
                v.check(segments[i].get("end", 0) == segments[i + 1].get("start", 0), "Music Schema", file, "timeline", f"Expected continuous | Gap between segment {i+1} and {i+2}")
    except Exception as e:
        v.check(False, "Music Schema", file, "parse", f"Parse Error: {str(e)}")


def validate_creative_review(v: Validator) -> None:
    file = "creative_review.json"
    path = VARIANT_DIR / file
    if not path.exists():
        v.check(False, "Creative Review", file, "file", "File not found")
        return
    try:
        data = load_json(path)
        for key in CREATIVE_REVIEW_KEYS:
            val = data.get(key)
            v.check(key in data, "Creative Review", file, key, "Expected field present | Got missing")
            v.check(val is not None, "Creative Review", file, key, "Expected non-empty | Got: None")
    except Exception as e:
        v.check(False, "Creative Review", file, "parse", f"Parse Error: {str(e)}")


def validate_quality_report(v: Validator) -> None:
    file = "quality_report.json"
    path = VARIANT_DIR / file
    if not path.exists():
        v.check(False, "Quality Report", file, "file", "File not found")
        return
    try:
        data = load_json(path)
        for key in ["passed", "issues", "warnings", "suggestions"]:
            v.check(key in data, "Quality Report", file, key, "Expected field present | Got missing")
    except Exception as e:
        v.check(False, "Quality Report", file, "parse", f"Parse Error: {str(e)}")


def validate_dashboard(v: Validator) -> None:
    file = "dashboard.txt"
    path = OUTPUT_DIR / file
    if not path.exists():
        v.check(False, "Dashboard", file, "file", "File not found")
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        checks = [
            ("Lens 使用统计", "Lens Usage"),
            ("运镜统计", "Camera Move Usage"),
            ("平均预测 CTR", "Average CTR"),
            ("平均预测 ROAS", "Average ROAS"),
            ("Top Blueprint", "Top Blueprint"),
            ("Bottom Blueprint", "Bottom Blueprint"),
        ]
        for check, label in checks:
            v.check(check in content, "Dashboard", file, label, "Expected present | Got missing")
    except Exception as e:
        v.check(False, "Dashboard", file, "read", f"Read Error: {str(e)}")


def validate_markdown(v: Validator) -> None:
    file = "creative_blueprint.md"
    path = VARIANT_DIR / file
    if not path.exists():
        v.check(False, "Markdown", file, "file", "File not found")
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        v.check("shake['enabled']" not in content and 'shake["enabled"]' not in content, "Markdown", file, "shake", "Forbidden format | Got shake['enabled']")
        
        camera_items = ["Lens", "Move", "Move Speed", "Zoom", "Focus", "Depth", "Shake", "Frame Rate", "FOV"]
        for item in camera_items:
            v.check(item in content, "Markdown", file, f"Camera.{item}", "Expected present | Got missing")
        
        v.check("Scene Prompt" not in content, "Markdown", file, "Scene Prompt", "Forbidden | Present")
        v.check("Camera Prompt" not in content, "Markdown", file, "Camera Prompt", "Forbidden | Present")
        v.check("Style Prompt" not in content, "Markdown", file, "Style Prompt", "Forbidden | Present")
        
        prompt_items = ["Image Prompt", "Video Prompt", "Motion Prompt", "Character Prompt", "Lighting Prompt", "Negative Prompt"]
        for item in prompt_items:
            v.check(item in content, "Markdown", file, item, "Expected present | Got missing")
        
    except Exception as e:
        v.check(False, "Markdown", file, "read", f"Read Error: {str(e)}")


def validate_blueprint_api(v: Validator) -> None:
    file = "blueprint.json"
    path = VARIANT_DIR / file
    if not path.exists():
        v.check(False, "Blueprint API", file, "file", "File not found")
        return
    try:
        data = load_json(path)
        v.check(data.get("variant_id"), "Blueprint API", file, "variant_id", "Expected non-empty | Got: empty")
        v.check(data.get("dna"), "Blueprint API", file, "dna", "Expected non-empty | Got: empty")
        v.check(data.get("segments"), "Blueprint API", file, "segments", "Expected non-empty | Got: empty")
    except Exception as e:
        v.check(False, "Blueprint API", file, "parse", f"Parse Error: {str(e)}")


def validate_camera_language(v: Validator) -> None:
    cam_lang_path = ROOT / "src" / "market_ops" / "video_blueprint" / "camera_language.py"
    v.check(not cam_lang_path.exists(), "Camera Language", "camera_language.py", "file", "Forbidden | Present")
    
    import_path = ROOT / "src" / "market_ops" / "video_blueprint" / "__init__.py"
    if import_path.exists():
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                content = f.read()
                v.check("camera_language" not in content, "Camera Language", "__init__.py", "camera_language", "Forbidden reference | Present")
        except Exception as e:
            v.check(False, "Camera Language", "__init__.py", "read", f"Read Error: {str(e)}")


def validate_file_names(v: Validator) -> None:
    for fname in REQUIRED_FILES:
        path = VARIANT_DIR / fname
        v.check(path.exists(), "File Names", fname, "file", "Expected present | Got missing")


VALIDATION_FUNCTIONS = [
    ("Camera Schema", validate_camera_schema),
    ("Shot Schema", validate_shot_schema),
    ("Asset Schema", validate_asset_schema),
    ("Prompt Schema", validate_prompt_schema),
    ("Editing Schema", validate_editing_schema),
    ("Subtitle Schema", validate_subtitle_schema),
    ("Music Schema", validate_music_schema),
    ("Creative Review", validate_creative_review),
    ("Quality Report", validate_quality_report),
    ("Dashboard", validate_dashboard),
    ("Markdown", validate_markdown),
    ("Blueprint API", validate_blueprint_api),
    ("Camera Language", validate_camera_language),
    ("File Names", validate_file_names),
]


def main() -> int:
    print("=" * 60)
    print("Blueprint Engine V4.4.1 RC1 Release Gate")
    print("=" * 60)
    
    validator = Validator()
    
    for name, fn in VALIDATION_FUNCTIONS:
        fn(validator)
    
    passed_count = 0
    for name, _ in VALIDATION_FUNCTIONS:
        errors = validator.get_errors_by_schema(name)
        status = "PASS" if not errors else "FAIL"
        print(f"\n{name:20} {status}")
        for err in errors:
            print("\nFAIL")
            print("\nFile:")
            print(err.file)
            print("\nField:")
            print(err.field)
            print("\nReason:")
            if " | Got:" in err.reason:
                reason_part, got_part = err.reason.split(" | Got:", 1)
                print(reason_part)
                print("\nGot:")
                print(got_part.strip())
            else:
                print(err.reason)
        if not errors:
            passed_count += 1
    
    print("\n" + "=" * 60)
    print("\nTOTAL")
    print("\n" + str(passed_count) + " / " + str(len(VALIDATION_FUNCTIONS)) + " PASS")
    print("\n" + "=" * 60)
    
    if validator.has_errors():
        print("\nFAILED")
        print("\nTotal Errors:")
        print("\n" + str(len(validator.errors)))
        print("\n" + "=" * 60)
        return 1
    else:
        print("\nBlueprint Engine V4.4.1 RC1")
        print("\nProduction Ready")
        return 0


if __name__ == "__main__":
    sys.exit(main())