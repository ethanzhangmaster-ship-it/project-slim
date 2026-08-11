using System;
using GameFactory.Analytics;
using GameFactory.Analytics.Events;
using GameFactory.Core;
using UnityEngine;

namespace GameFactory.Ads
{
    /// <summary>
    /// Facade matching the E13.1 PRD interface.
    ///   AdsManager.ShowReward(onComplete);
    ///   AdsManager.ShowInterstitial();
    ///   double rev = AdsManager.GetRevenue();
    /// Routes to the provider registered for config.ads.provider (MAX / LevelPlay / ...).
    ///
    /// E13.2.7: every ad interaction also emits a structured event through Analytics.LogEvent
    /// (ad_request / ad_show / ad_complete) so the Reality Dataset can compute fill rate,
    /// display rate, close rate and reward-completion rate — the inputs E13.3's agent needs.
    /// </summary>
    public static class AdsManager
    {
        private static IAdProvider _provider;
        private static AdsConfig _cfg;

        public static event Action OnInterstitialDisplayed;
        public static event Action OnInterstitialHidden;
        public static event Action<bool> OnRewardGranted;

        public static void Initialize(AdsConfig cfg)
        {
            _cfg = cfg;
            if (cfg == null) return;
            _provider = AdProviderRegistry.Create(cfg.provider);
            if (_provider == null)
            {
                Debug.LogWarning("[AdsManager] no provider registered for '" + cfg.provider +
                                 "'. Install the matching SDK and enable its scripting define.");
                return;
            }
            _provider.OnInterstitialDisplayed += () =>
            {
                OnInterstitialDisplayed?.Invoke();
                Analytics.LogEvent(GameplayEvent.AdShow("interstitial", _cfg.interstitial_id));
            };
            _provider.OnInterstitialHidden += () =>
            {
                OnInterstitialHidden?.Invoke();
                Analytics.LogEvent(GameplayEvent.AdComplete("interstitial", _cfg.interstitial_id, true));
            };
            _provider.OnRewardGranted += granted =>
            {
                OnRewardGranted?.Invoke(granted);
                if (granted)
                {
                    Analytics.LogEvent(GameplayEvent.AdShow("reward", _cfg.reward_id));
                    Analytics.LogEvent(GameplayEvent.AdComplete("reward", _cfg.reward_id, true));
                }
            };
            _provider.Initialize(cfg);
        }

        public static void ShowInterstitial()
        {
            Analytics.LogEvent(GameplayEvent.AdRequest("interstitial", _cfg?.interstitial_id ?? ""));
            _provider?.ShowInterstitial();
        }

        public static void ShowReward(Action<bool> onComplete)
        {
            Analytics.LogEvent(GameplayEvent.AdRequest("reward", _cfg?.reward_id ?? ""));
            _provider?.ShowReward(onComplete);
        }

        public static void ShowBanner() => _provider?.ShowBanner();
        public static double GetRevenue() => _provider?.GetRevenue() ?? 0d;
    }
}
