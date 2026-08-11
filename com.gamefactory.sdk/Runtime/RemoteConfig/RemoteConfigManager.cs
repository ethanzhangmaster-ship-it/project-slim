using System.Collections.Generic;
using GameFactory.Core;
using UnityEngine;

namespace GameFactory.RemoteConfig
{
    /// <summary>
    /// Production RemoteConfig facade (E13.2 Priority 4).
    /// Consumes a dot-path entry bag: { "ads.reward_frequency": "3", "gameplay.level_difficulty": "1.1" }.
    /// Nested remote_config in product.yaml is flattened to this by config_generator.
    /// Designed for future AI control: call ReloadFromFile() to swap in a server-pushed
    /// remote_config.json without rebuilding (no Firebase Remote Config required).
    /// </summary>
    public static class RemoteConfigManager
    {
        private static readonly Dictionary<string, string> Values = new Dictionary<string, string>();

        public static void Initialize(RemoteConfigData data)
        {
            Values.Clear();
            if (data?.entries != null)
                foreach (var e in data.entries)
                    if (!string.IsNullOrEmpty(e.key))
                        Values[e.key] = e.value;
            // TODO: ReloadFromFile(Application.persistentDataPath + "/remote_config.json");
        }

        /// <summary>Swap in a pre-flattened dot-path dictionary (e.g. from AI/remote push).</summary>
        public static void ApplyValues(Dictionary<string, string> values)
        {
            foreach (var kv in values) Values[kv.Key] = kv.Value;
        }

#if UNITY_ANDROID || UNITY_IOS
        /// <summary>Load a flattened remote_config.json from disk (AI-controlled overrides).</summary>
        public static void ReloadFromFile(string path)
        {
            if (!System.IO.File.Exists(path)) return;
            try
            {
                var wrapper = JsonUtility.FromJson<RemoteConfigWrapper>(System.IO.File.ReadAllText(path));
                if (wrapper?.entries != null)
                    foreach (var e in wrapper.entries) Values[e.key] = e.value;
            }
            catch (System.Exception e) { Debug.LogWarning("[RemoteConfig] reload failed: " + e.Message); }
        }

        [System.Serializable] private class RemoteConfigWrapper
        {
            public List<RemoteEntry> entries;
        }
#endif

        public static int GetInt(string key) => int.TryParse(GetString(key), out var v) ? v : 0;
        public static float GetFloat(string key) => float.TryParse(GetString(key), out var v) ? v : 0f;
        public static string GetString(string key) => Values.TryGetValue(key, out var v) ? v : string.Empty;
        public static bool HasKey(string key) => Values.ContainsKey(key);
    }
}
