# Deployment Guide

## Local Development

```bash
# 1. Clone
git clone <repo> launchforge
cd launchforge

# 2. Setup env
cp .env.example .env
# Edit .env with your credentials

# 3. Install
pip install -r requirements/dev.txt

# 4. Test
pytest tests/ -v

# 5. Security scan
python -c "from security.secrets.scanner import SecretScanner; print(SecretScanner().scan('src','operation','monetization').to_markdown())"
```

## Docker

```bash
cd deploy
docker-compose up -d
```

Environment variables in `docker-compose.yml`:
- `N_GAMES=12`: number of games to manage
- `GAMES=`: comma-separated game IDs (for sharding)
- `MAX_CONCURRENT=8`: max concurrent operations

## Production Checklist

- [ ] `.env` configured with real credentials
- [ ] `pytest tests/` all green
- [ ] `security scan` returns clean
- [ ] `python -c "from release_gate import gate_check; gate_check()"` is GREEN
- [ ] Docker `docker-compose up` succeeds
- [ ] Agent logs writing to `logs/agent_trace.jsonl`
- [ ] Audit trail writing to `data/audit/`
- [ ] Backups configured via `backup.BackupManager`
- [ ] P4 `ProductionReadinessGate` is ready for the exact production `AgentConfig`
- [ ] One-game dry-run and one-action approved canary completed per `production_runbook.md`

## Sharding

For 50+ games, split across workers:

```bash
# Worker 1: games 1-12
GAMES=witch_merge,puzzle_island,... docker-compose up

# Worker 2: games 13-24
GAMES=word_game_y,merge_kingdom,... docker-compose up
```
