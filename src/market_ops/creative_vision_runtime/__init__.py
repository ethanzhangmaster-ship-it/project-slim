"""E11.3 — Creative Vision Runtime。

CreativeEntity.asset → VisionAsset → Frame → Feature → DNA。

E11.3.1 Vision Asset Loader: CreativeEntity → VisionAsset（当前阶段）
E11.3.2 Frame Extraction:      VisionAsset → KeyFrames（后续）
E11.3.3 Vision Feature Store:  KeyFrames → Features（后续）
E11.3.4 Creative DNA Extractor: Features → CreativeDNA（后续）
E11.3.5 DNA Validation:        CreativeDNA → Validated DNA（后续）

与 E11.2 Asset Runtime 分离，各自独立运行。
"""