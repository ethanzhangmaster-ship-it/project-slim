using System;
using System.Collections.Generic;
using System.IO;
using GameFactory.Ads;
using GameFactory.Core;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.PackageManager;
using UnityEditor.PackageManager.Requests;
using UnityEngine;

namespace GameFactory.Editor
{
    /// <summary>
    /// Project setup entry points (GameFactory > ... menu):
    ///   • Setup Project        — configure the already-imported SDKs (defines + asmdef refs + report).
    ///   • Auto Setup Everything — ONE CLICK: auto-installs every required package via the
    ///     Package Manager (MAX, AdMob, Unity IAP, Adjust, Firebase, and ALL 8 MAX mediation
    ///     adapter packages), then configures + prints the readiness report. No manual
    ///     manifest.json editing and no separate setup run — the only remaining human step is
    ///     enabling each network in the AppLovin MAX dashboard (and that requires a login).
    /// </summary>
    public static class GameFactoryInstaller
    {
        private const string PackageName = "com.gamefactory.sdk";

        private static readonly Dictionary<string, (string folderPrefix, string define)> Sdks =
            new Dictionary<string, (string, string)>
            {
                ["AppLovin MAX"]      = ("com.applovin.mediation.max", "APPLOVIN_MAX"),
                ["ironSource LevelPlay"] = ("com.unity3d.mediation", "MODULE_LEVELPLAY"),
                ["Google AdMob"]      = ("com.google.ads.mobileads", "GOOGLE_MOBILE_ADS"),
                ["Unity IAP"]         = ("com.unity.purchasing", "UNITY_PURCHASING"),
                ["Adjust"]            = ("com.adjust.unity", "ADJUST_SDK"),
                ["Firebase Analytics"] = ("com.google.firebase.analytics", "FIREBASE_SDK"),
            };

        /// <summary>Every package GameFactory needs. Auto Setup Everything installs any that are
        /// missing; when all are present it just runs the configuration step.</summary>
        private static readonly string[] AutoSetupPackages = new[]
        {
            "com.applovin.mediation.max",                 // AppLovin MAX — mediation hub
            "com.google.ads.mobileads",                   // Google AdMob (standalone adapter)
            "com.unity.purchasing",                       // Unity IAP
            "com.adjust.unity",                           // Adjust analytics
            "com.google.firebase.analytics",              // Firebase analytics
            // All 8 MAX mediation adapter packages (=> mediated channels become code-ready ✓)
            "com.applovin.mediation.adapters.facebook",   // Meta Audience Network
            "com.applovin.mediation.adapters.unityads",   // Unity Ads
            "com.applovin.mediation.adapters.vungle",     // Vungle (Liftoff)
            "com.applovin.mediation.adapters.mintegral",  // Mintegral
            "com.applovin.mediation.adapters.pangle",     // Pangle (TikTok)
            "com.applovin.mediation.adapters.amazon",     // Amazon APS
            "com.applovin.mediation.adapters.inmobi",     // InMobi
            "com.applovin.mediation.adapters.chartboost", // Chartboost
        };

        [MenuItem("GameFactory/Setup Project")]
        public static void SetupProject()
        {
            Debug.Log("=== GameFactory Setup Project ===");
            CopyConfig();
            ConfigureAndReport();
            Debug.Log("=== GameFactory setup complete ===");
        }

        /// <summary>ONE-CLICK: install any missing required packages, then configure + report.
        /// The only step this cannot do for you is logging into the AppLovin MAX dashboard to
        /// enable each network (that needs your account credentials).</summary>
        [MenuItem("GameFactory/Auto Setup Everything")]
        public static void AutoSetupEverything()
        {
            Debug.Log("=== GameFactory Auto Setup Everything ===");
            CopyConfig();
            var missing = new List<string>();
            foreach (var pkg in AutoSetupPackages)
                if (!IsPackageInstalled(pkg)) missing.Add(pkg);

            if (missing.Count == 0)
            {
                Debug.Log("✓ All required packages already installed — configuring only.");
                ConfigureAndReport();
                return;
            }
            Debug.Log("→ Installing " + missing.Count + " missing package(s) — this may take a few minutes…");
            _pkgQueue = new Queue<string>(missing);
            AdvancePackageQueue();
        }

