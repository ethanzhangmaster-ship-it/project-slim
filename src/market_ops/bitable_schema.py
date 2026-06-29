"""Bitable 多维表格结构定义

定义 6 张可视化报告表的字段名称和类型，用于自动建表和数据校验。

Bitable 字段类型编号:
  1 = 文本, 2 = 数字, 3 = 单选, 4 = 多选, 5 = 日期,
  7 = 复选框, 11 = 人员, 15 = 超链接, 17 = 附件,
  1001 = 创建时间, 1002 = 修改时间
"""

from __future__ import annotations

from typing import Any

from market_ops.config import Settings

# -- 字段类型常量 --
TEXT = 1
NUMBER = 2
SINGLE_SELECT = 3
MULTI_SELECT = 4
DATE = 5


# -- 6 张表的字段定义 --

KPI_OVERVIEW_FIELDS: list[dict[str, Any]] = [
    {"field_name": "报告周期", "type": TEXT},
    {"field_name": "本周花费", "type": NUMBER},
    {"field_name": "整体收入", "type": NUMBER},
    {"field_name": "利润估算", "type": NUMBER},
    {"field_name": "公司总收入ROI", "type": TEXT},
    {"field_name": "主投渠道", "type": TEXT},
    {"field_name": "花费环比变化", "type": TEXT},
    {"field_name": "收入环比变化", "type": TEXT},
    {"field_name": "ROI环比变化", "type": TEXT},
    {"field_name": "重点亮点", "type": TEXT},
    {"field_name": "下周关注", "type": TEXT},
]

PROJECT_ANALYSIS_FIELDS: list[dict[str, Any]] = [
    {"field_name": "项目名称", "type": TEXT},
    {"field_name": "项目Key", "type": TEXT},
    {"field_name": "本周花费", "type": NUMBER},
    {"field_name": "花费环比", "type": TEXT},
    {"field_name": "总收入", "type": NUMBER},
    {"field_name": "总收入ROI", "type": NUMBER},
    {"field_name": "付费净ROI", "type": NUMBER},
    {"field_name": "平均ROAS", "type": NUMBER},
    {"field_name": "平均CPI", "type": NUMBER},
    {"field_name": "主投渠道", "type": TEXT},
    {"field_name": "风险段", "type": TEXT},
    {"field_name": "回本状态", "type": TEXT},
    {"field_name": "生命周期阶段", "type": TEXT},
    {"field_name": "增长潜力", "type": NUMBER},
    {"field_name": "风险等级", "type": TEXT},
    {"field_name": "置信度", "type": TEXT},
    {"field_name": "建议动作", "type": TEXT},
    {"field_name": "预测建议", "type": TEXT},
    {"field_name": "利润结构", "type": TEXT},
    # -- Phase 3: 回本曲线 + 动态保底线 --
    {"field_name": "静态保本D7", "type": NUMBER},
    {"field_name": "静态保本D30", "type": NUMBER},
    {"field_name": "动态保本D7", "type": NUMBER},
    {"field_name": "动态保本D30", "type": NUMBER},
    {"field_name": "当前D7", "type": NUMBER},
    {"field_name": "当前CPI", "type": NUMBER},
    {"field_name": "D1留存", "type": NUMBER},
    {"field_name": "当前ARPU", "type": NUMBER},
    {"field_name": "当前ARPPU", "type": NUMBER},
    {"field_name": "回本判断", "type": TEXT},
    {"field_name": "生命周期风险分", "type": NUMBER},
    {"field_name": "回本比例", "type": NUMBER},
    {"field_name": "质量得分", "type": NUMBER},
    {"field_name": "早期放量潜力", "type": NUMBER},
    {"field_name": "素材集群数", "type": NUMBER},
    {"field_name": "最大集群扩展性", "type": NUMBER},
    {"field_name": "疲劳信号数", "type": NUMBER},
]

CAMPAIGN_DETAIL_FIELDS: list[dict[str, Any]] = [
    {"field_name": "项目名称", "type": TEXT},
    {"field_name": "渠道", "type": TEXT},
    {"field_name": "Campaign名称", "type": TEXT},
    {"field_name": "国家", "type": TEXT},
    {"field_name": "商店", "type": TEXT},
    {"field_name": "花费", "type": NUMBER},
    {"field_name": "收入", "type": NUMBER},
    {"field_name": "ROI", "type": NUMBER},
    {"field_name": "CPI", "type": NUMBER},
    {"field_name": "CTR", "type": NUMBER},
    {"field_name": "安装数", "type": NUMBER},
    {"field_name": "D1留存", "type": NUMBER},
    {"field_name": "D7留存", "type": NUMBER},
    {"field_name": "花费环比", "type": TEXT},
    {"field_name": "回本门禁", "type": TEXT},
    {"field_name": "置信度", "type": TEXT},
    {"field_name": "风险判断", "type": TEXT},
    {"field_name": "建议动作", "type": TEXT},
    {"field_name": "问题描述", "type": TEXT},
    {"field_name": "原因", "type": TEXT},
    {"field_name": "负责人", "type": TEXT},
    {"field_name": "截止日期", "type": TEXT},
    {"field_name": "验收指标", "type": TEXT},
]

