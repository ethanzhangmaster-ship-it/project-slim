"""UA Connector Module — V3.8.1 Real UA Validation Layer

连接 Facebook/TikTok/Google Ads 真实买量数据。
"""

from .facebook_connector import FacebookConnector
from .tiktok_connector import TikTokConnector
from .google_ads_connector import GoogleAdsConnector

__all__ = [
    "FacebookConnector",
    "TikTokConnector",
    "GoogleAdsConnector",
]
