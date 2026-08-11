"""Phase 2.1.6.1 — 单张硬化 Prompt 生成测试。

用 creative_prompting 的硬化 Prompt（Visual Asset Only + 硬负面约束 + 4 模式构图）
直接调 Lovart 生成 1 张，验证：
  - 不生成文字 / Logo / CTA / 伪 UI
  - 1:1 方形、玩法清晰、女巫作为 host 而非 portrait
  - 与 winner 风格一致（用 winner_001 做参考附件）

用法:
  python scripts/gen_hardened_one.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from creative_prompting.prompt_template import build_prompt, DEFAULT_GAME
from creative_prompting.gameplay_pattern import GameplayPattern
from market_ops.clients.lovart import LovartClient, download_image

OUT = ROOT / "output" / "phase2_1_6_1" / "test_one"
OUT.mkdir(parents=True, exist_ok=True)

WINNER = ROOT / "output" / "phase2_1_5" / "real_validation" / "winner_reference" / "winner_001.png"

# 测试模式：MERGE（最典型的 winner 结构，也最能验证「无文字伪 UI」）
pattern = GameplayPattern.MERGE
prompt = build_prompt(DEFAULT_GAME, pattern)

print("=" * 70)
print("HARDENED PROMPT (pattern = %s)" % pattern.value)
print("=" * 70)
print(prompt)
print("=" * 70)

# 参考附件：用真实 winner 做风格锚定（winner 本身无 overlay 文字）
attachments = [str(WINNER)] if WINNER.exists() else None
print(f"Winner reference: {'YES -> ' + str(WINNER) if attachments else 'NOT FOUND, generating prompt-only'}")

print("\n[1/3] Initializing Lovart client ...")
client = LovartClient()

print("[2/3] Submitting generation (this blocks until done, up to 5 min) ...")
result = client.generate_image(prompt, attachments=attachments)
print(f"  status = {result.status} | images = {len(result.image_urls)} | elapsed = {result.elapsed_sec:.1f}s")

if not result.image_urls:
    print("\n[!] NO IMAGE RETURNED")
    print("assistant_text:", result.assistant_text[:600])
    raise SystemExit(1)

print("[3/3] Downloading result ...")
dest = OUT / "hardened_001.png"
download_image(result.image_urls[0], dest)
(OUT / "hardened_001_prompt.txt").write_text(prompt, encoding="utf-8")
print(f"\nDONE -> {dest}")
print(f"Prompt saved -> {OUT / 'hardened_001_prompt.txt'}")
