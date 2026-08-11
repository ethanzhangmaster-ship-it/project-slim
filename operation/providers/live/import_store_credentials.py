"""
P3 — Store credential import tool (one command, zero friction).
===============================================================

Usage:
    # Check store credential status
    python -m operation.providers.live.import_store_credentials

    # Import App Store Connect (.p8 file on disk)
    python -m operation.providers.live.import_store_credentials \
        --app-store --key-id XXXXXX --issuer-id YYYYYY \
        --p8-file "C:/path/to/AuthKey_XXXXXX.p8"

    # Import App Store Connect (paste the key inline)
    python -m operation.providers.live.import_store_credentials \
        --app-store --key-id XXXXXX --issuer-id YYYYYY \
        --p8-content "-----BEGIN PRIVATE KEY-----\nMIGTAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBH..."

    # Import Google Play (path to service account JSON)
    python -m operation.providers.live.import_store_credentials \
        --google-play --sa-json "C:/path/to/service-account.json"

    # Import both in one call
    python -m operation.providers.live.import_store_credentials \
        --app-store --key-id X --issuer-id Y --p8-file "C:/...p8" \
        --google-play --sa-json "C:/...json"

    # After importing, enable live mode
    python -m operation.providers.live.import_store_credentials \
        --live-enable

The script NEVER sends credentials anywhere — they are written only to
<workspace-root>/credentials/store_keys.json (git-ignored, same directory
as live_accounts.json). The filesystem never leaves your machine.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Same root as store_keys.py (4 levels up from this directory)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))))
_VAULT = os.path.join(_ROOT, "credentials", "store_keys.json")
_CREDENTIALS_DIR = os.path.join(_ROOT, "credentials")


def _print_status():
    """Print current store credential status."""
    from .store_keys import has_any, get_appstore, get_googleplay, load

    print("=== Store credential vault status ===")
    print(f"  vault path : {_VAULT}")
    print(f"  vault exists : {os.path.exists(_VAULT)}")

    as_ = get_appstore()
    gp = get_googleplay()
    print(f"  App Store Connect  : {'✅ configured' if as_ else '❌ missing'}")
    print(f"  Google Play        : {'✅ configured' if gp else '❌ missing'}")

    # LAUNCHFORGE_STORE_LIVE env var
    live = os.environ.get("LAUNCHFORGE_STORE_LIVE")
    live_file = os.path.join(_CREDENTIALS_DIR, ".env_store_live")
    if live != "1" and os.path.exists(live_file):
        try:
            with open(live_file) as f:
                if "LAUNCHFORGE_STORE_LIVE=1" in f.read():
                    live = "1 (via file)"
        except OSError:
            pass
    print(f"  LAUNCHFORGE_STORE_LIVE = {live or '(not set — dry-run mode)'}")

    if has_any():
        is_live = live and str(live) not in ("", "0")
        if is_live:
            print("\n  🔒 Live mode ACTIVE — daily briefing will call store APIs.")
            print("     Disable: python -m operation.providers.live.import_store_credentials --live-disable")
        else:
            print("\n  🔒 Credentials present but dry-run. To go live:")
            print("     python -m operation.providers.live.import_store_credentials --live-enable")
    else:
        print("\n  ⚠️  No store credentials yet. Use --help for import commands.")


def _import_appstore(args):
    from .store_keys import set_appstore

    p8 = args.p8_content
    if args.p8_file:
        if not os.path.exists(args.p8_file):
            print(f"❌ p8 file not found: {args.p8_file}")
            return 1
        try:
            with open(args.p8_file, "r", encoding="utf-8") as f:
                p8 = f.read()
        except OSError as exc:
            print(f"❌ Cannot read p8 file: {exc}")
            return 1

    if not p8:
        print("❌ --p8-content or --p8-file is required for App Store Connect")
        return 1
    if not p8.strip().startswith("-----BEGIN"):
        print("⚠️  p8 content doesn't start with '-----BEGIN PRIVATE KEY-----'")
        print("   This may still work, but double-check you pasted the full key.")
    if not args.key_id:
        print("❌ --key-id is required for App Store Connect")
        return 1
    if not args.issuer_id:
        print("❌ --issuer-id is required for App Store Connect")
        return 1

    set_appstore(args.key_id, args.issuer_id, p8.strip())
    print(f"✅ App Store Connect credentials written to {_VAULT}")
    print(f"   key_id={args.key_id}, issuer_id={args.issuer_id}")
    print(f"   (private_key_p8: {len(p8.strip())} chars)")
    return 0


def _import_googleplay(args):
    from .store_keys import set_googleplay

    sa_path = args.sa_json
    if not sa_path:
        print("❌ --sa-json (path to service account JSON) is required for Google Play")
        return 1
    abs_sa = os.path.abspath(sa_path)
    if not os.path.exists(abs_sa):
        print(f"❌ Service account JSON not found: {abs_sa}")
        return 1
    try:
        with open(abs_sa, "r", encoding="utf-8") as f:
            test = json.load(f)
        if "client_email" not in test:
            print("⚠️  The JSON doesn't look like a Google Play service account (missing client_email)")
            print("   Writing anyway, but double-check.")
    except (OSError, json.JSONDecodeError) as exc:
        print(f"❌ Cannot parse service account JSON: {exc}")
        return 1

    set_googleplay(abs_sa)
    print(f"✅ Google Play credentials written to {_VAULT}")
    print(f"   service_account_json_path = {abs_sa}")
    print(f"   client_email = {test.get('client_email', '?')}")
    return 0


def _enable_live():
    """Persist LAUNCHFORGE_STORE_LIVE=1 into the user env."""
    env_path = os.path.join(_CREDENTIALS_DIR, ".env_store_live")
    try:
        os.makedirs(_CREDENTIALS_DIR, exist_ok=True)
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("LAUNCHFORGE_STORE_LIVE=1\n")
        print(f"✅ Live mode enabled (written to {env_path})")
        print()
        print("   The daily briefing automatically reads this file — no other")
        print("   setup is needed. The next 09:30 run will pull real status.")
        print()
        print("   To disable later:")
        print("     python -m operation.providers.live.import_store_credentials --live-disable")
    except OSError as exc:
        print(f"❌ Cannot write env file: {exc}")
        return 1
    return 0


def _disable_live():
    env_path = os.path.join(_CREDENTIALS_DIR, ".env_store_live")
    try:
        if os.path.exists(env_path):
            os.remove(env_path)
        print(f"✅ Live mode disabled (removed {env_path})")
        print("   Now in dry-run mode — store status API calls will not be made.")
    except OSError as exc:
        print(f"❌ Cannot remove env file: {exc}")
        return 1
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if not argv:
        _print_status()
        return 0

    # short-circuit for --live-enable/--live-disable (no credential args needed)
    if argv == ["--live-enable"]:
        return _enable_live()
    if argv == ["--live-disable"]:
        return _disable_live()

    # no credential flags -> status only
    known_flags = {"--app-store", "--key-id", "--issuer-id",
                   "--p8-file", "--p8-content", "--google-play", "--sa-json"}
    if not any(a in known_flags for a in argv):
        _print_status()
        return 0

    p = argparse.ArgumentParser(
        prog="python -m operation.providers.live.import_store_credentials",
        description="Import & verify App Store Connect / Google Play credentials.")

    p.add_argument("--app-store", action="store_true",
                   help="import App Store Connect credentials")
    p.add_argument("--key-id", default="",
                   help="App Store Connect key ID (e.g. ABC123DEFG)")
    p.add_argument("--issuer-id", default="",
                   help="App Store Connect issuer ID (UUID)")
    p.add_argument("--p8-file", default="",
                   help="path to the .p8 private key file (e.g. AuthKey_ABC123.p8)")
    p.add_argument("--p8-content", default="",
                   help="paste the .p8 private key content inline")

    p.add_argument("--google-play", action="store_true",
                   help="import Google Play Console credentials")
    p.add_argument("--sa-json", default="",
                   help="path to the Google Play service account JSON file")

    p.add_argument("--live-enable", action="store_true",
                   help="enable live store API calls (set LAUNCHFORGE_STORE_LIVE=1)")
    p.add_argument("--live-disable", action="store_true",
                   help="disable live store API calls")

    args = p.parse_args(argv)

    if args.live_enable:
        return _enable_live()
    if args.live_disable:
        return _disable_live()

    ret = 0
    if args.app_store:
        ret |= _import_appstore(args)
    if args.google_play:
        ret |= _import_googleplay(args)
    if not args.app_store and not args.google_play and \
       not args.live_enable and not args.live_disable:
        _print_status()
    return ret


if __name__ == "__main__":
    sys.exit(main())
