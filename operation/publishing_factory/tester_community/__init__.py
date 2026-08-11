"""12-person Closed Testing Tester Community for Google Play.

Quickstart (one-time setup):

    # 1. Configure the community (give me 12 Gmail addresses):
    python -m operation.publishing_factory.tester_community init \\
        --emails "alice@gmail.com,bob@gmail.com,charlie@gmail.com,
                   dave@gmail.com,eve@gmail.com,frank@gmail.com,
                   grace@gmail.com,henry@gmail.com,iris@gmail.com,
                   jack@gmail.com,kate@gmail.com,liam@gmail.com"

    # 2. Verify / preview:
    python -m operation.publishing_factory.tester_community status
    python -m operation.publishing_factory.tester_community invite \\
        com.ofwsalary.ofwcalculator            # dry-run by default

    # 3. Actually invite (sends emails to the 12 testers via Google Play Edits API):
    python -m operation.publishing_factory.tester_community invite \\
        com.ofwsalary.ofwcalculator --apply

    # 4. Check eligibility progress (days running toward 14):
    python -m operation.publishing_factory.tester_community check

    # 5. Add more members later:
    python -m operation.publishing_factory.tester_community add \\
        --emails newbie@gmail.com
"""
from operation.publishing_factory.tester_community.community import (
    load as community_load,
    save as community_save,
    add_emails,
    add_groups,
    empty_config,
    cred_path,
    status_text,
    _REQUIRED_TESTERS,
    _normalize_emails,
    _normalize_groups,
)
from operation.publishing_factory.tester_community.eligibility import (
    REQUIRED_TESTERS as _REQ_T,
    REQUIRED_DAYS as _REQ_D,
    get as eligibility_get,
    all_apps as eligibility_all_apps,
    render_markdown as eligibility_render_markdown,
)
from operation.publishing_factory.tester_community.inviter import invite as invite_pkg


__all__ = [
    "community_load", "community_save", "add_emails", "add_groups",
    "empty_config", "cred_path", "status_text",
    "eligibility_get", "eligibility_all_apps",
    "eligibility_render_markdown",
    "invite_pkg",
    "_REQUIRED_TESTERS", "_normalize_emails", "_normalize_groups",
]
