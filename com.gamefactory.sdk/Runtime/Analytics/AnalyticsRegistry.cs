using System;
using System.Collections.Generic;

namespace GameFactory.Analytics
{
    /// <summary>
    /// Resolves analytics providers by config key ("Firebase", "Adjust", ...).
    /// Each provider assembly registers a factory via Register() (guarded by its SDK define).
    /// </summary>
    public static class AnalyticsRegistry
    {
        private static readonly Dictionary<string, Func<IAnalyticsProvider>> Factories =
            new Dictionary<string, Func<IAnalyticsProvider>>(StringComparer.OrdinalIgnoreCase);

        public static void Register(string key, Func<IAnalyticsProvider> factory)
        {
            if (string.IsNullOrEmpty(key) || factory == null) return;
            Factories[key] = factory;
            UnityEngine.Debug.Log("[AnalyticsRegistry] registered: " + key);
        }

        public static IAnalyticsProvider Create(string key) =>
            Factories.TryGetValue(key ?? "", out var f) ? f() : null;

        public static bool Has(string key) => !string.IsNullOrEmpty(key) && Factories.ContainsKey(key);
    }
}
