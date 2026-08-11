using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using GameFactory.Ads;

namespace GameFactory.Editor
{
    /// <summary>
    /// One-window readiness board for the whole GameFactory SDK. Ads channels + IAP + analytics +
    /// RemoteConfig, each with auto-detected status and any "REPLACE_WITH_*" placeholders still left
    /// in the config. Open via: GameFactory > Readiness.
    ///
    /// The only thing it can't do for you is the actual MAX-dashboard login; for that it shows a
    /// checkbox you tick once you've enabled the network (persisted in EditorPrefs).
    /// </summary>
    public class GameFactoryReadiness : EditorWindow
    {
        private Dictionary<string, string> _detected;
        private HashSet<string> _mediatedImported;
        private CfgRoot _cfg;
        private Vector2 _scroll;
        private int _done, _total;

        [MenuItem("GameFactory/Readiness")]
        public static void Open()
        {
            var w = GetWindow<GameFactoryReadiness>("GameFactory Readiness");
            w.minSize = new Vector2(560, 520);
            w.Show();
        }

        private void OnEnable() => Refresh();

        private void Refresh()
        {
            _detected = GameFactoryInstaller.DetectPackages();
            _mediatedImported = GameFactoryInstaller.DetectMediatedAdapters();
            _cfg = ReadConfig();
            Repaint();
        }

        private static bool IsDashboardEnabled(string channel) =>
            EditorPrefs.GetBool("GameFactory.ChannelEnabled." + channel, false);

        private static void SetDashboardEnabled(string channel, bool v) =>
            EditorPrefs.SetBool("GameFactory.ChannelEnabled." + channel, v);

        private static bool HasPlaceholder(string s) =>
            !string.IsNullOrEmpty(s) && s.Contains("REPLACE_WITH");

        // ---------- config read (lightweight, schema-known) ----------
        [System.Serializable] private class CfgProduct { public string id; public string type; }
        [System.Serializable] private class CfgIap { public bool enabled; public CfgProduct[] products; }
        [System.Serializable] private class CfgEntry { public string key; public string value; }
        [System.Serializable] private class CfgRc { public CfgEntry[] entries; }
        [System.Serializable] private class CfgAnalytics { public string[] providers; public string firebase_key; public string adjust_token; }
        [System.Serializable] private class CfgAds { public string app_key; }
        [System.Serializable] private class CfgRoot
        {
            public CfgAds ads;
            public CfgIap iap;
            public CfgRc remote_config;
            public CfgAnalytics analytics;
        }

        private static CfgRoot ReadConfig()
        {
            var path = FindConfigFile();
            if (path == null || !File.Exists(path)) return null;
            try { return JsonUtility.FromJson<CfgRoot>(File.ReadAllText(path)); }
            catch (System.Exception) { return null; }
        }

        private static string FindConfigFile()
        {
            var copied = Path.Combine(Application.dataPath, "Resources", "GameFactory", "gamefactory_config.json");
            if (File.Exists(copied)) return copied;
            var roots = new[]
            {
                Path.Combine(Application.dataPath, "..", "Library", "PackageCache"),
                Path.Combine(Application.dataPath, "..", "Packages"),
            };
            foreach (var root in roots)
            {
                if (!Directory.Exists(root)) continue;
                foreach (var dir in Directory.GetDirectories(root))
                    if (Path.GetFileName(dir).StartsWith("com.gamefactory.sdk", System.StringComparison.Ordinal))
                    {
                        var p = Path.Combine(dir, "Resources", "gamefactory_config.json");
                        if (File.Exists(p)) return p;
                    }
            }
            return null;
        }

        // ---------- rendering ----------
        private void Row(string label, bool ready, string detail)
        {
            _total++;
            if (ready) _done++;
            using (new EditorGUILayout.HorizontalScope(EditorStyles.helpBox))
                EditorGUILayout.LabelField((ready ? "✓ " : "• ") + label + "  " + detail,
                    ready ? EditorStyles.boldLabel : EditorStyles.label);
        }

        private void OnGUI()
        {
            _done = 0; _total = 0;
            EditorGUILayout.LabelField("GameFactory — SDK Readiness", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(
                "① Auto Setup Everything installs + configures all code. ② Open MAX Dashboard, then tick each " +
                "mediated network once enabled there. Anything marked • still needs your action.",
                MessageType.Info);

            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("① Auto Setup Everything", GUILayout.Height(28)))
                    GameFactoryInstaller.AutoSetupEverything();
                if (GUILayout.Button("② Open MAX Dashboard", GUILayout.Height(28)))
                    GameFactoryInstaller.OpenMaxDashboard();
                if (GUILayout.Button("↻ Refresh", GUILayout.Height(28)))
                    Refresh();
            }

