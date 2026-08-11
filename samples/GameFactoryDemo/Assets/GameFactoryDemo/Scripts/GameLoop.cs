using GameFactory;
using GameFactory.RemoteConfig;
using UnityEngine;

namespace GameFactory.Samples.GameFactoryDemo
{
    /// <summary>
    /// E13.2.6.2 — verifies the bootstrap / init chain and demonstrates RemoteConfig-driven gameplay.
    /// Logs the expected init summary and auto-advances a trivial "puzzle" level counter; every
    /// `ads.reward_frequency` levels it logs that a rewarded ad is due (pulled live from RemoteConfig).
    /// </summary>
    [AddComponentMenu("GameFactory/Demo/GameLoop")]
    public class GameLoop : MonoBehaviour
    {
        private int _level = 1;

        private void Awake()
        {
            if (!GameFactory.IsInitialized || GameFactory.Config == null)
            {
                Debug.LogWarning("[GameFactory] init did not complete before GameLoop.Awake — check Boot ordering.");
                return;
            }

            var cfg = GameFactory.Config;
            Debug.Log("[GameFactory] Config Loaded: " + cfg.game_name);
            Debug.Log("[GameFactory] Ads Provider: " + cfg.ads.provider);
            Debug.Log("[GameFactory] Analytics: " + string.Join(",", cfg.analytics.providers));
            Debug.Log("[GameFactory] SDK Ready");

            GameFactory.OnReady += () => Debug.Log("[GameFactory] OnReady fired");

            // Trivial puzzle loop: advance a level every 5s; reward cadence from RemoteConfig.
            InvokeRepeating(nameof(AdvanceLevel), 5f, 5f);
        }

        private void AdvanceLevel()
        {
            _level++;
            int freq = RemoteConfigManager.GetInt("ads.reward_frequency");
            if (freq > 0 && _level % freq == 0)
                Debug.Log($"[GameLoop] level {_level} reached — reward due (cadence={freq}, from RemoteConfig)");
            else
                Debug.Log($"[GameLoop] level {_level} (next reward at multiple of {freq})");
        }
    }
}
