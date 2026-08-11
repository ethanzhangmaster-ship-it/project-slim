using GameFactory.Ads;
using GameFactory.Analytics;
using GameFactory.Core;
using GameFactory.IAP;
using GameFactory.RemoteConfig;
using GameFactory.User;
using UnityEngine;

namespace GameFactory
{
    /// <summary>
    /// Entry point of the SDK. Call GameFactory.Initialize() once at game boot
    /// (e.g. from GameFactoryBootstrap on your first scene, or manually).
    /// Loads gamefactory_config.json from Resources, initializes every subsystem,
    /// then fires OnReady.
    /// </summary>
    public static class GameFactory
    {
        public static event Action OnReady;

        public static GameFactoryConfig Config { get; private set; }
        public static bool IsInitialized { get; private set; }

        public static void Initialize()
        {
            if (IsInitialized) return;

            Config = GameFactoryConfig.LoadFromResources();
            if (Config == null)
            {
                Debug.LogError("[GameFactory] gamefactory_config.json not found under " +
                               "Assets/Resources/GameFactory/. Run 'GameFactory > Setup Project' or " +
                               "launchforge config_generator.");
                return;
            }

            ServiceLocator.Set(Config);
            ServiceLocator.Set(UserManager.Instance);
            Analytics.GameSlug = Config.game_name;

            AdsManager.Initialize(Config.ads);
            Analytics.Initialize(Config.analytics);
            RemoteConfigManager.Initialize(Config.remote_config);
            IAPManager.Initialize(Config.iap);
            UserManager.Initialize();

            IsInitialized = true;
            Debug.Log("[GameFactory] Ready: " + Config.game_name);
            OnReady?.Invoke();
        }
    }
}
