"""CLI entry-point for the closed-testing tester community.

Subcommands
-----------
init    one-time setup — seed credentials/tester_community.json with the
        permanent 12-person community (emails + optional Google Groups).
add     append one or more emails or groups to an existing community.
status  show current community configuration.
invite  invite the community (or override list) to an app's closed track.
        --apply performs the real API call (default is dry-run).
check   show per-app closed-testing eligibility (testers/days/prod-ready).

This CLI is what ``tests/e15_1_2/test_tester_community.py`` exercises,
and what the operator runs after ``git pull`` to seed the community.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List

from operation.publishing_factory.tester_community import (
    add_emails as _add_emails,
    add_groups as _add_groups,
    community_load,
    community_save,
    cred_path as _cred_path,
    empty_config,
    eligibility_all_apps,
    eligibility_get,
    eligibility_render_markdown,
    invite_pkg,
    status_text,
    _REQUIRED_TESTERS,
)


def _print_status(st: dict) -> None:
    """Persist the status dict (utf-8, always) and print an ASCII-safe
    one-liner so Windows consoles can't crash on CJK diagnostics."""
    try:
        with open("last_tc_status.json", "w", encoding="utf-8") as fh:
            json.dump(st, fh, ensure_ascii=False, indent=2)
    except Exception:  # noqa: BLE001
        pass
    print(f">>> TC RESULT: ok={st.get('ok')} stage={st.get('stage')} "
          f"testers={st.get('tester_count')} "
          f"http_status={st.get('http_status')}",
          flush=True)
    text = json.dumps(st, ensure_ascii=False, indent=2)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(json.dumps(st, ensure_ascii=True, indent=2), flush=True)


# --------------------------------------------------------------------- #
# Sub-commands
# --------------------------------------------------------------------- #
def cmd_init(args: argparse.Namespace) -> int:
    emails: List[str] = []
    if args.emails:
        emails = [e.strip() for e in args.emails.split(",") if e.strip()]
    groups: List[str] = []
    if args.groups:
        groups = [g.strip() for g in args.groups.split(",") if g.strip()]
    try:
        norm_emails = _require_min(emails, "emails")
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    try:
        norm_groups = _require_min_groups(groups)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    cfg = empty_config()
    cfg["emails"] = norm_emails
    cfg["groups"] = norm_groups
    cfg["note"] = args.note or (
        f"Closed-testing tester community (12+). "
        f"Setup with operation.publishing_factory.tester_community init.")
    p = community_save(cfg)
    print(f"OK: wrote {p}")
    print(f"     emails={len(norm_emails)} (target: {_REQUIRED_TESTERS}+)")
    print(f"     groups={len(norm_groups)}")
    if len(norm_emails) < _REQUIRED_TESTERS and not norm_groups:
        print(f"\nWARN: only {len(norm_emails)} emails (target "
              f"{_REQUIRED_TESTERS}+). You can still save, just add more "
              f"later via `tester_community add --emails ...`.")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    if not (args.emails or args.groups):
        print("ERROR: provide --emails (comma-separated) or --groups")
        return 2
    p = None
    if args.emails:
        try:
            p = _add_emails([e.strip() for e in args.emails.split(",")
                              if e.strip()])
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 2
    if args.groups:
        try:
            p = _add_groups([g.strip() for g in args.groups.split(",")
                              if g.strip()])
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 2
    print(f"OK: appended -> {p}")
    print(status_text())
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    print(status_text())
    return 0


def cmd_invite(args: argparse.Namespace) -> int:
    apply_real = bool(args.apply)
    tester_emails = None
    tester_groups = None
    if args.emails:
        tester_emails = [e.strip() for e in args.emails.split(",")
                          if e.strip()]
    if args.groups:
        tester_groups = [g.strip() for g in args.groups.split(",")
                          if g.strip()]
    st = invite_pkg(
        args.package,
        apply=apply_real,
        tester_emails=tester_emails,
        tester_groups=tester_groups,
    )
    _print_status(st)
    return 0 if st.get("ok") else 1


def cmd_check(args: argparse.Namespace) -> int:
    if args.package:
        rows = [eligibility_get(args.package)]
    else:
        rows = eligibility_all_apps()
    md = eligibility_render_markdown(rows)
    print(md)
    return 0


def _require_min(values, label):
    """Validate basic email shape only — don't enforce the 12 hard so
    that the user can incrementally add people."""
    from operation.publishing_factory.tester_community.community import (
        _normalize_emails)
    return _normalize_emails(values)


def _require_min_groups(values):
    from operation.publishing_factory.tester_community.community import (
        _normalize_groups)
    return _normalize_groups(values)


# --------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(
        prog="tester_community",
        description=("12-person Closed Testing Tester Community for Google "
                     "Play. One-time setup, reused across all new apps."))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="one-time setup")
    p_init.add_argument("--emails", help="comma-separated 12+ Gmail addresses")
    p_init.add_argument("--groups", help="comma-separated Google Groups")
    p_init.add_argument("--note", help="optional note (default: auto)")
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="append emails/groups to existing community")
    p_add.add_argument("--emails", help="comma-separated emails to add")
    p_add.add_argument("--groups", help="comma-separated groups to add")
    p_add.set_defaults(func=cmd_add)

    p_status = sub.add_parser("status", help="show community configuration")
    p_status.set_defaults(func=cmd_status)

    p_invite = sub.add_parser("invite",
                              help="invite community to a package's closed track")
    p_invite.add_argument("package", help="target package_name")
    p_invite.add_argument("--apply", action="store_true",
                          help="actually send invites (default: dry-run)")
    p_invite.add_argument("--emails", help="override tester emails (csv)")
    p_invite.add_argument("--groups", help="override tester groups (csv)")
    p_invite.set_defaults(func=cmd_invite)

    p_check = sub.add_parser("check",
                             help="show per-app closed-testing eligibility")
    p_check.add_argument("package", nargs="?", help="specific package "
                          "(omit for all tracked)")
    p_check.set_defaults(func=cmd_check)

    args = ap.parse_args()
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
