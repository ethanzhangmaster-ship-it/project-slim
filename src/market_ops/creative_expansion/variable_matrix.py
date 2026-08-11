"""创意扩量变量矩阵

定义 Collection Hook 创意中所有可扩量的维度、取值范围和风险等级。
风险等级分为 P0（安全/高频）、P1（中等风险）、P2（高风险/低频）。
"""

from dataclasses import dataclass, field


@dataclass
class Variable:
    """单个可扩量变量"""

    dimension: str  # 维度标识，如 "creature.color"
    path: list[str]  # 在 Creative DNA 中的路径，如 ["creatures", "0", "color"]
    risk_level: str  # 风险等级: "P0", "P1", "P2"
    values: list[str]  # 可替换的候选值
    current_value: str = ""  # 当前 Winning 创意的取值


class VariableMatrix:
    """定义 Collection Hook 创意的全部可扩量变量矩阵"""

    # P0 - 安全变量（低风险，高频测试）
    P0_DIMENSIONS: dict[str, dict] = {
        "creature.color": {
            "path": ["creatures", "0", "color"],
            "values": ["pink", "green", "purple", "gold", "silver", "ruby"],
            # 默认/基准值: blue
        },
        "creature.type": {
            "path": ["creatures", "0", "type"],
            "values": ["Cat", "Fox", "Owl", "Unicorn", "Fairy", "Magic Egg", "Squirrel", "Phoenix"],
            # 默认/基准值: Dragon
        },
        "creature.glow": {
            "path": ["creatures", "0", "glow"],
            "values": ["cyan", "pink", "purple", "green", "white", "rainbow"],
            # 默认/基准值: gold
        },
        "creature.action": {
            "path": ["creatures", "0", "action"],
            "values": ["flying", "sleeping", "playing", "hunting", "sitting", "gliding"],
            # 默认/基准值: perched
        },
        "particle.color": {
            "path": ["particles", "0", "color"],
            "values": ["cyan", "pink", "rainbow", "purple", "white", "green"],
            # 默认/基准值: gold
        },
        "particle.type": {
            "path": ["particles", "0", "type"],
            "values": ["bubbles", "snow", "stars", "hearts", "feathers", "petals"],
            # 默认/基准值: sparkles
        },
        "plant.type": {
            "path": ["plants", "0", "type"],
            "values": ["crystal", "flower", "coral", "gem", "mushroom_cluster", "vine"],
            # 默认/基准值: mushroom
        },
        "plant.glow": {
            "path": ["plants", "0", "glow"],
            "values": ["pink", "gold", "white", "purple", "blue", "rainbow"],
            # 默认/基准值: teal
        },
        "lighting.color": {
            "path": ["lighting", "color"],
            "values": ["cool blue", "moon", "pink", "green", "sunset", "aurora"],
            # 默认/基准值: warm gold
        },
        "background.detail": {
            "path": ["background", "detail"],
            "values": ["pond", "statue", "tree", "ruins", "archway", "waterfall"],
            # 默认/基准值: fountain
        },
    }

    # P1 - 中等风险变量
    P1_DIMENSIONS: dict[str, dict] = {
        "character.clothes": {
            "path": ["character", "clothes"],
            "values": [
                "blue robe", "red dress", "green tunic", "white gown",
                "gold armor", "silver cloak", "purple hat and dress",
            ],
            # 默认/基准值: purple cloak
        },
        "character.pose": {
            "path": ["character", "pose"],
            "values": ["sitting", "floating", "walking", "kneeling", "leaning", "crouching"],
            # 默认/基准值: standing
        },
        "character.gesture": {
            "path": ["character", "gesture"],
            "values": ["pointing", "waving", "casting", "holding_orb", "arms_open", "finger_to_lips"],
            # 默认/基准值: hands clasped
        },
        "camera.shot_type": {
            "path": ["camera", "shot_type"],
            "values": ["close-up", "wide", "over-shoulder", "low-angle", "bird-eye"],
            # 默认/基准值: medium
        },
        "camera.movement": {
            "path": ["camera", "movement"],
            "values": ["push_in", "orbit", "tilt", "dolly_out", "crane_up"],
            # 默认/基准值: static
        },
        "environment.type": {
            "path": ["environment", "type"],
            "values": [
                "Crystal Cave", "Moon Lake", "Magic Garden", "Star Tower",
                "Sky Island", "Vineyard", "Mushroom Village",
            ],
            # 默认/基准值: Magic Forest
        },
        "environment.time": {
            "path": ["environment", "time"],
            "values": ["sunset", "dawn", "dusk", "midnight", "eclipse", "aurora"],
            # 默认/基准值: night
        },
    }

    # P2 - 高风险变量（极少变更，绝不同时改变多个）
    P2_DIMENSIONS: dict[str, dict] = {
        "character.type": {
            "path": ["character", "type"],
            "values": ["wizard", "girl", "boy", "elf", "fairy_queen"],
            # 默认/基准值: witch — ⚠️ 危险：改变角色核心身份
        },
        "hook.type": {
            "path": ["hook", "type"],
            "values": ["curiosity", "crisis", "mystery", "reward_reveal"],
            # 默认/基准值: collection — ⚠️ 危险：改变钩子类型
        },
        "composition.layout": {
            "path": ["composition", "layout"],
            "values": ["split", "diagonal", "frame_in_frame", "symmetrical"],
            # 默认/基准值: centered — ⚠️ 危险：改变构图逻辑
        },
        "style": {
            "path": ["style", "render"],
            "values": ["2D anime", "pixel art", "watercolor", "storybook"],
            # 默认/基准值: 3D render — ⚠️ 极其危险：改变整体视觉风格
        },
    }

    # 所有维度的合并映射，便于快速查找
    _ALL_DIMENSIONS: dict[str, dict] = {}

    def __init__(self) -> None:
        self._ALL_DIMENSIONS = {
            **{k: {**v, "risk_level": "P0"} for k, v in self.P0_DIMENSIONS.items()},
            **{k: {**v, "risk_level": "P1"} for k, v in self.P1_DIMENSIONS.items()},
            **{k: {**v, "risk_level": "P2"} for k, v in self.P2_DIMENSIONS.items()},
        }

    def get_matrix_for_dna(self, dna: dict) -> list[Variable]:
        """根据 Creative DNA 提取所有变量槽位，填充当前值

        Args:
            dna: Creative DNA 字典，结构如
                {
                    "creatures": [{"type": "Dragon", "color": "blue", ...}],
                    "particles": [{"type": "sparkles", ...}],
                    ...
                }

        Returns:
            填充了 current_value 的 Variable 列表
        """
        variables: list[Variable] = []

        for dimension, meta in self._ALL_DIMENSIONS.items():
            current_value = self._extract_value(dna, meta["path"])
            variables.append(
                Variable(
                    dimension=dimension,
                    path=meta["path"],
                    risk_level=meta["risk_level"],
                    values=meta["values"],
                    current_value=str(current_value) if current_value is not None else "",
                )
            )

        return variables

    def get_variants_for_dimension(self, dimension: str, current_value: str) -> list[str]:
        """获取某个维度的所有候选替换值（排除当前值）

        Args:
            dimension: 维度标识，如 "creature.color"
            current_value: 当前取值，将被从候选列表中排除

        Returns:
            可替换的候选值列表
        """
        meta = self._ALL_DIMENSIONS.get(dimension)
        if meta is None:
            return []

        # 排除当前值，返回其余候选
        return [v for v in meta["values"] if v.lower() != current_value.lower()]

    def get_risk_level(self, dimension: str) -> str:
        """获取维度的风险等级

        Args:
            dimension: 维度标识

        Returns:
            "P0" / "P1" / "P2"，未知维度返回 "P2"（保守策略）
        """
        meta = self._ALL_DIMENSIONS.get(dimension)
        if meta is None:
            return "P2"  # 未知维度按最高风险处理
        return meta["risk_level"]

    def count_total_variants(self, matrix: list[Variable]) -> int:
        """统计变量矩阵的总变体数

        计算方式：对每个变量取 (候选值数 - 排除当前值后的数量)，再求积。
        即每个维度可替换的选项数之积。

        Args:
            matrix: 由 get_matrix_for_dna 返回的变量列表

        Returns:
            总变体数
        """
        total = 1
        for var in matrix:
            # 可替换的候选数 = 候选总数 - 1（排除当前值）
            # 若当前值不在候选列表中，则全部候选均可替换
            replaceable = [v for v in var.values if v.lower() != var.current_value.lower()]
            if replaceable:
                total *= len(replaceable)
        return total

    # ---- 内部工具方法 ----

    @staticmethod
    def _extract_value(data: dict, path: list[str]) -> object:
        """按路径从嵌套字典中提取值

        Args:
            data: 嵌套字典
            path: 路径片段列表，如 ["creatures", "0", "color"]

        Returns:
            找到的值，未找到则返回 None
        """
        current = data
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list):
                try:
                    current = current[int(key)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current
