using System;
using GameFactory.Analytics;
using GameFactory.Analytics.Events;
using GameFactory.Core;
using UnityEngine;
#if GOOGLE_MOBILE_ADS
using GoogleMobileAds.Api;
#endif

namespace GameFactory.Ads
{
    /// <summary>
    /// Google AdMob adapter (standalone, Google Mobile Ads SDK).
    /// Used when config.ads.provider == "AdMob" for direct (non-MAX) integration. AdMob is also a
    /// MAX-mediated network, so you can alternatively run it through MAX — this adapter is the
    /// direct path. Compiles ONLY when GOOGLE_MOBILE_ADS is defined and the Google Mobile Ads
    /// package (com.google.ads.mobileads) is installed; the installer injects the SDK assembly
    /// reference into GameFactory.Ads.AdMob.asmdef automatically.
    /// </summary>
    public class AdMobProvider : IAdProvider
    {
        private AdsConfig _cfg;
        private double _lastRevenue;
        private Action<bool> _pendingReward;
        private long _lastRequestAt;
        private string _lastFormat = "";
#if GOOGLE_MOBILE_ADS
        private InterstitialAd _interstitial;
        private RewardedAd _rewarded;
        private BannerView _banner;
#endif

        public event Action OnInterstitialDisplayed;
        public event Action OnInterstitialHidden;
        public event Action<bool> OnRewardGranted;

        public void Initialize(AdsConfig cfg)
        {
            _cfg = cfg;
#if GOOGLE_MOBILE_ADS
            MobileAds.Initialize(_ =>
            {
                LoadInterstitial();
                LoadRewarded();
                Debug.Log("[AdMobProvider] Initialized");
            });
#else
            Debug.LogWarning("[AdMobProvider] Google Mobile Ads SDK not present; define GOOGLE_MOBILE_ADS to enable.");
#endif
        }

        public void ShowInterstitial()
        {
            _lastFormat = "interstitial";
            _lastRequestAt = CurrentMs();
#if GOOGLE_MOBILE_ADS
            if (_interstitial != null && _interstitial.CanShowAd())
                _interstitial.Show();
            else
                LoadInterstitial(); // try to recover for next time
#endif
        }

        public void ShowReward(Action<bool> onComplete)
        {
            _lastFormat = "reward";
            _lastRequestAt = CurrentMs();
            _pendingReward = onComplete;
#if GOOGLE_MOBILE_ADS
            if (_rewarded != null && _rewarded.CanShowAd())
            {
                _rewarded.Show(_ =>
                {
                    _pendingReward?.Invoke(true);
                    OnRewardGranted?.Invoke(true);
                    _pendingReward = null;
                });
            }
            else
            {
                _pendingReward = null; // not ready; fail fast
            }
#endif
        }

        public void ShowBanner()
        {
            _lastFormat = "banner";
#if GOOGLE_MOBILE_ADS
            if (_banner == null)
            {
                _banner = new BannerView(_cfg.banner_id, AdSize.Banner, AdPosition.Bottom);
                _banner.LoadAd(new AdRequest());
            }
            _banner.Show();
#endif
        }

        public double GetRevenue() => _lastRevenue;

#if GOOGLE_MOBILE_ADS
        private void LoadInterstitial()
        {
            InterstitialAd.Load(_cfg.interstitial_id, new AdRequest(), (ad, error) =>
            {
                if (error != null || ad == null)
                {
                    Debug.LogWarning("[AdMob] interstitial load failed: " + error?.GetMessage());
                    return;
                }
                _interstitial = ad;
                ad.OnAdFullScreenContentOpened += () => OnInterstitialDisplayed?.Invoke();
                ad.OnAdFullScreenContentClosed += () => OnInterstitialHidden?.Invoke();
                ad.OnAdPaid += value => EmitRevenue("interstitial", _cfg.interstitial_id, value);
            });
        }

        private void LoadRewarded()
        {
            RewardedAd.Load(_cfg.reward_id, new AdRequest(), (ad, error) =>
            {
                if (error != null || ad == null)
                {
                    Debug.LogWarning("[AdMob] rewarded load failed: " + error?.GetMessage());
                    return;
                }
                _rewarded = ad;
                ad.OnAdPaid += value => EmitRevenue("reward", _cfg.reward_id, value);
            });
        }

        private void EmitRevenue(string format, string adUnit, AdValue value)
        {
            _lastRevenue = value.Value / 1_000_000.0; // micros -> USD
            var e = new AdRevenueEvent();
            e.Set(adFormat: format,
                  network: "AdMob",
                  placement: "",
                  adUnit: adUnit,
                  revenue: _lastRevenue,
                  country: "",
                  latencyMs: _lastRequestAt > 0 ? CurrentMs() - _lastRequestAt : 0);
            e.game = Analytics.GameSlug;
            // Single delivery path: buffer -> uploader -> Adjust/Firebase. No double-send.
            Analytics.LogEvent(e);
        }
#endif

        private static long CurrentMs() =>
            (long)(DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalMilliseconds;

#if GOOGLE_MOBILE_ADS
        internal static class AdMobProviderRegistration
        {
            [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
            private static void Register()
            {
                AdProviderRegistry.Register("AdMob", () => new AdMobProvider());
            }
        }
#endif
    }
}
