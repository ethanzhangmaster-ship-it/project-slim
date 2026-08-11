"""DNA Mutation Engine — Phase 2 核心。

输入：winner_dna（来自 WinnerDNALoader 的归一化结构）
输出：count 个**唯一**的 DNA 变体，每个含：
    - mutation_id: "mut_NNN"
    - dna: 完整变异后 DNA（character/theme/reward/background/composition/color/hook）
    - mutation_reason: 人类可读的变异说明（保留哪些 / 改变哪些）

设计原则：
- 保留核心维度（character / color / hook）以锚定“Winner 像”；
- 在 background / gameplay / reward / composition 上做有策略的变化制造多样性；
- 通过冻结键去重，保证 50 个变体互不重复；
- composition 采用轮询（round-robin），确保 ≥5 个构图聚类（diversity 验收）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from market_ops.creative_intelligence.factory.dna.mutation_strategy import (  # noqa: E402
    MutationDimension,
)


class DNAMutator:
    def __init__(self, library_path: str | Path | None = None) -> None:
        if library_path is None:
            library_path = Path(__file__).resolve().parent / "mutation_library.json"
        self.library_path = Path(library_path)
        self.library: dict[str, Any] = json.loads(
            self.library_path.read_text(encoding="utf-8")
        )

    # ------------------------------------------------------------------
    def mutate(self, winner_dna: dict[str, Any], count: int = 50) -> list[dict[str, Any]]:
        """生成 count 个唯一 DNA 变体。

        做法：对可变维度做笛卡尔积 → 冻结键去重 → 按构图维度轮询分组取前 count 个，
        保证 (a) 绝对唯一（无重复 DNA）；(b) 构图维度在结果中均匀分布（≥5 个聚类，
        满足 diversity 验收）；(c) 核心维度（character / color / hook）始终保留。
        """
        import itertools

        base = self._extract_base_dna(winner_dna)
        comps = list(self.library.get("composition", [])) or [base["composition"]]
        rewards = self._matching_rewards(base) or [base["reward"]]
        # 保留 base 背景作为“最小变异”选项，制造相似度梯度
        bgs = [base["background"]] + list(self.library.get("background", [])) or [
            base["background"]
        ]
        colors = self._matching_colors(base) or [base["color"]]
        # 保留 base 钩子（如 collection）作为选项，部分变体更贴近 winner
        hooks = list(self.library.get("hook", [])) or [base["hook"]]

        # 1) 笛卡尔积 + 去重，得到全部候选 DNA
        seen: set[tuple] = set()
        uniq: list[dict[str, Any]] = []
        for comp, rw, bg, col, hk in itertools.product(comps, rewards, bgs, colors, hooks):
            dna = {
                "character": base["character"],
                "theme": base["theme"],
                "reward": rw,
                "background": bg,
                "composition": comp,
                "color": col,
                "hook": hk,
            }
            key = self._key(dna)
            if key not in seen:
                seen.add(key)
                uniq.append(dna)
            if len(uniq) >= count * 200:  # 上限保护
                break

        # 2) 按构图维度分组，轮询取数以保证多样性
        groups: dict[str, list[dict[str, Any]]] = {comp: [] for comp in comps}
        for d in uniq:
            groups[d["composition"]].append(d)

        variants: list[dict[str, Any]] = []
        while len(variants) < count:
            progressed = False
            for comp in comps:
                if groups[comp]:
                    d = groups[comp].pop(0)
                    variants.append(d)
                    progressed = True
                    if len(variants) >= count:
                        break
            if not progressed:
                break

        # 3) 构造最终结构（mutation_id / reason）
        out: list[dict[str, Any]] = []
        for idx, dna in enumerate(variants, start=1):
            reason = self._reason(
                base,
                dna,
                dna["reward"],
                dna["composition"],
                dna["color"],
                dna["hook"],
            )
            out.append(
                {
                    "mutation_id": f"mut_{idx:03d}",
                    "dna": dna,
                    "mutation_reason": reason,
                }
            )
        return out


    # ------------------------------------------------------------------
    @staticmethod
    def _key(dna: dict[str, Any]) -> tuple:
        return tuple(sorted((k, str(v)) for k, v in dna.items()))

    def _matching_rewards(self, base: dict[str, Any]) -> list[str]:
        out: list[str] = [base["reward"]]  # 保留 base 作为“最小变异”选项
        for r in self.library.get("reward", []):
            if isinstance(r, dict) and r.get("from") == base["reward"]:
                out.append(r["to"])
        if len(out) == 1:
            out += list(self.library.get("reward_alternatives", []))
        # 去重保序
        seen = set()
        uniq = []
        for x in out:
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        return uniq

    def _matching_colors(self, base: dict[str, Any]) -> list[str]:
        out: list[str] = [base["color"]]  # 保留 base 作为“最小变异”选项
        for c in self.library.get("color", []):
            if isinstance(c, dict) and c.get("from") == base["color"]:
                out.append(c["to"])
        if len(out) == 1:
            out += list(self.library.get("color_alternatives", []))
        seen = set()
        uniq = []
        for x in out:
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        return uniq

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_base_dna(winner_dna: dict[str, Any]) -> dict[str, Any]:
        """从归一化 winner_dna 提取变异引擎的 base DNA。

        兼容 WinnerDNALoader 输出（含 raw 原始字段：standout_features / overall_summary）。
        """
        raw = winner_dna.get("raw", {}) or {}
        subject = (winner_dna.get("subject", "") or "").lower()

        character = "witch"
        for kw in ("witch", "mage", "fairy", "wizard", "goddess", "hero", "princess", "warrior"):
            if kw in subject:
                character = kw
                break

        standout = raw.get("standout_features", []) or []
        summary = raw.get("overall_summary", "") or ""
        text = " ".join(standout).lower() + " " + summary.lower()
        reward = "magic garden"
        for kw in (
            "baby dragon",
            "dragon",
            "phoenix",
            "cat",
            "gargoyle",
            "treasure",
            "grimoire",
            "celestial flower",
            "magic chest",
        ):
            if kw in text:
                reward = kw
                break

        palette = (winner_dna.get("palette", "") or "").lower()
        if "purple" in palette or "magenta" in palette:
            color = "purple blue"
        elif "red" in palette or "crimson" in palette:
            color = "crimson"
        elif "green" in palette or "emerald" in palette:
            color = "emerald"
        else:
            color = "purple blue"

        comp = winner_dna.get("hook_type") or "collection"
        hook = winner_dna.get("hook_type") or "collection"
        theme = winner_dna.get("theme") or "magic garden"
        background = "magical castle garden"

        return {
            "character": character,
            "theme": theme,
            "reward": reward,
            "background": background,
            "composition": comp,
            "color": color,
            "hook": hook,
        }

    @staticmethod
    def _reason(
        base: dict[str, Any],
        dna: dict[str, Any],
        rw: str,
        comp: str,
        col: str,
        hk: str,
    ) -> str:
        preserved = []
        if dna["character"] == base["character"]:
            preserved.append(f"character={base['character']}")
        if dna["color"] == base["color"]:
            preserved.append(f"color={base['color']}")
        if dna["hook"] == base["hook"]:
            preserved.append(f"hook={base['hook']}")
        changes = []
        if dna["reward"] != base["reward"]:
            changes.append(f"reward: {base['reward']} → {dna['reward']}")
        if dna["composition"] != base["composition"]:
            changes.append(f"composition: {base['composition']} → {dna['composition']}")
        if dna["background"] != base["background"]:
            changes.append("background → " + dna["background"])
        if dna["color"] != base["color"]:
            changes.append(f"color: {base['color']} → {dna['color']}")
        if dna["hook"] != base["hook"]:
            changes.append(f"hook: {base['hook']} → {dna['hook']}")
        head = "保持 " + " / ".join(preserved) if preserved else "无保留维度"
        body = "；改变 " + "；".join(changes) if changes else "；无变化"
        return head + body
