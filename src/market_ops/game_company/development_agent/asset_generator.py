from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GeneratedAsset:
    asset_id: str
    asset_type: str
    asset_name: str
    status: str = "generated"
    quality: float = 0.0


class AssetGenerator:
    def __init__(self):
        self.assets: Dict[str, GeneratedAsset] = {}

    def generate(self, genre_or_type, asset_types: List[str] = None, style: str = "cozy") -> Any:
        if isinstance(genre_or_type, str) and isinstance(asset_types, list):
            assets = []
            asset_names = {"sprites": ["item_1", "item_2", "item_3"], "ui": ["btn", "panel", "icon"], "audio": ["bgm", "sfx"], "particles": ["sparkle", "burst"], "buildings": ["house", "shop"]}
            
            for asset_type in asset_types:
                names = asset_names.get(asset_type, ["default"])
                for name in names:
                    asset = GeneratedAsset(
                        asset_id=f"asset_{hash(asset_type + name) % 10000:04d}",
                        asset_type=asset_type,
                        asset_name=f"{asset_type}_{name}",
                        status="generated",
                        quality=self._calculate_quality(asset_type, style),
                    )
                    self.assets[asset.asset_id] = asset
                    assets.append(asset)
                    if len(assets) >= len(asset_types) * 2:
                        break
            
            return assets
        
        asset = GeneratedAsset(
            asset_id=f"asset_{hash(str(genre_or_type)) % 10000:04d}",
            asset_type=genre_or_type,
            asset_name=str(genre_or_type),
            status="generated",
            quality=self._calculate_quality(str(genre_or_type), style),
        )
        self.assets[asset.asset_id] = asset
        return asset

    def generate_batch(self, asset_specs: List[Dict[str, Any]], style: str = "cozy") -> List[GeneratedAsset]:
        assets = []
        for spec in asset_specs:
            asset = self.generate(spec["type"], spec["name"], style)
            assets.append(asset)
        return assets

    def _calculate_quality(self, asset_type: str, style: str) -> float:
        base_quality = 0.85
        
        if asset_type in ["character", "environment"]:
            base_quality += 0.05
        if asset_type == "icon":
            base_quality += 0.05
        
        if style == "cozy":
            base_quality += 0.03
        
        return min(base_quality, 0.95)

    def generate_demo(self) -> List[GeneratedAsset]:
        specs = [
            {"type": "sprite", "name": "merge_item_1"},
            {"type": "sprite", "name": "merge_item_2"},
            {"type": "character", "name": "witch_char"},
            {"type": "environment", "name": "garden_bg"},
            {"type": "ui", "name": "btn_primary"},
        ]
        return self.generate_batch(specs, "cozy")
