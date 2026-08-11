"""AI Game Studio OS Workspace — 控制中心后端.

将分散的 Agent / 数据 / 增长 / Creative / 商业化系统统一接入
可视化控制中心。FastAPI app + Dashboard 聚合 + Mock 数据层。

模块结构:
  - models.py: Workspace DTO (适配 PRD 字段, 不侵入现有 dataclass)
  - mock_provider.py: 内置 Mock 数据生成器
  - aggregator.py: Dashboard 数据聚合层
  - app.py: FastAPI 应用 + 路由
"""

__version__ = "0.1.0"
