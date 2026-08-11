# Per-game credentials (E14.3.5 Credential Isolation)

Each game is a fully isolated tenant. Its secrets live under its own directory
and are ONLY reachable through `monetization.providers.CredentialResolver`,
which confines every lookup to `<root>/<game_id>/` and refuses cross-game
references with `CredentialAccessDenied` (no fallback).

```
credentials/
├── game_a/
│   ├── max.json            # AppLovin MAX keys
│   ├── remote_config.json  # Firebase / GameFactory Config keys
│   └── metadata.json       # non-secret game metadata
└── game_b/
    ├── max.json
    └── remote_config.json
```

> The values shipped here are **fake placeholders** for structure/testing only.
> Replace with real keys per game, and keep this directory out of version
> control in production (add to `.gitignore`).

Provider kind → filename mapping:

| Provider kind        | File                    |
|----------------------|-------------------------|
| `MAX`                | `max.json`              |
| `LevelPlay`          | `levelplay.json`        |
| `RemoteConfig`       | `remote_config.json`    |
| `GameFactoryConfig`  | `gamefactory_config.json` |
