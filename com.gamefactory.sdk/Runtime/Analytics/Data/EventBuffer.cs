using System;
using System.Collections.Generic;
using System.IO;
using GameFactory.Analytics.Events;
using UnityEngine;

namespace GameFactory.Analytics.Data
{
    /// <summary>
    /// In-memory ring buffer + offline cache for GameFactory events.
    ///
    /// LEAN: no backend. Events are held in memory and persisted as JSON lines under
    /// Application.persistentDataPath so they survive crashes / offline sessions, then replay
    /// on next launch via <see cref="Flush"/>. The active <see cref="EventUploader"/> decides
    /// where flushed batches go (default: the enabled Analytics providers).
    /// </summary>
    public class EventBuffer
    {
        private const string CacheFile = "gamefactory_events.jsonl";
        private const int MaxBuffered = 2000;

        private readonly List<GameEvent> _queue = new List<GameEvent>();
        private string _cachePath;
        private bool _loaded;

        public static readonly EventBuffer Instance = new EventBuffer();

        public int Count
        {
            get { lock (_queue) return _queue.Count; }
        }

        public void Initialize()
        {
            if (_loaded) return;
            _loaded = true;
            _cachePath = Path.Combine(Application.persistentDataPath, CacheFile);
            LoadFromDisk();
            // Best-effort flush when the app goes to background or quits.
            Application.focusChanged += _ => Flush();
            Application.quitting += Flush;
        }

        public void Push(GameEvent e)
        {
            lock (_queue)
            {
                _queue.Add(e);
                if (_queue.Count > MaxBuffered) _queue.RemoveAt(0);
            }
            AppendLine(e);
            if (_queue.Count >= MaxBuffered) Flush();
        }

        public List<GameEvent> Drain()
        {
            List<GameEvent> outp;
            lock (_queue)
            {
                outp = new List<GameEvent>(_queue);
                _queue.Clear();
            }
            return outp;
        }

        public void Clear()
        {
            lock (_queue) _queue.Clear();
            SaveToDisk();
        }

        /// <summary>Drain the buffer and hand the batch to the active uploader.</summary>
        public void Flush()
        {
            var batch = Drain();
            if (batch.Count == 0) return;
            var dicts = new List<Dictionary<string, object>>(batch.Count);
            foreach (var e in batch) dicts.Add(e.ToDictionary());
            EventUploader.Active?.Upload(dicts);
            SaveToDisk();
        }

        // ---- offline cache (append-only JSON lines) ----

        private void AppendLine(GameEvent e)
        {
            if (string.IsNullOrEmpty(_cachePath)) return;
            try
            {
                using var sw = new StreamWriter(_cachePath, true);
                sw.WriteLine(EventSerializer.Write(e.ToDictionary()));
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[EventBuffer] append failed: " + ex.Message);
            }
        }

        private void SaveToDisk()
        {
            if (string.IsNullOrEmpty(_cachePath)) return;
            try
            {
                using var sw = new StreamWriter(_cachePath, false);
                lock (_queue)
                {
                    foreach (var e in _queue) sw.WriteLine(EventSerializer.Write(e.ToDictionary()));
                }
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[EventBuffer] save failed: " + ex.Message);
            }
        }

        private void LoadFromDisk()
        {
            if (!File.Exists(_cachePath)) return;
            try
            {
                foreach (var line in File.ReadAllLines(_cachePath))
                {
                    if (string.IsNullOrWhiteSpace(line)) continue;
                    var dict = EventSerializer.Read(line);
                    if (dict == null) continue;
                    _queue.Add(new RawEvent(dict));
                }
                if (_queue.Count > 0)
                    Debug.Log("[EventBuffer] replayed " + _queue.Count + " cached events from disk");
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[EventBuffer] load failed: " + ex.Message);
            }
        }

        /// <summary>Disk-loaded event: carries the already-serialized dict, skips typed reconstruction.</summary>
        private class RawEvent : GameEvent
        {
            private readonly Dictionary<string, object> _d;
            public RawEvent(Dictionary<string, object> d)
                : base(d.TryGetValue("event", out var n) ? (n?.ToString() ?? "unknown") : "unknown")
            {
                _d = d;
                if (d.TryGetValue("game", out var g)) game = g?.ToString();
                if (d.TryGetValue("platform", out var p)) platform = p?.ToString();
                if (d.TryGetValue("country", out var c)) country = c?.ToString();
                if (d.TryGetValue("user_id", out var u)) user_id = u?.ToString();
                if (d.TryGetValue("session_id", out var s)) session_id = s?.ToString();
                if (d.TryGetValue("timestamp_ms", out var t) && t is long tl) timestamp_ms = tl;
            }
            public override Dictionary<string, object> ToDictionary() => new Dictionary<string, object>(_d);
        }
    }
}
