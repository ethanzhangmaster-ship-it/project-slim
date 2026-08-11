"""V4.0 Creative Intelligence Platform — Repository Adapters.

Bridges to existing modules:
  - Facebook adapter → wraps existing Facebook API + performance data
  - Adjust adapter → wraps existing Adjust data
  - Eagle adapter → wraps existing Creative Mapping Engine
"""

from .facebook_adapter import FacebookAdapter
from .adjust_adapter import AdjustAdapter
from .eagle_adapter import EagleAdapter

__all__ = ["FacebookAdapter", "AdjustAdapter", "EagleAdapter"]