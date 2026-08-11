using System.Collections.Generic;
using GameFactory.Analytics.Data;
using GameFactory.Analytics.Events;
using GameFactory.Core;
using UnityEngine;

namespace GameFactory.Analytics
{
    /// <summary>
    /// Facade matching the E13.1 PRD interface:
    ///   Analytics.Track("level_complete", new() { ["level"] = 10 });   // raw, direct to providers
    ///   Analytics.LogEvent(GameplayEvent.LevelStart(3));               // structured, via buffer
    ///
    /// <see cref="Track"/> routes a raw event straight to every enabled provider (used by
    /// E13.2.6 validation). <see cref="LogEvent"/> is the E13.2.7 path: it stamps the envelope,
    /// pushes the event into <see cref="EventBuffer"/>, and the buffer flushes batches through
    /// the active <see cref="IEventUploader"/>. The default uploader forwards to the same
    /// providers, so there is exactly ONE delivery path — no double-send.
    /// </summary>
    public static class Analytics
    {
        private static readonly List<IAnalyticsProvider> Providers = new List<IAnalyticsProvider>();

        /// <summary>Game slug stamped onto every event envelope. Set by GameFactory.Initialize.</summary>
        public static string GameSlug { get; set; } = "";

        public static void Initialize(AnalyticsConfig cfg)
        {
            Providers.Clear();
            if (cfg?.providers == null) return;
            foreach (var p in cfg.providers)
            {
                var provider = AnalyticsRegistry.Create(p);
                if (provider == null)
                {
                    Debug.LogWarning("[Analytics] no provider registered for '" + p +
                                     "'. Install the SDK and enable its scripting define.");
                    continue;
                }
                Providers.Add(provider);
            }
            Debug.Log("[Analytics] Initialized providers=" + Providers.Count);
            // E15.2.7: route buffered events to the optional backend when configured.
            if (!string.IsNullOrEmpty(cfg.event_endpoint))
            {
                var appId = !string.IsNullOrEmpty(cfg.app_id) ? cfg.app_id : GameSlug;
                EventUploader.Active = new RemoteEventUploader(cfg.event_endpoint, appId);
            }
            InitSession();
        }

        /// <summary>Boots the event layer and emits the self-describing lifecycle events.</summary>
        private static void InitSession()
        {
            EventBuffer.Instance.Initialize();
            if (EventUploader.Active == null) EventUploader.Active = new AnalyticsEventUploader();

            // install fires exactly once per install (persisted across sessions)
            if (PlayerPrefs.GetInt("gf_installed", 0) == 0)
            {
                PlayerPrefs.SetInt("gf_installed", 1);
                LogEvent(GameplayEvent.Install());
            }
            LogEvent(GameplayEvent.SessionStart());
            FlushEvents();
        }

        /// <summary>Raw event — goes straight to providers (no buffering). Kept for E13.2.6 validation.</summary>
        public static void Track(string eventName, Dictionary<string, object> parameters = null)
        {
            parameters ??= new Dictionary<string, object>();
            foreach (var p in Providers) p.Track(eventName, parameters);
        }

        /// <summary>Structured event — the E13.2.7 canonical path through the event buffer.</summary>
        public static void LogEvent(GameEvent e)
        {
            if (string.IsNullOrEmpty(e.game)) e.game = GameSlug;
            if (string.IsNullOrEmpty(e.platform)) e.platform = Platform();
            EventBuffer.Instance.Push(e);
        }

        /// <summary>Force a buffer drain+upload now (e.g. before reading back validated events).</summary>
        public static void FlushEvents() => EventBuffer.Instance.Flush();

        public static int BufferedEventCount() => EventBuffer.Instance.Count;

        private static string Platform()
        {
#if UNITY_ANDROID
            return "android";
#elif UNITY_IOS
            return "ios";
#else
            return "unknown";
#endif
        }
    }
}
