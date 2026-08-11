"""E15.2.8 tests — shared helpers."""
import os, json, tempfile
from operation.player_monetization.events.collector import SyntheticProvider
from operation.player_monetization.models import PlayerProfile
from operation.remote_config.models import RemoteConfig



def synthetic_events(n_users=3):
    ev = []
    for i in range(n_users):
        ev.extend(SyntheticProvider().one_user(f"u{i}", ad_requests=10, ad_shows=8))
    return ev


def write_jsonl(path, events):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def default_cfg(game_id="com.gf.test"):
    return RemoteConfig.default_for(game_id)
