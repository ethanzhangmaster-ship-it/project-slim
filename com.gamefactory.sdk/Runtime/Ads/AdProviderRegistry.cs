using System;
using System.Collections.Generic;

namespace GameFactory.Ads
{
    /// <summary>
    /// Resolves ad providers by config key ("MAX", "LevelPlay", ...).
    /// Each provider assembly registers a factory via Register() (guarded by its SDK define),
    /// so a provider only exists when its SDK + scripting define are present.
    /// </summary>
    public static class AdProviderRegistry
    {
        private static readonly Dictionary<string, Func<IAdProvider>> Factories =
            new Dictionary<string, Func<IAdProvider>>(StringComparer.OrdinalIgnoreCase);

        public static void Register(string key, Func<IAdProvider> factory)
        {
            if (string.IsNullOrEmpty(key) || factory == null) return;
            Factories[key] = factory;
            UnityEngine.Debug.Log("[AdProviderRegistry] registered: " + key);
        }

        public static IAdProvider Create(string key) =>
            Factories.TryGetValue(key ?? "", out var f) ? f() : null;

        public static bool Has(string key) => !string.IsNullOrEmpty(key) && Factories.ContainsKey(key);
    }
}
