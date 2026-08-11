using System;
using System.Collections.Generic;
using GameFactory.Analytics;
using GameFactory.Analytics.Events;
using GameFactory.Core;
using UnityEngine;

namespace GameFactory.Ads
{
    /// <summary>
    /// AppLovin MAX adapter (legacy MaxSdk).
    /// This assembly (GameFactory.Ads.Max) is compiled ONLY when the APPLOVIN_MAX scripting
    /// define is set AND the MaxSdk package is installed (see GameFactory.Ads.Max.asmdef
    /// defineConstraints). So MaxSdk types are always available here. Recommended for new games.
    /// </summary>
    public class MaxAdProvider : IAdProvider
    {
        private AdsConfig _cfg;
        private double _lastRevenue;
        private Action<bool> _pendingReward;
        private long _lastRequestAt;
        private string _lastFormat = "";

        public event Action OnInterstitialDisplayed;
        public event Action OnInterstitialHidden;
        public event Action<bool> OnRewardGranted;

        public void Initialize(AdsConfig cfg)
        {
            _cfg = cfg;
            MaxSdk.SetSdkKey(_cfg.app_key);
            MaxSdk.InitializeSdk();
            MaxSdkCallbacks.OnAdRevenuePaidEvent += OnAdRevenuePaid;

            MaxSdkCallbacks.Interstitial.OnAdDisplayedEvent += (adUnitId, info) =>
                OnInterstitialDisplayed?.Invoke();
            MaxSdkCallbacks.Interstitial.OnAdHiddenEvent += (adUnitId, info) =>
                OnInterstitialHidden?.Invoke();

            MaxSdkCallbacks.Rewarded.OnAdReceivedRewardEvent += (adUnitId, reward) =>
            {
                _pendingReward?.Invoke(true);
                _pendingReward = null;
                OnRewardGranted?.Invoke(true);
            };
            MaxSdkCallbacks.Rewarded.OnAdHiddenEvent += (adUnitId, info) =>
            {
                if (_pendingReward != null) { _pendingReward.Invoke(true); _pendingReward = null; }
            };
            Debug.Log("[MaxAdProvider] Initialized");
        }

        public void ShowInterstitial()
        {
            _lastFormat = "interstitial";
            _lastRequestAt = CurrentMs();
            if (MaxSdk.IsInterstitialReady(_cfg.interstitial_id))
                MaxSdk.ShowInterstitial(_cfg.interstitial_id);
        }

        public void ShowReward(Action<bool> onComplete)
        {
            _lastFormat = "reward";
            _lastRequestAt = CurrentMs();
            _pendingReward = onComplete;
            if (MaxSdk.IsRewardedAdReady(_cfg.reward_id))
                MaxSdk.ShowRewardedAd(_cfg.reward_id);
            else
                _pendingReward = null; // not ready; fail fast
        }

        public void ShowBanner()
        {
            _lastFormat = "banner";
            MaxSdk.CreateBanner(_cfg.banner_id, MaxSdkBase.BannerPosition.BottomCenter);
            MaxSdk.ShowBanner(_cfg.banner_id);
        }

        public double GetRevenue() => _lastRevenue;

        private void OnAdRevenuePaidEvent(MaxSdkBase.AdInfo adInfo)
        {
            _lastRevenue = adInfo.Revenue;
            var fmt = FormatOf(adInfo.AdUnitIdentifier);
            long latency = _lastRequestAt > 0 ? CurrentMs() - _lastRequestAt : 0;

            var e = new AdRevenueEvent();
            e.Set(adFormat: fmt,
                  network: adInfo.NetworkName,
                  placement: adInfo.Placement,
                  adUnit: adInfo.AdUnitIdentifier,
                  revenue: adInfo.Revenue,
                  country: adInfo.CountryCode,
                  latencyMs: latency);
            e.game = Analytics.GameSlug;
            // Single delivery path: buffer -> uploader -> Adjust/Firebase. No double-send.
            Analytics.LogEvent(e);
        }

        private string FormatOf(string adUnitId)
        {
            if (adUnitId == _cfg.reward_id) return "reward";
            if (adUnitId == _cfg.interstitial_id) return "interstitial";
            if (adUnitId == _cfg.banner_id) return "banner";
            return string.IsNullOrEmpty(_lastFormat) ? "unknown" : _lastFormat;
        }

        private static long CurrentMs() =>
            (long)(DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalMilliseconds;

#if APPLOVIN_MAX
        internal static class MaxAdProviderRegistration
        {
            [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
            private static void Register()
            {
                AdProviderRegistry.Register("MAX", () => new MaxAdProvider());
            }
        }
#endif
    }
}