CREATIVE_ANALYSIS_FIELDS: list[dict[str, Any]] = [
    {"field_name": "素材ID", "type": TEXT},
    {"field_name": "素材名称", "type": TEXT},
    {"field_name": "素材类型", "type": TEXT},
    {"field_name": "项目", "type": TEXT},
    {"field_name": "渠道", "type": TEXT},
    {"field_name": "国家", "type": TEXT},
    {"field_name": "CTR", "type": NUMBER},
    {"field_name": "ROAS", "type": NUMBER},
    {"field_name": "花费", "type": NUMBER},
    {"field_name": "安装数", "type": NUMBER},
    {"field_name": "收入", "type": NUMBER},
    {"field_name": "CPI", "type": NUMBER},
    {"field_name": "CPM", "type": NUMBER},
    {"field_name": "样本状态", "type": TEXT},
    {"field_name": "疲劳状态", "type": TEXT},
    {"field_name": "CTR降幅", "type": NUMBER},
    {"field_name": "CPI涨幅", "type": NUMBER},
    {"field_name": "ROI变化", "type": NUMBER},
    {"field_name": "上周花费", "type": NUMBER},
    {"field_name": "上周ROI", "type": NUMBER},
    {"field_name": "上周CTR", "type": NUMBER},
    {"field_name": "上周CPI", "type": NUMBER},
    {"field_name": "生命周期", "type": TEXT},
    {"field_name": "Hook类型", "type": TEXT},
    {"field_name": "风险等级", "type": TEXT},
    {"field_name": "建议动作", "type": TEXT},
    {"field_name": "疲劳原因", "type": TEXT},
    {"field_name": "修复建议", "type": TEXT},
    {"field_name": "置信度", "type": TEXT},
]

DECISION_DISTRIBUTION_FIELDS: list[dict[str, Any]] = [
    {"field_name": "实体类型", "type": TEXT},
    {"field_name": "实体ID", "type": TEXT},
    {"field_name": "项目", "type": TEXT},
    {"field_name": "范围", "type": TEXT},
    {"field_name": "决策类别", "type": TEXT},
    {"field_name": "增长得分", "type": NUMBER},
    {"field_name": "风险得分", "type": NUMBER},
    {"field_name": "花费", "type": NUMBER},
    {"field_name": "收入", "type": NUMBER},
    {"field_name": "ROI", "type": NUMBER},
    {"field_name": "置信度", "type": NUMBER},
    {"field_name": "增长阶段", "type": TEXT},
    {"field_name": "推荐动作", "type": TEXT},
    # -- Phase 1: 13维权重拆解 --
    {"field_name": "原始增长优先级", "type": NUMBER},
    {"field_name": "原始风险优先级", "type": NUMBER},
    {"field_name": "生命周期阶段", "type": TEXT},
    {"field_name": "生命周期增长潜力", "type": NUMBER},
    {"field_name": "生命周期风险分", "type": NUMBER},
    {"field_name": "生命周期决策输入", "type": TEXT},
    {"field_name": "战略对齐分", "type": NUMBER},
    {"field_name": "战略护栏风险", "type": NUMBER},
    {"field_name": "战略护栏阻断", "type": TEXT},
    {"field_name": "剧本增长偏置", "type": NUMBER},
    {"field_name": "剧本风险偏置", "type": NUMBER},
    {"field_name": "动作信号", "type": TEXT},
    {"field_name": "预算变化信号", "type": TEXT},
    # -- 信号链 --
    {"field_name": "正向信号", "type": TEXT},
    {"field_name": "负向信号", "type": TEXT},
    {"field_name": "引用子模块", "type": TEXT},
]

ACTION_TRACKING_FIELDS: list[dict[str, Any]] = [
    {"field_name": "Task ID", "type": TEXT},
    {"field_name": "Source Meeting", "type": TEXT},
    {"field_name": "Type", "type": TEXT},
    {"field_name": "Title", "type": TEXT},
    {"field_name": "Owner", "type": TEXT},
    {"field_name": "Status", "type": TEXT},
    {"field_name": "Acceptance Metric", "type": TEXT},
    {"field_name": "Due Date", "type": TEXT},
    {"field_name": "Description", "type": TEXT},
    {"field_name": "Latest Note", "type": TEXT},
    {"field_name": "Decision Context", "type": TEXT},
    {"field_name": "Priority Score", "type": NUMBER},
    # -- Phase 5: 闭环回填 --
    {"field_name": "完成日期", "type": TEXT},
    {"field_name": "实际结果", "type": TEXT},
    {"field_name": "验收值", "type": TEXT},
    {"field_name": "创建日期", "type": TEXT},
]


