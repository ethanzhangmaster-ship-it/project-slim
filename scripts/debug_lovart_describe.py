"""调试Lovart describe_image - 单图测试"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Load .env
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from market_ops.clients.lovart import LovartClient

# 用P04花费最高的图测试
TEST_IMAGE = ROOT / "output" / "facebook_top_creatives" / "P04" / "P4-And-T1-深度挖掘-图片1-1229_1620939025566756.png"

print(f"测试图片: {TEST_IMAGE}")
print(f"存在: {TEST_IMAGE.exists()}")
print(f"大小: {TEST_IMAGE.stat().st_size // 1024} KB")

print("\n初始化LovartClient...")
try:
    client = LovartClient(mode="fast")
    print(f"OK: AK={client._ak[:8]}... base={client._base}")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)

print("\n调用 describe_image...")
t0 = time.time()
try:
    result = client.describe_image(TEST_IMAGE, project="P04")
    elapsed = time.time() - t0
    print(f"耗时: {elapsed:.1f}s")
    print(f"结果keys: {list(result.keys())}")

    if "error" in result:
        print(f"ERROR: {result['error']}")
        if "assistant_text" in result:
            print(f"assistant_text: {result['assistant_text'][:300]}")
    else:
        print("\n=== Visual DNA ===")
        for k, v in result.items():
            if not k.startswith("_"):
                print(f"  {k}: {v}")
except Exception as e:
    elapsed = time.time() - t0
    print(f"EXCEPTION after {elapsed:.1f}s: {e}")
    import traceback
    traceback.print_exc()
