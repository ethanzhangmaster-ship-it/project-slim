using GameFactory;
using GameFactory.Analytics;
using GameFactory.Analytics.Data;
using GameFactory.Analytics.Events;
using UnityEngine;

namespace GameFactoryDemo
{
    /// <summary>
    /// E13.2.7 harness: emits one of every standardized event through the event layer, then
    /// flushes the buffer. Run it in the GameFactoryDemo after GameFactory is ready to confirm
    /// the whole chain (event -> buffer -> uploader -> Adjust/Firebase) works end to end.
    /// </summary>
    public class MonetizationTest : MonoBehaviour
    {
        private void Start()
        {
            if (GameFactory.IsInitialized) Run();
            else GameFactory.OnReady += Run;
        }

        private void OnDestroy() => GameFactory.OnReady -= Run;

        private void Run()
        {
            Log("=== GameFactory Monetization Events (E13.2.7) ===");

            Analytics.LogEvent(GameplayEvent.Install());
            Analytics.LogEvent(GameplayEvent.SessionStart());
            Analytics.LogEvent(GameplayEvent.LevelStart(1));
            Analytics.LogEvent(GameplayEvent.LevelComplete(1, 100));
            Analytics.LogEvent(GameplayEvent.AdRequest("reward", "reward_01", "applovin"));
            Analytics.LogEvent(GameplayEvent.AdShow("reward", "reward_01"));
            Analytics.LogEvent(GameplayEvent.AdComplete("reward", "reward_01", true));

            var rev = new AdRevenueEvent();
            rev.Set(adFormat: "reward", network: "applovin", placement: "reward_01",
                    adUnit: "reward_01", revenue: 0.0325, country: "US", latencyMs: 350);
            Analytics.LogEvent(rev);

            Analytics.LogEvent(GameplayEvent.Purchase("remove_ads", 2.99, "USD"));

            Analytics.FlushEvents();
            Log("Buffered events flushed. Buffer count after flush = " + Analytics.BufferedEventCount());
            Log("Open the integration log / Adjust & Firebase dashboards to confirm delivery.");
        }

        private static void Log(string s) => Debug.Log("[MonetizationTest] " + s);
    }
}
