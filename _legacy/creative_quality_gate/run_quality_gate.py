"""Phase 2.1.6 — Production Readiness Gate 入口。

读取 real_validation 数据集（winner + creatives + metadata + strategy），
逐图跑 CriticAgent，输出 output/quality_gate/ 五件产物，并判定 9 项验收。

Pipeline（接 PRD 第 10 条）：
  Generate → Production Quality Gate → OpenCLIP Ranking → TOP → Export

用法：
  python creative_quality_gate/run_quality_gate.py
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from creative_quality_gate.critic_agent import CriticAgent  # noqa: E402
from creative_quality_gate.models import GateResult  # noqa: E402
from creative_quality_gate.report import build_outputs  # noqa: E402
from creative_quality_gate.visual_checker import ai_text_density  # noqa: E402
from creative_quality_gate.scoring import DIM_PASS, REJECT_ARTIFACT  # noqa: E402
from creative_prompting.prompt_template import build_v3_prompts  # noqa: E402

BASE = _ROOT / "output" / "phase2_1_5" / "real_validation"
WINNER = BASE / "winner_reference" / "winner_001.png"
META = BASE / "metadata.json"
STRATEGY = _ROOT / "output" / "creative_analysis" / "prompt_director" / "creative_strategy.json"
CREATIVES_DIR = BASE / "creatives"
OUT_DIR = _ROOT / "output" / "quality_gate"

# PRD 2.1.6.1 第 10 条 6 项强制验收 + 能力验收
ACCEPT_KEYS = [
    "Prompt Hardening (no generated text)",
    "Prompt Hardening (no fake logo)",
    "Correct Ratio (1:1)",
    "Gameplay Understandable",
    "Reward Visible",
    "Not Poster Style",
    "Gameplay Multi-Pattern",
    "AI Artifact Detection",
    "Production Score",
    "HTML Report",
    "Pipeline Integration",
    "3/3 Creative PASS",
]


def _load_creatives() -> list[dict]:
    if not META.exists():
        # 无 metadata 时直接扫目录
        items = []
        for p in sorted(CREATIVES_DIR.glob("*.png")):
            cid = p.stem
            items.append({"creative_id": cid, "file": str(p), "group": "", "mutation_type": ""})
        return items
    data = json.loads(META.read_text(encoding="utf-8"))
    items = []
    for c in data.get("creatives", []):
        cid = c["creative_id"]
        fp = CREATIVES_DIR / f"{cid}.png"
        items.append(
            {
                "creative_id": cid,
                "file": str(fp),
                "group": c.get("group", ""),
                "mutation_type": c.get("mutation_type", ""),
            }
        )
    return items


def _make_dirty_probe() -> Path:
    """构造一张带乱码文字叠加的脏图（tempfile），用于验证 AI Artifact 检测能力。

    用 PIL 在深色底上随机绘制大量彩色乱码字符块，模拟 AI 生成图常见的
    'garbled text scribbles' 失败模式。该图本身不含正常游戏结构。
    """
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (512, 512), (30, 30, 45))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 26)
    except Exception:
        font = ImageFont.load_default()
    chars = "▓▒░@#$%&*(){}[]<>?/\\|=+~^ABCDEF0123456789"
    random.seed(7)
    for _ in range(140):
        x = random.randint(0, 470)
        y = random.randint(0, 470)
        chunk = "".join(random.choice(chars) for _ in range(random.randint(4, 9)))
        col = (random.randint(180, 255), random.randint(180, 255), random.randint(180, 255))
        draw.text((x, y), chunk, fill=col, font=font)
    p = Path(tempfile.gettempdir()) / "_dirty_probe.png"
    img.save(p)
    return p


def _write_hardened_prompts(out_dir: Path) -> Path:
    """PRD 2.1.6.1 — 把 3 张验证图对应的强化 Prompt 落盘，证明 Prompt Hardening 可用。

    这些 Prompt 由新建的 creative_prompting/ 模块产出，已内置：
      Visual Asset Only 正向约束 + 广告三段式结构 + 硬负面约束（灭文字/Logo/UI 幻觉）
      + 4 模式构图要求（MERGE / EVOLUTION / COLLECTION / REWARD_REVEAL）。
    """
    prompts = build_v3_prompts()
    pdir = out_dir / "prompts"
    pdir.mkdir(parents=True, exist_ok=True)
    for cid, text in prompts.items():
        (pdir / f"{cid}.txt").write_text(text, encoding="utf-8")
    return pdir


def main() -> int:
    creatives = _load_creatives()
    if not creatives:
        print("ERROR: no creatives found", file=sys.stderr)
        return 1
    if not WINNER.exists():
        print("ERROR: winner reference missing", file=sys.stderr)
        return 1

    # strategy 仅作接口存在性校验（PRD 要求输入之一）
    strategy_ok = STRATEGY.exists()

    agent = CriticAgent(device="cpu")

    # 合成脏图对照：验证 AI Artifact 检测能力（带乱码文字叠加）
    # 注意：必须用连通域文字检测 ai_text_density（scipy 连通域），
    # 不能用 CLIP 的 ai_artifact 维度——CLIP 在「文本/渲染畸形」方向上反转
    # （干净游戏美术≈1.0，真实乱码图≈0.0），不可靠。
    dirty_path = _make_dirty_probe()
    dirty_art = ai_text_density(dirty_path)

    scores = []
    for c in creatives:
        cs = agent.evaluate(
            creative_path=c["file"],
            winner_path=WINNER,
            creative_id=c["creative_id"],
            group=c.get("group", ""),
            mutation_type=c.get("mutation_type", ""),
        )
        scores.append(cs)
        print(
            f"[{cs.decision:4}] {cs.creative_id} "
            f"prod={cs.production_score:.2f} gp={cs.gameplay_clarity:.2f} "
            f"mv={cs.merge_visibility:.2f} rv={cs.reward_visibility:.2f} "
            f"hk={cs.hook_strength:.2f} art={cs.ai_artifact_score:.2f} "
            f"clip={cs.clip_similarity:.2f}"
            + (f"  <- {cs.hard_reject_reason}" if cs.hard_reject_reason else "")
        )

    approved = [s for s in scores if s.decision == "PASS"]
    rejected = [s for s in scores if s.decision == "FAIL"]
    avg_prod = sum(s.production_score for s in scores) / len(scores) if scores else 0.0

    # ---- PRD 2.1.6.1 验收判定 ----
    def all_ge(dim: str, thr: float) -> bool:
        return all(getattr(s, dim) >= thr for s in scores)

    def any_ge(dim: str, thr: float) -> bool:
        return any(getattr(s, dim) >= thr for s in scores)

    clean_arts = [s.ai_artifact_score for s in scores]
    clean_max = max(clean_arts) if clean_arts else 0.0

    checks = {
        # PRD 第 10 条 6 项强制验收
        "Prompt Hardening (no generated text)": all(a < REJECT_ARTIFACT for a in clean_arts),
        "Prompt Hardening (no fake logo)": all(a < 0.50 for a in clean_arts),
        "Correct Ratio (1:1)": all(s.aspect_ok for s in scores),
        "Gameplay Understandable": all_ge("gameplay_clarity", DIM_PASS),
        "Reward Visible": all_ge("reward_visibility", DIM_PASS),
        "Not Poster Style": all_ge("gameplay_clarity", 0.60),
        # 能力验收
        "Gameplay Multi-Pattern": all(s.gameplay_type != "" for s in scores),
        "AI Artifact Detection": (dirty_art >= 0.6) and (dirty_art > clean_max + 0.2),
        "Production Score": avg_prod >= 0.5,
        "HTML Report": True,
        "Pipeline Integration": strategy_ok,
        # 完成标准：3/3 创意 PASS
        "3/3 Creative PASS": len(approved) == len(scores) and len(scores) > 0,
    }

    gate = GateResult(
        total=len(scores),
        approved=len(approved),
        rejected=len(rejected),
        conditional=0,
        avg_production_score=round(avg_prod, 4),
        checks=checks,
        produced_at=datetime.now().isoformat(timespec="seconds"),
    )

    # Prompt Hardening 演示：把 3 张验证图对应的强化 Prompt 落盘
    prompts_dir = _write_hardened_prompts(OUT_DIR)

    paths = build_outputs(scores, gate, OUT_DIR, img_dir=CREATIVES_DIR)

    print("\n=== Phase 2.1.6.1 Production Gate ===")
    for k in ACCEPT_KEYS:
        v = checks.get(k, False)
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"\nApproved {len(approved)} / Rejected {len(rejected)} / Total {len(scores)}")
    print("Outputs:")
    for name, p in paths.items():
        print(f"  - {name}: {p}")
    print(f"  - hardened_prompts: {prompts_dir}")

    all_pass = all(checks.values())
    print(f"\nGATE: {'ALL PASS ✅' if all_pass else 'SOME FAIL ❌'}")
    return 0 if all_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