            _scroll = EditorGUILayout.BeginScrollView(_scroll);

            // --- Ads channels ---
            SectionLabel("Ad Channels");
            foreach (var kv in AdChannelRegistry.EuUsChannels)
            {
                var channel = kv.Key;
                var mode = kv.Value;
                if (mode == AdChannelRegistry.ChannelMode.Standalone)
                {
                    bool ready = GameFactoryInstaller.IsStandaloneReady(channel, _detected);
                    Row(channel + " [Standalone]", ready, ready ? "code-ready" : "SDK missing — run Auto Setup");
                }
                else
                {
                    bool imported = _mediatedImported.Contains(channel);
                    bool done = imported && IsDashboardEnabled(channel);
                    if (!imported)
                        Row(channel + " [Mediated]", false, "import adapter pkg + enable in dashboard");
                    else if (!done)
                        Row(channel + " [Mediated]", false, "imported — enable in dashboard");
                    else
                        Row(channel + " [Mediated]", true, "imported + enabled");
                }
            }
            // MAX app key placeholder (the one non-dashboard thing you must paste)
            bool appKeyOk = _cfg?.ads != null && !HasPlaceholder(_cfg.ads.app_key);
            Row("MAX App Key (config)", appKeyOk, appKeyOk ? "set" : "still REPLACE_WITH_MAX_APP_KEY — paste in config");

            // --- IAP ---
            SectionLabel("In-App Purchases (Unity IAP)");
            bool iapPkg = _detected.ContainsKey("Unity IAP");
            bool iapCfg = _cfg?.iap != null && _cfg.iap.enabled;
            int prodCount = _cfg?.iap?.products != null ? _cfg.iap.products.Length : 0;
            if (!iapPkg)
                Row("Unity IAP package", false, "missing — run Auto Setup");
            else if (!iapCfg)
                Row("Unity IAP enabled", false, "package OK — set iap.enabled=true in config");
            else
                Row("Unity IAP", true, "ready (" + prodCount + " product(s) in config)");

            // --- Analytics ---
            SectionLabel("Analytics");
            bool adjustPkg = _detected.ContainsKey("Adjust");
            bool fbPkg = _detected.ContainsKey("Firebase Analytics");
            if (!adjustPkg)
                Row("Adjust", false, "package missing — run Auto Setup");
            else
            {
                bool tokOk = _cfg?.analytics != null && !HasPlaceholder(_cfg.analytics.adjust_token);
                Row("Adjust", tokOk, tokOk ? "ready" : "package OK — adjust_token still REPLACE_WITH_*");
            }
            if (!fbPkg)
                Row("Firebase Analytics", false, "package missing — run Auto Setup");
            else
            {
                bool keyOk = _cfg?.analytics != null && !HasPlaceholder(_cfg.analytics.firebase_key);
                Row("Firebase Analytics", keyOk, keyOk ? "ready" : "package OK — firebase_key still REPLACE_WITH_*");
            }

            // --- RemoteConfig ---
            SectionLabel("Remote Config");
            int rcCount = _cfg?.remote_config?.entries != null ? _cfg.remote_config.entries.Length : 0;
            Row("Remote Config (built-in)", true, "no package needed — " + rcCount + " entr(y/ies) in config");

            EditorGUILayout.EndScrollView();

            EditorGUILayout.LabelField($"Progress: {_done}/{_total} ready", EditorStyles.boldLabel);
            using (new EditorGUILayout.HorizontalScope())
            {
                EditorGUILayout.LabelField(_done == _total ? "All set — SDK fully wired." : "Finish the • items above.",
                    _done == _total ? EditorStyles.boldLabel : EditorStyles.label);
                if (GUILayout.Button("Reset channel ticks", GUILayout.Width(130)))
                {
                    foreach (var c in AdChannelRegistry.MediatedChannels) SetDashboardEnabled(c, false);
                    Refresh();
                }
            }
        }

        private void SectionLabel(string text)
        {
            var prev = EditorStyles.label.fontStyle;
            EditorStyles.label.fontStyle = FontStyle.Bold;
            EditorGUILayout.LabelField(text);
            EditorStyles.label.fontStyle = prev;
            EditorGUILayout.Separator();
        }
    }
}
