using System;
using System.Collections.Generic;

namespace GameFactory.Analytics.Events
{
    /// <summary>
    /// Base class for every GameFactory monetization / gameplay event.
    ///
    /// The serialized shape produced by <see cref="ToDictionary"/> is the canonical contract
    /// consumed by the Reality Dataset (E13.3) and any future backend. Keep field names and
    /// meanings STABLE — downstream pipelines (Adjust, Firebase, CI, AI agent) depend on them.
    ///
    /// Envelope (always present):
    ///   event, game, platform, country, user_id, session_id, timestamp_ms, timestamp
    /// Plus an open <c>props</c> bag for event-specific fields.
    /// </summary>
    public abstract class GameEvent
    {
        public string event_name;
        public string game;
        public string platform;
        public string country;
        public string user_id;
        public string session_id;
        public long timestamp_ms;
        public Dictionary<string, object> props = new Dictionary<string, object>();

        protected GameEvent(string name)
        {
            event_name = name;
            timestamp_ms = (long)(DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalMilliseconds;
        }

        /// <summary>Common envelope + prop bag. Providers / CI read exactly this shape.</summary>
        public virtual Dictionary<string, object> ToDictionary()
        {
            var d = new Dictionary<string, object>
            {
                ["event"] = event_name,
                ["game"] = game,
                ["platform"] = platform,
                ["country"] = country,
                ["user_id"] = user_id,
                ["session_id"] = session_id,
                ["timestamp_ms"] = timestamp_ms,
                ["timestamp"] = new DateTime(1970, 1, 1, DateTimeKind.Utc)
                                    .AddMilliseconds(timestamp_ms).ToString("o"),
            };
            foreach (var kv in props) d[kv.Key] = kv.Value;
            return d;
        }

        /// <summary>Short identity used in logs / dedup. Not part of the payload.</summary>
        public string Id => event_name + "_" + timestamp_ms;
    }
}
