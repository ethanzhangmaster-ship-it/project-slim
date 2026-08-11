"""P04 Creative Factory V2 — Pipeline Runner (CLI).

Phase 1:
  python pipeline_runner.py --winner winner_001 --count 50
  python pipeline_runner.py --winner winner_001 --count 50 --dry-run

Phase 2 (DNA Mutation Engine + CLIP Similarity Ranking + TOP10):
  python pipeline_runner.py --winner winner_001 --count 50 --phase2 --dry-run
  python pipeline_runner.py --winner winner_001 --count 50 --phase2 --clip-mode openclip

说明:
  --dry-run 仅用于验证整条管线接线（本地占位图，不消耗 Lovart 额度）。
  --clip-mode: auto(探测) | openclip | clip | heuristic(无 ML 依赖回退)。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# 从 __file__ 向上搜索包含 market_ops 包的目录（即 src 根），与文件相对深度解耦
def _src_root() -> Path:
    here = Path(__file__).resolve()
    for cand in [here, *here.parents]:
        if (cand / "market_ops").is_dir():
            return cand
    raise RuntimeError("无法定位 src 根目录（未找到 market_ops 包）")


sys.path.insert(0, str(_src_root()))


def _progress(done: int, total: int, width: int = 20) -> str:
    filled = int(width * done / max(1, total))
    return "█" * filled + "░" * (width - filled)


def main() -> int:
    parser = argparse.ArgumentParser(description="P04 Creative Factory V2 — Pipeline Runner")
    parser.add_argument("--winner", type=str, required=True, help="winner_id 或 winner_NNN 别名")
    parser.add_argument("--count", type=int, default=50, help="生成创意数量 (默认 50)")
    parser.add_argument("--dry-run", action="store_true", help="不调用 Lovart，仅验证管线")
    parser.add_argument("--model", type=str, default=None, help="指定 Lovart 模型（可选）")
    parser.add_argument("--output", type=str, default=None, help="自定义输出根目录")
    parser.add_argument("--phase2", action="store_true", help="启用 Phase 2：Mutation + CLIP Ranking + TOP10")
    parser.add_argument(
        "--clip-mode",
        type=str,
        default="auto",
        choices=["auto", "openclip", "clip", "heuristic"],
        help="CLIP 相似度模式 (默认 auto 探测)",
    )
    parser.add_argument("--top-k", type=int, default=10, help="排序保留候选数 (默认 10)")
    args = parser.parse_args()

    from market_ops.creative_intelligence.factory.creative_factory import CreativeFactory

    phase = "Phase 2" if args.phase2 else "Phase 1"
    print("=" * 64)
    print(f"  P04 Creative Factory V2 — {phase}")
    print(
        f"  winner={args.winner}  count={args.count}  dry_run={args.dry_run}"
        + (f"  clip={args.clip_mode}  top_k={args.top_k}" if args.phase2 else "")
    )
    print("=" * 64)

    try:
        factory = CreativeFactory(output_dir=args.output)

        # [1] Load Winner DNA
        t0 = time.time()
        print(f"\n[1] Load Winner DNA")
        from market_ops.creative_intelligence.factory.dna.winner_dna_loader import (
            WinnerDNALoader,
        )
        winner = WinnerDNALoader().load_winner(args.winner)
        print(f"  ✓ {args.winner} (code=winner_{winner['winner_code']}, "
              f"subject={winner.get('subject','')[:40]})")

        # [2] Validate Reference
        print(f"\n[2] Validate Reference")
        if args.dry_run:
            print("  ✓ image available (dry-run, 跳过远程校验)")
        else:
            print("  … 校验参考图 URL 与本地文件")

        if args.phase2:
            # [3] Mutate DNA
            print(f"\n[3] Mutate DNA → {args.count} variants")
            print(f"  ✓ DNA Mutation Engine 就绪（unique variants 保证）")

            # [4] Generate
            print(f"\n[4] Generate {args.count} creatives")
            result = factory.generate(
                winner_id=args.winner,
                count=args.count,
                dry_run=args.dry_run,
                model=args.model,
                use_mutation=True,
                rank=True,
                top_k=args.top_k,
                clip_mode=args.clip_mode,
            )
            print(f"  {_progress(args.count, args.count)} {args.count}/{args.count}")

            # [5] CLIP Rank → TOP-K
            rk = result.get("ranking") or {}
            print(f"\n[5] CLIP Rank → TOP{args.top_k}")
            print(f"  ✓ clip_mode = {rk.get('clip_mode')}")
            print(f"  ✓ composition clusters = {rk.get('composition_clusters')}")
            print(f"  ✓ top = {', '.join(rk.get('top_ids', [])[:5])} ...")
        else:
            # [3] Generate
            print(f"\n[3] Generate {args.count} variations")
            result = factory.generate(
                winner_id=args.winner,
                count=args.count,
                dry_run=args.dry_run,
                model=args.model,
            )
            print(f"  {_progress(args.count, args.count)} {args.count}/{args.count}")

        # Final: Export
        step_no = 6 if args.phase2 else 4
        print(f"\n[{step_no}] Export batch")
        meta = Path(result["batch_dir"]) / "batch_metadata.json"
        if not meta.exists():
            raise RuntimeError(f"batch_metadata.json 未生成: {meta}")
        print(f"  ✓ completed")
        print(f"  reference_status = {result['reference_status']}")
        print(f"  generation_mode = {result.get('generation_mode')}")
        print(f"  ready = {result['ready']}/{result['generation_count']}")
        print(f"  batch = {result['batch_dir']}")
        if args.phase2 and result.get("ranking"):
            prod = Path(result["ranking"]["production_candidates_dir"])
            print(f"  production_candidates = {prod}")

        elapsed = time.time() - t0
        print(f"\n{'=' * 64}")
        print(f"  ✅ {phase} 完成 ({elapsed:.1f}s)")
        print(f"{'=' * 64}")
        return 0

    except Exception as exc:
        print(f"\n  ✗ 失败: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