        /// <summary>One click opens the AppLovin MAX dashboard so you can enable the mediated
        /// networks (the only step Auto Setup Everything can't do for you — it needs your login).</summary>
        [MenuItem("GameFactory/Open MAX Dashboard")]
        public static void OpenMaxDashboard()
        {
            Application.OpenURL("https://dashboard.applovin.com/");
            Debug.Log("→ Opened AppLovin MAX dashboard. Enable each network under Mediation > Manage > Networks.");
        }

        private static void ConfigureAndReport()
        {
            var detected = DetectPackages();
            EnableDefines(detected);
            InjectLevelPlayReference(detected.ContainsKey("ironSource LevelPlay"));
            InjectAdMobReference(detected.ContainsKey("Google AdMob"));
            InjectIapReference(detected.ContainsKey("Unity IAP"));
            var mediatedReady = DetectMediatedAdapters();
            AssetDatabase.Refresh();
            PrintChannelReport(detected, mediatedReady);
        }

        private static bool IsPackageInstalled(string prefix)
        {
            var roots = new[]
            {
                Path.Combine(Application.dataPath, "..", "Library", "PackageCache"),
                Path.Combine(Application.dataPath, "..", "Packages"),
            };
            foreach (var root in roots)
            {
                if (!Directory.Exists(root)) continue;
                foreach (var dir in Directory.GetDirectories(root))
                    if (Path.GetFileName(dir).StartsWith(prefix, StringComparison.Ordinal)) return true;
            }
            return false;
        }

        // --- Async package-install queue (PackageManager.Client.Add is non-blocking) ---
        private static Queue<string> _pkgQueue;
        private static AddRequest _currentAdd;

        private static void AdvancePackageQueue()
        {
            if (_pkgQueue == null || _pkgQueue.Count == 0)
            {
                _pkgQueue = null;
                _currentAdd = null;
                Debug.Log("✓ Package install queue drained. Configuring + printing report…");
                ConfigureAndReport();
                return;
            }
            var pkg = _pkgQueue.Dequeue();
            Debug.Log("→ Adding " + pkg + " …");
            _currentAdd = Client.Add(pkg);
            EditorApplication.update += PollPackageAdd;
        }

        private static void PollPackageAdd()
        {
            if (_currentAdd == null) { EditorApplication.update -= PollPackageAdd; return; }
            if (!_currentAdd.IsCompleted) return;
            EditorApplication.update -= PollPackageAdd;
            if (_currentAdd.Status == StatusCode.Success)
                Debug.Log("✓ Installed " + _currentAdd.Result?.packageId);
            else
                Debug.LogWarning("✗ Failed to install " + ( _currentAdd.Result?.packageId ?? "?" ) +
                                 ": " + _currentAdd.Error?.message + " (continue — configure remaining)");
            AdvancePackageQueue();
        }

        private static void CopyConfig()
        {
            var root = FindPackageRoot();
            if (root == null) { Debug.LogWarning("[GameFactory] package root not found; skipping config copy."); return; }
            var src = Path.Combine(root, "Resources", "gamefactory_config.json");
            var destDir = Path.Combine(Application.dataPath, "Resources", "GameFactory");
            var dest = Path.Combine(destDir, "gamefactory_config.json");
            try
            {
                if (!File.Exists(src)) { Debug.LogWarning("[GameFactory] default config missing at " + src); return; }
                Directory.CreateDirectory(destDir);
                if (File.Exists(dest)) { Debug.Log("[GameFactory] config already exists at " + dest + " (kept)."); return; }
                File.Copy(src, dest);
                Debug.Log("✓ Copied gamefactory_config.json -> " + dest);
            }
            catch (Exception e) { Debug.LogError("[GameFactory] config copy failed: " + e.Message); }
        }

        public static Dictionary<string, string> DetectPackages()
        {
            var result = new Dictionary<string, string>();
            var roots = new[]
            {
                Path.Combine(Application.dataPath, "..", "Library", "PackageCache"),
                Path.Combine(Application.dataPath, "..", "Packages"),
            };
            foreach (var kv in Sdks)
            {
                bool found = false;
                foreach (var root in roots)
                {
                    if (!Directory.Exists(root)) continue;
                    foreach (var dir in Directory.GetDirectories(root))
                    {
                        if (Path.GetFileName(dir).StartsWith(kv.Value.folderPrefix, StringComparison.Ordinal))
                        { found = true; break; }
                    }
                    if (found) break;
                }
                if (found)
                {
                    result[kv.Key] = kv.Value.define;
                    Debug.Log("✓ " + kv.Key + " detected");
                }
                else
                {
                    Debug.Log("✗ " + kv.Key + " missing (define " + kv.Value.define + " not enabled)");
                }
            }
            return result;
        }

