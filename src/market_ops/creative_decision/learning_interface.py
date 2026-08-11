"""Module 9: Learning Interface（预留）

预留 Facebook 投放数据回流接口。
未来支持：
- Facebook Marketing API 数据自动回流
- 根据实际 CTR/ROAS/CVR 更新预测模型
- 自动调整 Variable Weight
- 多市场独立策略学习
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FacebookResult:
    """单个创意在 Facebook 上的投放结果"""
    creative_id: str
    variant_id: str
    campaign_id: str = ""
    adset_id: str = ""
    
    # 表现指标
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    installs: int = 0
    cvr: float = 0.0
    ipm: float = 0.0
    spend: float = 0.0
    cpi: float = 0.0
    cpp: float = 0.0
    
    # ROAS
    d1_revenue: float = 0.0
    d1_roas: float = 0.0
    d7_revenue: float = 0.0
    d7_roas: float = 0.0
    d30_revenue: float = 0.0
    d30_roas: float = 0.0
    
    # 疲劳指标
    frequency: float = 0.0
    days_running: int = 0
    
    # 受众
    country: str = ""
    age_range: str = ""
    gender: str = ""
    placement: str = ""
    
    # 时间
    date: str = ""


@dataclass
class LearningUpdate:
    """学习更新结果"""
    variable_weights_delta: dict[str, float] = field(default_factory=dict)
    prediction_bias_correction: dict[str, float] = field(default_factory=dict)
    new_insights: list[str] = field(default_factory=list)
    model_version: str = "v1.0"


class LearningInterface:
    """学习接口 - 预留 Facebook 数据回流
    
    当前版本：
    - 提供接口定义
    - 支持手动导入历史数据
    - 生成学习报告（但不做实际模型更新）
    
    未来版本：
    - 连接 Facebook Marketing API
    - 自动每日回流数据
    - 在线学习更新权重
    - 多市场独立模型
    """
    
    def __init__(self, history_dir: str | Path = ""):
        self.history_dir = Path(history_dir) if history_dir else Path("facebook_history")
        self.results: list[FacebookResult] = []
    
    def load_history(self, results: list[dict]) -> None:
        """加载历史投放数据
        
        Args:
            results: FacebookResult 的字典列表
        """
        self.results = [FacebookResult(**r) for r in results]
        print(f"[Learning] 加载了 {len(self.results)} 条历史记录")
    
    def load_from_files(self, history_dir: str | Path) -> None:
        """从文件目录加载历史数据
        
        期望目录结构：
        facebook_history/
            creative_001/
                ctr.json
                roas.json
                cvr.json
        """
        history_dir = Path(history_dir)
        if not history_dir.exists():
            print(f"[Learning] 历史数据目录不存在: {history_dir}")
            return
        
        # 预留：未来解析 JSON 文件
        print(f"[Learning] 历史数据目录: {history_dir}（预留接口）")
    
    def learn(self, ranked_variants: list[dict]) -> LearningUpdate:
        """基于历史数据学习，生成权重更新建议
        
        当前版本：生成报告但不修改权重
        未来版本：自动更新模型参数
        
        Args:
            ranked_variants: V4.2 Ranking 结果
        """
        if not self.results:
            print("[Learning] 无历史数据，跳过学习")
            return LearningUpdate()
        
        # 分析：哪些 changed_dimension  historically 表现更好
        dim_performance: dict[str, list[float]] = {}
        for r in self.results:
            # 找到对应的 variant
            # 预留：需要 variant → creative_id 的映射
            pass
        
        # 生成洞察
        insights = [
            "[预留] 历史数据已加载，等待模型训练逻辑",
            "[预留] 未来将根据实际 CTR/ROAS 自动调整预测模型",
            "[预留] 支持多市场独立策略学习",
        ]
        
        return LearningUpdate(
            new_insights=insights,
        )
    
    def get_insights_for_variant(self, variant_id: str) -> list[str]:
        """获取特定 variant 的历史洞察"""
        variant_results = [r for r in self.results if r.variant_id == variant_id]
        if not variant_results:
            return ["无历史投放数据"]
        
        insights = []
        avg_ctr = sum(r.ctr for r in variant_results) / len(variant_results)
        avg_roas = sum(r.d7_roas for r in variant_results) / len(variant_results)
        
        insights.append(f"历史 CTR: {avg_ctr:.2%}")
        insights.append(f"历史 D7 ROAS: {avg_roas:.2f}")
        
        return insights
    
    def export_learning_data(self, output_path: str | Path) -> None:
        """导出学习数据供外部模型训练"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = []
        for r in self.results:
            data.append({
                "variant_id": r.variant_id,
                "country": r.country,
                "placement": r.placement,
                "ctr": r.ctr,
                "cvr": r.cvr,
                "roas": r.d7_roas,
                "spend": r.spend,
            })
        
        import json
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"[Learning] 学习数据已导出: {output_path}")
