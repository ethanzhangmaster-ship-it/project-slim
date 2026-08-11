"""E11.2.3-4 — Creative Asset Runtime (Event-Driven Continuous Binding Pipeline)。

E11.2.3: 将 E11.2 从定时脚本升级为事件驱动的持续运行服务。
E11.2.4: 接入 Facebook Graph API + Adjust API 真实数据源。

模块：
  - events/asset_events.py       — 事件类型定义（frozen dataclass）
  - events/event_bus_adapter.py  — AssetEventBus（发布/订阅/持久化/重试）
  - workers/eagle_worker.py      — EagleScannerWorker
  - workers/binding_worker.py    — BindingWorker
  - workers/materializer_worker.py — MaterializerWorker
  - workers/lifecycle_worker.py  — LifecycleWorker
  - workers/facebook_worker.py   — FacebookWorker (E11.2.4)
  - workers/adjust_worker.py     — AdjustWorker (E11.2.4)
  - connectors/facebook_connector.py — FacebookConnector (E11.2.4)
  - connectors/adjust_connector.py   — AdjustConnector (E11.2.4)
  - runtime.py                   — AssetRuntime 编排器
  - daemon.py                    — RuntimeDaemon (E11.2.4)
"""