        private static void EnableDefines(Dictionary<string, string> detected)
        {
            var groups = new[] { NamedBuildTarget.Android, NamedBuildTarget.iOS, NamedBuildTarget.Standalone };
            foreach (var group in groups)
            {
                var current = PlayerSettings.GetScriptingDefineSymbolsForGroup(group);
                var parts = new HashSet<string>(current.Split(';', ','), StringComparer.Ordinal);
                bool changed = false;
                foreach (var define in detected.Values)
                {
                    if (parts.Add(define)) changed = true;
                }
                if (changed)
                {
                    PlayerSettings.SetScriptingDefineSymbolsForGroup(group, string.Join(";", parts));
                    Debug.Log("[GameFactory] enabled defines for " + group + ": " + string.Join(",", detected.Values));
                }
            }
        }

        private static void InjectLevelPlayReference(bool levelPlayDetected)
        {
            if (!levelPlayDetected) return;
            var root = FindPackageRoot();
            if (root == null) return;
            var asmdefPath = Path.Combine(root, "Runtime", "Ads", "LevelPlay", "GameFactory.Ads.LevelPlay.asmdef");
            if (!File.Exists(asmdefPath)) return;

            try
            {
                var levelPlayAsmName = FindLevelPlayAsmdefName();
                if (string.IsNullOrEmpty(levelPlayAsmName)) return;

                var text = File.ReadAllText(asmdefPath);
                var doc = JsonUtility.FromJson<AsmdefDoc>(text); // fallback parse
                if (doc == null || doc.references == null) return;
                if (!Array.Exists(doc.references, r => r == levelPlayAsmName))
                {
                    var list = new List<string>(doc.references) { levelPlayAsmName };
                    doc.references = list.ToArray();
                    File.WriteAllText(asmdefPath, JsonUtility.ToJson(doc, true));
                    AssetDatabase.ImportAsset(asmdefPath);
                    Debug.Log("✓ Injected LevelPlay SDK reference '" + levelPlayAsmName + "' into " + Path.GetFileName(asmdefPath));
                }
                else
                {
                    Debug.Log("[GameFactory] LevelPlay reference already present: " + levelPlayAsmName);
                }
            }
            catch (Exception e) { Debug.LogWarning("[GameFactory] LevelPlay asmdef injection skipped: " + e.Message); }
        }

        private static string FindLevelPlayAsmdefName()
        {
            var roots = new[]
            {
                Path.Combine(Application.dataPath, "..", "Library", "PackageCache"),
                Path.Combine(Application.dataPath, "..", "Packages"),
            };
            foreach (var root in roots)
            {
                if (!Directory.Exists(root)) continue;
                foreach (var dir in Directory.GetDirectories(root))
                {
                    if (!Path.GetFileName(dir).StartsWith("com.unity3d.mediation", StringComparison.Ordinal)) continue;
                    foreach (var asm in Directory.GetFiles(dir, "*.asmdef", SearchOption.AllDirectories))
                    {
                        try
                        {
                            var d = JsonUtility.FromJson<AsmdefDoc>(File.ReadAllText(asm));
                            if (!string.IsNullOrEmpty(d.name)) return d.name;
                        }
                        catch { /* ignore */ }
                    }
                }
            }
            return null;
        }

        private static void InjectAdMobReference(bool adMobDetected)
        {
            if (!adMobDetected) return;
            var root = FindPackageRoot();
            if (root == null) return;
            var asmdefPath = Path.Combine(root, "Runtime", "Ads", "AdMob", "GameFactory.Ads.AdMob.asmdef");
            InjectAsmReference(asmdefPath, "com.google.ads.mobileads", "Google AdMob");
        }

