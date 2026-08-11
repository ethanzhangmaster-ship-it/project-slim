using System;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace GameFactory.Analytics.Data
{
    /// <summary>
    /// Sink for batched, serialized events.
    ///
    /// E15.2.7 ships two implementations:
    ///   - <see cref="AnalyticsEventUploader"/>: default. Forwards structured events to the
    ///     enabled Analytics providers (Adjust / Firebase) through the existing facade.
    ///   - <see cref="RemoteEventUploader"/>: POSTs buffered events to the optional event
    ///     backend (LaunchForge player_monetization ingest receiver). Enabled only when
    ///     <c>AnalyticsConfig.event_endpoint</c> is set; otherwise it stays disabled (Lean
    ///     default: no network calls) and events remain in the offline cache for replay.
    /// </summary>
    public interface IEventUploader
    {
        bool Enabled { get; }
        void Upload(List<Dictionary<string, object>> batch);
    }

    /// <summary>Active sink used by <see cref="EventBuffer.Flush"/>. Swap at runtime if needed.</summary>
    public static class EventUploader
    {
        public static IEventUploader Active { get; set; } = new AnalyticsEventUploader();
    }

    /// <summary>Default sink: routes structured events to Adjust / Firebase via the Analytics facade.</summary>
    public class AnalyticsEventUploader : IEventUploader
    {
        public bool Enabled => true;

        public void Upload(List<Dictionary<string, object>> batch)
        {
            foreach (var d in batch)
            {
                if (!d.TryGetValue("event", out var ev) || ev == null) continue;
                Analytics.Analytics.Track(ev.ToString(), new Dictionary<string, object>(d));
            }
        }
    }

    /// <summary>
    /// E15.2.7 event backend sink. POSTs a JSON array of buffered events to
    /// <c>AnalyticsConfig.event_endpoint</c> via <see cref="UnityWebRequest"/>. Fire-and-forget:
    /// the request runs on Unity's network thread and the (optional) completion callback only
    /// logs — no game-thread blocking. If the POST fails, the events are ALREADY persisted to the
    /// offline JSONL cache by <see cref="EventBuffer"/>, so they replay on the next launch/flush.
    ///
    /// The endpoint is normalized to end with <c>/events</c> (the LaunchForge ingest receiver's
    /// path) and the game's <c>app_id</c> is sent as the <c>X-Game-Id</c> header so the receiver
    /// can route events into <c>data/player_events/&lt;app_id&gt;.jsonl</c> without baking the id
    /// into every envelope.
    /// </summary>
    public class RemoteEventUploader : IEventUploader
    {
        private readonly string _endpoint;
        private readonly string _appId;

        public RemoteEventUploader(string endpoint, string appId = "")
        {
            _endpoint = NormalizeEndpoint(endpoint);
            _appId = appId ?? "";
        }

        public bool Enabled => !string.IsNullOrEmpty(_endpoint);

        /// <summary>Ensures the URL targets the ingest receiver's POST /events route.</summary>
        private static string NormalizeEndpoint(string endpoint)
        {
            if (string.IsNullOrEmpty(endpoint)) return "";
            endpoint = endpoint.Trim();
            if (endpoint.EndsWith("/events", StringComparison.OrdinalIgnoreCase))
                return endpoint;
            if (endpoint.EndsWith("/")) return endpoint + "events";
            return endpoint + "/events";
        }

        public void Upload(List<Dictionary<string, object>> batch)
        {
            if (!Enabled || batch == null || batch.Count == 0) return;
            try
            {
                var json = EventSerializer.WriteBatch(batch);
                var req = new UnityWebRequest(_endpoint, "POST");
                var bytes = Encoding.UTF8.GetBytes(json);
                req.uploadHandler = new UploadHandlerRaw(bytes);
                req.downloadHandler = new DownloadHandlerBuffer();
                req.SetRequestHeader("Content-Type", "application/json");
                if (!string.IsNullOrEmpty(_appId))
                    req.SetRequestHeader("X-Game-Id", _appId);
                req.SendWebRequest().completed += _ => { /* fire-and-forget; cache replay covers failures */ };
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[RemoteEventUploader] upload skipped: " + ex.Message);
            }
        }
    }
}
