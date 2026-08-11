"""
E15.3 §2 — Config Deployer.

Takes ExperimentBinder output (control + variant RemoteConfig pair) and writes
them to the outputs/configs/ tree where the SDK's GFRemoteConfig can fetch.

Also writes a manifest.json so the SDK knows which experiment is active and
can hash-allocate users to control/variant deterministically.
"""
from __future__ import annotations
import json, os
from typing import Dict, Optional
from datetime import date as _date

from operation.remote_config.models import RemoteConfig


class ConfigDeployer:
    OUTPUT = "outputs/configs"

    def deploy(self, control: RemoteConfig, variant: RemoteConfig,
               game_id: str, experiment_id: str,
               output_dir: str = "") -> Dict:
        root = output_dir or self.OUTPUT
        game_dir = os.path.join(root, game_id)
        os.makedirs(game_dir, exist_ok=True)

        # flat JSON for SDK consumption
        for cfg, tag in ((control, "control"), (variant, "variant")):
            path = os.path.join(
                game_dir, f"{experiment_id}_{tag}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg.to_flat_dict(), f, ensure_ascii=False)

        # manifest
        manifest = {
            "game_id": game_id,
            "experiment_id": experiment_id,
            "created_at": _date.today().isoformat(),
            "control": control.to_flat_dict(),
            "variant": variant.to_flat_dict(),
            "allocation": {"control": 0.5, "variant": 0.5},
        }
        manifest_path = os.path.join(game_dir, f"{experiment_id}_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        return {
            "game_id": game_id, "experiment_id": experiment_id,
            "control_path": os.path.join(game_dir, f"{experiment_id}_control.json"),
            "variant_path": os.path.join(game_dir, f"{experiment_id}_variant.json"),
            "manifest_path": manifest_path,
        }
