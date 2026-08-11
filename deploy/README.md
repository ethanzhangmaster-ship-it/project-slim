# E14.4.1 — Lean Container Runtime

把现有纯 Python 编排器（`agent` + `runtime/supervisor` + `runtime/scheduler`）
打包成**单 worker 镜像**，运营 10–50 款游戏。

原则（延续 E13.x → E14.3 的 Lean 架构）：

- **无重型后端**：不引入 FastAPI / Postgres / Redis / S3。
- **唯一状态**：JSONL `DecisionStore`，挂在卷上（`/app/data/stores`）。
- **密钥隔离**：`credentials/` 以只读卷挂载，`CredentialResolver`（E14.3.5）
  保证 game_A 读不到 game_B 的 key。
- **水平分片**：一个容器负责游戏的**子集**（`GAMES=...`），50 游戏靠 N 个
  worker 横向扩展，每个仍完全隔离。

---

## 文件

| 文件 | 作用 |
|---|---|
| `Dockerfile` | python:3.13-slim + venv + jsonschema + worker 入口 |
| `worker.py` | 容器入口：装配 OS → 可选 CredentialResolver → Supervisor → Scheduler，跑每日周期或常驻循环，SIGTERM 优雅退出 |
| `docker-compose.yml` | 单 worker service + 卷挂 credentials/stores/checkpoints + 分片 env |
| `../requirements.txt` | 仅 `jsonschema`（核心编排 stdlib-only） |

> 构建上下文必须是**仓库根目录**（launchforge 的父目录），因为 Dockerfile 用
> `COPY launchforge ...`。

---

## 构建

```bash
# 在仓库根目录执行
docker build -f launchforge/deploy/Dockerfile -t launchforge-worker .
```

## 本地冒烟（无需 Docker）

`worker.py` 可直接用 `python` 跑，验证入口装配正确：

```bash
cd launchforge
python deploy/worker.py --once --n-games 12
# 也支持真实密钥隔离：
python deploy/worker.py --once \
    --credentials-dir credentials \
    --store-dir /tmp/lf_stores \
    --checkpoint-dir /tmp/lf_ckpt
```

## 运行（容器）

```bash
docker compose -f launchforge/deploy/docker-compose.yml up --build
```

### 分片（50 游戏 / 5 worker，每 worker 10 游戏）

给不同 worker 传不同 `GAMES` 环境变量即可，例如：

```bash
docker run --rm \
  -e GAMES=game_00,game_01,game_02,game_03,game_04,game_05,game_06,game_07,game_08,game_09 \
  -e MAX_CONCURRENT=8 \
  -v "$PWD/credentials:/app/credentials:ro" \
  -v lf_stores:/app/data/stores \
  -v lf_checkpoints:/app/data/checkpoints \
  launchforge-worker
```

---

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `GAMES_DIR` | `""` | 游戏配置 JSON 目录（每游戏一个 `*.json`，`GameConfig`）；空则用 `N_GAMES` 合成 |
| `N_GAMES` | `12` | 无配置目录时的合成游戏数 |
| `STORE_DIR` | `/app/data/stores` | JSONL 状态卷 |
| `CHECKPOINT_DIR` | `/app/data/checkpoints` | 运行时检查点卷 |
| `CREDENTIALS_DIR` | `""` | 密钥只读卷；设了才启用 per-game 隔离 |
| `GAMES` | `""` | 分片：逗号分隔的 slug 子集 |
| `MAX_CONCURRENT` | `8` | Scheduler 池大小 = 资源限流单位 |
| `DAILY_CYCLES` | `1` | 每游戏每日决策循环数 |
| `ONCE` | `""` | 设任意值 = 跑一轮每日周期后退出（冒烟/测试） |
| `INTERVAL_SECONDS` | `86400` | 常驻模式下一轮间隔（秒） |

---

## 真联通说明

本 worker 的所有「执行」仍走 E13.3.3 的 gated mock Executor（`real_api_called`
锁死 `false`）。要真连 AppLovin MAX / RemoteConfig，需：
1. 在 `credentials/<game>/` 提供真实 key；
2. 把 `ProviderRegistry` 的 `RealMaxClient` seam（`arm_real_client` hook）接上真实 SDK；
3. 解锁生产沙箱策略（需人工评审闸门）。

沙箱（本机）不会伪造任何 API 调用。