        private static void InjectIapReference(bool iapDetected)
        {
            if (!iapDetected) return;
            var root = FindPackageRoot();
            if (root == null) return;
            var asmdefPath = Path.Combine(root, "Runtime", "IAP", "GameFactory.IAP.asmdef");
            InjectAsmReference(asmdefPath, "com.unity.purchasing", "Unity IAP");
        }

        /// <summary>Generic reference injection: find the SDK asmdef name under PackageCache/Packages
        /// matching folderPrefix and add it to target asmdef.references.</summary>
        private static void InjectAsmReference(string asmdefPath, string folderPrefix, string label)
        {
            if (!File.Exists(asmdefPath)) return;
            try
            {
                var sdkAsmName = FindSdkAsmdefName(folderPrefix);
                if (string.IsNullOrEmpty(sdkAsmName)) return;

                var text = File.ReadAllText(asmdefPath);
                var doc = JsonUtility.FromJson<AsmdefDoc>(text);
                if (doc == null || doc.references == null) return;
                if (!Array.Exists(doc.references, r => r == sdkAsmName))
                {
                    var list = new List<string>(doc.references) { sdkAsmName };
                    doc.references = list.ToArray();
                    File.WriteAllText(asmdefPath, JsonUtility.ToJson(doc, true));
                    AssetDatabase.ImportAsset(asmdefPath);
                    Debug.Log("✓ Injected " + label + " SDK reference '" + sdkAsmName + "' into " + Path.GetFileName(asmdefPath));
                }
                else
                {
                    Debug.Log("[GameFactory] " + label + " reference already present: " + sdkAsmName);
                }
            }
            catch (Exception e) { Debug.LogWarning("[GameFactory] " + label + " asmdef injection skipped: " + e.Message); }
        }

        private static string FindSdkAsmdefName(string folderPrefix)
        {
            var roots = new[]
            {
                Path.Combine(Application.dataPath, "..", "Library", "PackageCache"),
                Path.Combine(Application.dataPath, "..", "Packages"),
            };
            foreach (var root in roots)
            {
                if (!Directory.Exists(root)) continue;
                foreach (var dir in Directory.GetDirectories(root))
                {
                    if (!Path.GetFileName(dir).StartsWith(folderPrefix, StringComparison.Ordinal)) continue;
                    foreach (var asm in Directory.GetFiles(dir, "*.asmdef", SearchOption.AllDirectories))
                    {
                        try
                        {
                            var d = JsonUtility.FromJson<AsmdefDoc>(File.ReadAllText(asm));
                            if (!string.IsNullOrEmpty(d.name)) return d.name;
                        }
                        catch { /* ignore */ }
                    }
                }
            }
            return null;
        }

        /// <summary>Prints the EU/US channel readiness report: which channels are code-ready
        /// (standalone adapter compiled, or mediated adapter package imported) vs which must be
        /// enabled in the MAX/LevelPlay dashboard + have their adapter package imported.</summary>
        private static void PrintChannelReport(Dictionary<string, string> detected, HashSet<string> mediatedReady)
        {
            Debug.Log("=== GameFactory EU/US Channel Readiness ===");
            foreach (var kv in AdChannelRegistry.EuUsChannels)
            {
                var channel = kv.Key;
                var mode = kv.Value;
                if (mode == AdChannelRegistry.ChannelMode.Standalone)
                {
                    bool ready = IsStandaloneReady(channel, detected);
                    Debug.Log((ready ? "✓ " : "✗ ") + channel + " (standalone adapter" +
                              (ready ? ", SDK detected" : ", SDK NOT installed — run Setup again after importing") + ")");
                }
                else
                {
                    bool ready = mediatedReady.Contains(channel);
                    Debug.Log((ready ? "✓ " : "• ") + channel + " (mediated via MAX/LevelPlay — " +
                              (ready ? "adapter pkg imported, enable in dashboard"
                                     : "enable in dashboard + import adapter pkg")) + ")");
                }
            }
            Debug.Log("=== End channel report ===");
        }

