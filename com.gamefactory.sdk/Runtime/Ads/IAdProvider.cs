using System;
using GameFactory.Core;

namespace GameFactory.Ads
{
    /// <summary>
    /// Adapter contract. Add a new class per standalone network (MAX, LevelPlay, AdMob implemented;
    /// mediated networks such as Meta/Vungle/Mintegral/Pangle/UnityAds/Amazon/InMobi/Chartboost are
    /// connected through MAX/LevelPlay mediation, not as standalone adapters here).
    /// Providers register themselves into AdProviderRegistry (see MaxAdProvider) so the facade
    /// resolves them by config key without a static cross-assembly reference.
    /// </summary>
    public interface IAdProvider
    {
        void Initialize(AdsConfig cfg);
        void ShowInterstitial();
        void ShowReward(Action<bool> onComplete);
        void ShowBanner();
        double GetRevenue(); // latest impression revenue (USD)

        // Lifecycle events (E13.2.6): observable ad states for integration validation.
        event Action OnInterstitialDisplayed;
        event Action OnInterstitialHidden;
        event Action<bool> OnRewardGranted;
    }
}
