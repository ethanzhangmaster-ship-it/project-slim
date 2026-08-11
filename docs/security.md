# Security Guide

## Secret Management

All secrets MUST go through `SecretManager`. Never hardcode tokens.

```python
from security import SecretManager

sm = SecretManager(credentials_dir="credentials")
sm.register_required("MAX_REPORT_KEY", "AppLovin MAX Report API key")
sm.register_required("PLAY_SERVICE_ACCOUNT", "Google Play service account JSON")

# Validate at startup
sm.validate_or_raise()

# Use
key = sm.get("MAX_REPORT_KEY")
```

## Environment Variables

Copy `.env.example` to `.env` and fill in values.

**NEVER commit `.env` to git.**

## Scanning

Run the scanner to detect hardcoded secrets:

```bash
python -c "
from security.secrets.scanner import SecretScanner
r = SecretScanner().scan('src', 'operation', 'monetization')
print(r.to_markdown())"
```

Tests intentionally contain synthetic secret-shaped fixtures to verify detection and
must not be mixed into the production-source gate. They remain covered by the scanner's
own unit tests and the full pytest release gate.

## Agent Permissions

Each agent declares its resource access:

```python
from security.permissions import Resource, Action, AgentPermission

# ASO Agent: can read store data, write experiments, read/write memory
```

## Pre-commit Checklist

- [ ] No hardcoded tokens in source
- [ ] `.env` is gitignored
- [ ] Credential JSON files are gitignored
- [ ] Secret scanner returns clean
- [ ] Environment validator passes