        /// <summary>Scans the project for imported AppLovin MAX mediation adapter packages and
        /// returns the set of mediated EuUsChannels that are actually code-ready (adapter imported).</summary>
        public static HashSet<string> DetectMediatedAdapters()
        {
            var ready = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var roots = new[]
            {
                Path.Combine(Application.dataPath, "..", "Library", "PackageCache"),
                Path.Combine(Application.dataPath, "..", "Packages"),
            };
            const string prefix = "com.applovin.mediation.adapters.";
            foreach (var root in roots)
            {
                if (!Directory.Exists(root)) continue;
                foreach (var dir in Directory.GetDirectories(root))
                {
                    var name = Path.GetFileName(dir);
                    if (!name.StartsWith(prefix, StringComparison.Ordinal)) continue;
                    var channel = AdChannelRegistry.ResolveMediatedChannel(name);
                    if (!string.IsNullOrEmpty(channel)) ready.Add(channel);
                }
            }
            return ready;
        }

        public static bool IsStandaloneReady(string channel, Dictionary<string, string> detected)
        {
            switch (channel)
            {
                case "MAX":       return detected.ContainsKey("AppLovin MAX");
                case "LevelPlay": return detected.ContainsKey("ironSource LevelPlay");
                case "AdMob":     return detected.ContainsKey("Google AdMob");
                default:          return false;
            }
        }

        private static string FindPackageRoot()
        {
            foreach (var guid in AssetDatabase.FindAssets("GameFactoryInstaller"))
            {
                var p = AssetDatabase.GUIDToAssetPath(guid);
                var idx = p.IndexOf(PackageName, StringComparison.Ordinal);
                if (idx >= 0) return p.Substring(0, idx + PackageName.Length);
            }
            return null;
        }

        [Serializable] private class AsmdefDoc { public string name; public string[] references; }

        /// <summary>
        /// E15.2.7 drop-in affordance: paste the LaunchForge event ingest endpoint + app id and
        /// write them straight into the copied gamefactory_config.json. One click after pasting —
        /// no manual JSON editing. Leaving the endpoint blank keeps the SDK in offline-only mode
        /// (events stay in the local JSONL cache for replay).
        /// </summary>
        public class EventBackendWindow : EditorWindow
        {
            private string _endpoint = "";
            private string _appId = "";

            [MenuItem("GameFactory/Configure Event Backend")]
            public static void Open()
            {
                var w = GetWindow<EventBackendWindow>("GameFactory Event Backend");
                w.minSize = new Vector2(440, 170);
                var path = Path.Combine(Application.dataPath, "Resources", "GameFactory", "gamefactory_config.json");
                if (File.Exists(path))
                {
                    var cfg = JsonUtility.FromJson<GameFactoryConfig>(File.ReadAllText(path));
                    if (cfg != null && cfg.analytics != null)
                    {
                        w._endpoint = cfg.analytics.event_endpoint ?? "";
                        w._appId = cfg.analytics.app_id ?? "";
                    }
                }
            }

            private void OnGUI()
            {
                EditorGUILayout.LabelField("LaunchForge Event Backend (E15.2.7)", EditorStyles.boldLabel);
                EditorGUILayout.HelpBox(
                    "Paste the event ingest endpoint (LaunchForge player_monetization receiver, e.g. " +
                    "http://10.0.0.5:8765). Leave blank to keep events offline-only.", MessageType.Info);
                _endpoint = EditorGUILayout.TextField("Endpoint", _endpoint);
                _appId = EditorGUILayout.TextField("App ID", _appId);
                if (GUILayout.Button("Apply", GUILayout.Height(30)))
                {
                    Apply();
                    Close();
                }
            }

            private void Apply()
            {
                var path = Path.Combine(Application.dataPath, "Resources", "GameFactory", "gamefactory_config.json");
                if (!File.Exists(path))
                {
                    Debug.LogError("[GameFactory] config not found at " + path + " — run 'GameFactory > Setup Project' first.");
                    return;
                }
                var cfg = JsonUtility.FromJson<GameFactoryConfig>(File.ReadAllText(path));
                if (cfg == null || cfg.analytics == null)
                {
                    Debug.LogError("[GameFactory] failed to parse config at " + path);
                    return;
                }
                cfg.analytics.event_endpoint = _endpoint.Trim();
                cfg.analytics.app_id = _appId.Trim();
                File.WriteAllText(path, JsonUtility.ToJson(cfg, true));
                AssetDatabase.ImportAsset("Assets/Resources/GameFactory/gamefactory_config.json");
                Debug.Log("✓ Event backend configured: endpoint='" + cfg.analytics.event_endpoint +
                          "' app_id='" + cfg.analytics.app_id + "'");
            }
        }
    }
}
