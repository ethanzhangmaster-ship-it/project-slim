using System;
using System.Collections.Generic;

namespace GameFactory.Ads
{
    /// <summary>
    /// EU/US mainstream monetization-channel roster for the GameFactory pipeline.
    ///
    /// Two connection models:
    ///   Standalone — has a native C# adapter in this SDK (conditional assembly compiled only
    ///                when its SDK + scripting define are present). config.ads.provider selects it.
    ///   Mediated   — connected through the AppLovin MAX (or LevelPlay) mediation dashboard +
    ///                the network's MAX adapter package. NO per-network adapter is written here;
    ///                doing so would be redundant (the SDK already bundles each network's SDK).
    ///
    /// This is the single source of truth the installer's readiness report reads from, so
    /// "欧美主流渠道都接了" is verifiable rather than asserted.
    /// </summary>
    public static class AdChannelRegistry
    {
        public enum ChannelMode { Standalone, Mediated }

        public static readonly IReadOnlyDictionary<string, ChannelMode> EuUsChannels =
            new Dictionary<string, ChannelMode>(StringComparer.OrdinalIgnoreCase)
            {
                // --- Standalone (native adapter in this SDK) ---
                ["MAX"]       = ChannelMode.Standalone,   // AppLovin MAX — mediation hub (recommended)
                ["LevelPlay"] = ChannelMode.Standalone,   // ironSource LevelPlay — mediation
                ["AdMob"]     = ChannelMode.Standalone,   // Google AdMob — direct (Google Mobile Ads SDK)
                // --- Mediated through MAX / LevelPlay (enable in dashboard + import adapter pkg) ---
                ["Meta"]      = ChannelMode.Mediated,     // Meta Audience Network
                ["UnityAds"]  = ChannelMode.Mediated,     // Unity Ads
                ["Vungle"]    = ChannelMode.Mediated,     // Vungle (Liftoff)
                ["Mintegral"] = ChannelMode.Mediated,     // Mintegral
                ["Pangle"]    = ChannelMode.Mediated,     // Pangle / TikTok
                ["AmazonAPS"] = ChannelMode.Mediated,     // Amazon Publisher Services
                ["InMobi"]    = ChannelMode.Mediated,     // InMobi
                ["Chartboost"]= ChannelMode.Mediated,     // Chartboost
            };

        /// <summary>Channels that have a native C# adapter shipped in this SDK.</summary>
        public static IReadOnlyList<string> StandaloneChannels
        {
            get
            {
                var list = new List<string>();
                foreach (var kv in EuUsChannels)
                    if (kv.Value == ChannelMode.Standalone) list.Add(kv.Key);
                return list;
            }
        }

        /// <summary>Channels connected via MAX/LevelPlay mediation (no adapter code needed).</summary>
        public static IReadOnlyList<string> MediatedChannels
        {
            get
            {
                var list = new List<string>();
                foreach (var kv in EuUsChannels)
                    if (kv.Value == ChannelMode.Mediated) list.Add(kv.Key);
                return list;
            }
        }

        /// <summary>
        /// AppLovin MAX ships every mediated network as a separate UPM adapter package named
        /// "com.applovin.mediation.adapters.&lt;slug&gt;". This maps the package slug to the
        /// channel key in EuUsChannels so the installer can report which mediated networks are
        /// actually imported into the project (vs merely enabled in the dashboard).
        /// </summary>
        public static readonly IReadOnlyDictionary<string, string> MediatedAdapterSlugs =
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["facebook"]  = "Meta",
                ["unityads"]  = "UnityAds",
                ["vungle"]    = "Vungle",
                ["mintegral"] = "Mintegral",
                ["pangle"]    = "Pangle",
                ["amazon"]    = "AmazonAPS",
                ["inmobi"]    = "InMobi",
                ["chartboost"]= "Chartboost",
            };

        /// <summary>
        /// Resolves a MAX adapter package name (e.g. "com.applovin.mediation.adapters.facebook")
        /// to a known EuUsChannels key, or null if it is not a tracked EU/US channel (e.g. AdMob's
        /// MAX adapter resolves to null because AdMob is a standalone channel here).
        /// </summary>
        public static string ResolveMediatedChannel(string packageName)
        {
            if (string.IsNullOrEmpty(packageName)) return null;
            const string prefix = "com.applovin.mediation.adapters.";
            if (!packageName.StartsWith(prefix, StringComparison.Ordinal)) return null;
            var slug = packageName.Substring(prefix.Length).Split('.')[0];
            return MediatedAdapterSlugs.TryGetValue(slug, out var channel) ? channel : null;
        }

        public static bool IsKnown(string channel) =>
            !string.IsNullOrEmpty(channel) && EuUsChannels.ContainsKey(channel);

        public static bool IsStandalone(string channel) =>
            EuUsChannels.TryGetValue(channel ?? "", out var m) && m == ChannelMode.Standalone;
    }
}