# -- 视频素材总表 (wiki 维度) --

VIDEO_CREATIVE_FIELDS: list[dict[str, Any]] = [
    # -- 制作跟踪 (sheet 1, 17 cols) --
    {"field_name": "周次", "type": TEXT},
    {"field_name": "素材编号", "type": TEXT},
    {"field_name": "平台", "type": TEXT},
    {"field_name": "状态", "type": TEXT},
    {"field_name": "项目", "type": TEXT},
    {"field_name": "负责人", "type": TEXT},
    {"field_name": "优先级", "type": TEXT},
    {"field_name": "类型", "type": TEXT},
    {"field_name": "视频内容", "type": TEXT},
    {"field_name": "素材命名格式", "type": TEXT},
    {"field_name": "参考视频/图片", "type": TEXT},
    {"field_name": "制作说明", "type": TEXT},
    {"field_name": "尺寸", "type": TEXT},
    {"field_name": "制作成员", "type": TEXT},
    {"field_name": "开始制作时间", "type": TEXT},
    {"field_name": "终止时间", "type": TEXT},
    {"field_name": "交付时间", "type": TEXT},
    # -- 投放数据 (sheet 2/3, 23 cols) --
    {"field_name": "投放日期", "type": TEXT},
    {"field_name": "停投日期", "type": TEXT},
    {"field_name": "素材评级", "type": TEXT},
    {"field_name": "Cost", "type": NUMBER},
    {"field_name": "CTR", "type": NUMBER},
    {"field_name": "点击次数", "type": NUMBER},
    {"field_name": "Install", "type": NUMBER},
    {"field_name": "CPI", "type": NUMBER},
    {"field_name": "IPM", "type": NUMBER},
    {"field_name": "CVR", "type": NUMBER},
    {"field_name": "展示次数", "type": NUMBER},
    {"field_name": "CPM", "type": NUMBER},
    {"field_name": "有效行为已达标", "type": NUMBER},
    {"field_name": "CPA", "type": NUMBER},
    {"field_name": "转化价值", "type": NUMBER},
    {"field_name": "Roas", "type": NUMBER},
    {"field_name": "D0_ROAS", "type": NUMBER},
    {"field_name": "D3_ROAS", "type": NUMBER},
    {"field_name": "D7_ROAS", "type": NUMBER},
    {"field_name": "D1留存率", "type": NUMBER},
    {"field_name": "D3留存率", "type": NUMBER},
    {"field_name": "D7留存率", "type": NUMBER},
    {"field_name": "回收情况", "type": TEXT},
]


# -- 表名 → 字段定义映射 --

TABLE_SCHEMAS: dict[str, list[dict[str, Any]]] = {
    "公司指标总览": KPI_OVERVIEW_FIELDS,
    "项目分析表": PROJECT_ANALYSIS_FIELDS,
    "Campaign明细表": CAMPAIGN_DETAIL_FIELDS,
    "素材分析表": CREATIVE_ANALYSIS_FIELDS,
    "决策分布表": DECISION_DISTRIBUTION_FIELDS,
    "行动追踪表": ACTION_TRACKING_FIELDS,
    "视频素材总表": VIDEO_CREATIVE_FIELDS,
}

# -- 表名 → Settings 属性名映射 --

_TABLE_ID_ATTR: dict[str, str] = {
    "公司指标总览": "bitable_kpi_overview_table_id",
    "项目分析表": "bitable_project_analysis_table_id",
    "Campaign明细表": "bitable_campaign_detail_table_id",
    "素材分析表": "bitable_creative_analysis_table_id",
    "决策分布表": "bitable_decision_distribution_table_id",
    "行动追踪表": "bitable_action_tracking_table_id",
    "视频素材总表": "bitable_video_creative_table_id",
}


def get_table_schema(table_name: str) -> list[dict[str, Any]]:
    """Return the field definitions for a given table name."""
    return TABLE_SCHEMAS[table_name]


def get_table_id_map(settings: Settings) -> dict[str, str | None]:
    """Return mapping of table_name -> table_id from settings."""
    result: dict[str, str | None] = {}
    for table_name, attr_name in _TABLE_ID_ATTR.items():
        result[table_name] = getattr(settings, attr_name, None)
    return result


def get_ordered_table_names() -> list[str]:
    """Return table names in the canonical display order."""
    return list(TABLE_SCHEMAS.keys())
