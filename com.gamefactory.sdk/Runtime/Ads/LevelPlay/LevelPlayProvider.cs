using System;
using System.Collections.Generic;
using GameFactory.Analytics;
using GameFactory.Analytics.Events;
using GameFactory.Core;
using UnityEngine;

namespace GameFactory.Ads
{
    /// <summary>
    /// ironSource LevelPlay adapter (the mediation Watermelon Core already wires in BusStop).
    /// This assembly (GameFactory.Ads.LevelPlay) compiles ONLY when MODULE_LEVELPLAY is defined
    /// and the LevelPlay/IronSource package is installed. The installer injects the LevelPlay
    /// SDK assembly reference into GameFactory.Ads.LevelPlay.asmdef automatically. Keeping
    /// MODULE_LEVELPLAY means BusStop's existing path works without ripping out Watermelon.
    /// </summary>
    public class LevelPlayProvider : IAdProvider
    {
        private AdsConfig _cfg;
        private double _lastRevenue;
        private Action<bool> _pendingReward;
        private long _rewardRequestAt;
        private long _interstitialRequestAt;

        public event Action OnInterstitialDisplayed;
        public event Action OnInterstitialHidden;
        public event Action<bool> OnRewardGranted;

        public void Initialize(AdsConfig cfg)
        {
            _cfg = cfg;
            IronSource.Agent.init(_cfg.app_key);
            IronSource.Agent.shouldTrackNetworkState(true);

            IronSourceEvents.onRewardedVideoAdRewardedEvent += OnRewarded;
            IronSourceEvents.onRewardedVideoAdClosedEvent += OnRewardedClosed;
            IronSourceEvents.onInterstitialAdOpenedEvent += () => OnInterstitialDisplayed?.Invoke();
            IronSourceEvents.onInterstitialAdClosedEvent += () => { OnInterstitialHidden?.Invoke(); OnInterstitialClosed(); };
            IronSourceEvents.onImpressionDataEvent += OnImpressionData;

            IronSource.Agent.loadInterstitial();
            IronSource.Agent.loadRewardedVideo();
            Debug.Log("[LevelPlayProvider] Initialized");
        }

        public void ShowInterstitial()
        {
            _interstitialRequestAt = CurrentMs();
            if (IronSource.Agent.isInterstitialReady())
                IronSource.Agent.showInterstitial();
        }

        public void ShowReward(Action<bool> onComplete)
        {
            _rewardRequestAt = CurrentMs();
            _pendingReward = onComplete;
            if (IronSource.Agent.isRewardedVideoAvailable())
                IronSource.Agent.showRewardedVideo();
            else
                _pendingReward = null;
        }

        public void ShowBanner()
        {
            IronSource.Agent.loadBanner(IronSourceBannerSize.BANNER, IronSourceBannerPosition.BOTTOM);
            IronSource.Agent.displayBanner();
        }

        public double GetRevenue() => _lastRevenue;

        private void OnRewarded(IronSourcePlacement placement)
        {
            _pendingReward?.Invoke(true);
            OnRewardGranted?.Invoke(true);
        }
        private void OnRewardedClosed() { if (_pendingReward != null) { _pendingReward.Invoke(true); _pendingReward = null; } }
        private void OnInterstitialClosed() { IronSource.Agent.loadInterstitial(); }

        private void OnImpressionData(IronSourceImpressionData data)
        {
            _lastRevenue = data.revenue;
            string fmt = FormatOf(data.adUnit);
            long latency = fmt == "reward" ? CurrentMs() - _rewardRequestAt
                         : fmt == "interstitial" ? CurrentMs() - _interstitialRequestAt : 0;

            var e = new AdRevenueEvent();
            e.Set(adFormat: fmt,
                  network: data.adNetwork,
                  placement: data.placement,
                  adUnit: data.adUnit,
                  revenue: data.revenue,
                  country: data.country,
                  latencyMs: latency);
            e.game = Analytics.GameSlug;
            // Single delivery path: buffer -> uploader -> Adjust/Firebase. No double-send.
            Analytics.LogEvent(e);
        }

        private string FormatOf(string adUnit)
        {
            if (adUnit == _cfg.reward_id) return "reward";
            if (adUnit == _cfg.interstitial_id) return "interstitial";
            if (adUnit == _cfg.banner_id) return "banner";
            return "unknown";
        }

        private static long CurrentMs() =>
            (long)(DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalMilliseconds;

#if MODULE_LEVELPLAY
        internal static class LevelPlayProviderRegistration
        {
            [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
            private static void Register()
            {
                AdProviderRegistry.Register("LevelPlay", () => new LevelPlayProvider());
            }
        }
#endif
    }
}
