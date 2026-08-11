using System.Collections.Generic;
using GameFactory.Core;
using UnityEngine;

namespace GameFactory.Analytics
{
    /// <summary>
    /// Adjust adapter. This assembly (GameFactory.Analytics.Adjust) compiles ONLY when the
    /// ADJUST_SDK scripting define is set and the Adjust package is installed. Fill EVENT_TOKENS
    /// with the tokens from your Adjust dashboard (the placeholders are illustrative).
    /// </summary>
    public class AdjustProvider : IAnalyticsProvider
    {
        private readonly string _token;

        // event name -> Adjust event token (replace placeholders in your Adjust dashboard)
        private static readonly Dictionary<string, string> EventTokens = new Dictionary<string, string>
        {
            ["tutorial_complete"] = "tut001",
            ["level_start"]       = "lvlsta",
            ["level_complete"]    = "lvlcmp",
            ["level_fail"]        = "lvlfail",
            ["ad_impression"]     = "adimp",
            ["purchase"]          = "purchase",
            ["test_event"]        = "testevt",  // validation-only; replace with a real Adjust event token
        };

        public AdjustProvider(string token) => _token = token;

        public void Track(string eventName, Dictionary<string, object> parameters)
        {
            if (eventName == "ad_revenue") { TrackAdRevenue(parameters); return; }

            if (!EventTokens.TryGetValue(eventName, out var token))
            {
                Debug.Log("[Adjust] no token for " + eventName + " — skipping");
                return;
            }
            var evt = new AdjustEvent(token);
            foreach (var kv in parameters)
                evt.addCallbackParameter(kv.Key, kv.Value?.ToString() ?? "");
            Adjust.trackEvent(evt);
        }

        private void TrackAdRevenue(Dictionary<string, object> p)
        {
            var source = AdjustConfig.AdjustAdRevenueSourceAppLovinMAX;
            var adRev = new AdjustAdRevenue(source);
            if (p.TryGetValue("revenue", out var rev)) adRev.setRevenue(System.Convert.ToDouble(rev), "USD");
            if (p.TryGetValue("network", out var net)) adRev.setAdRevenueNetwork(net?.ToString());
            if (p.TryGetValue("ad_unit", out var unit)) adRev.setAdRevenueUnit(unit?.ToString());
            if (p.TryGetValue("placement", out var place)) adRev.setAdRevenuePlacement(place?.ToString());
            Adjust.trackAdRevenue(adRev);
        }
    }

#if ADJUST_SDK
    internal static class AdjustProviderRegistration
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        private static void Register()
        {
            // token is read at Analytics.Initialize time from config; registry factory ignores it.
            AnalyticsRegistry.Register("Adjust", () => new AdjustProvider(string.Empty));
        }
    }
#endif
}
