import shutil
from pathlib import Path

source_dirs = [Path("D:/T1"), Path("D:/p4素材")]
target_dir = Path("D:/project_slim/output/P04_videos_from_eagle")
target_dir.mkdir(parents=True, exist_ok=True)

copied = 0
skipped = 0

for src_dir in source_dirs:
    if not src_dir.exists():
        continue
    for video_file in src_dir.rglob("*"):
        if video_file.is_file() and video_file.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
            dst_path = target_dir / video_file.name
            
            if dst_path.exists():
                skipped += 1
                continue
            
            print(f"COPY: {video_file.name} ({video_file.stat().st_size / 1024 / 1024:.1f} MB)")
            shutil.copy2(video_file, dst_path)
            copied += 1

print(f"\nDone! Copied: {copied}, Skipped (duplicates): {skipped}")
print(f"Output directory: {target_dir}")

# List final contents
final_files = sorted([f for f in target_dir.iterdir() if f.is_file()])
print(f"\nTotal unique videos in target: {len(final_files)}")
for f in final_files:
    print(f"  {f.name}")
