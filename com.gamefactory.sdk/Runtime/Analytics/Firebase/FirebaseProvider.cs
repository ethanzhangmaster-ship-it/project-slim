using System.Collections.Generic;
using GameFactory.Core;
using UnityEngine;

namespace GameFactory.Analytics
{
    /// <summary>
    /// Firebase Analytics adapter. This assembly (GameFactory.Analytics.Firebase) compiles ONLY
    /// when the FIREBASE_SDK scripting define is set and the Firebase Analytics package is installed.
    /// </summary>
    public class FirebaseProvider : IAnalyticsProvider
    {
        private readonly string _apiKey;
        public FirebaseProvider(string apiKey) => _apiKey = apiKey;

        public void Track(string eventName, Dictionary<string, object> parameters)
        {
            var pars = new List<Firebase.Analytics.Parameter>();
            foreach (var kv in parameters)
                pars.Add(new Firebase.Analytics.Parameter(kv.Key, kv.Value?.ToString() ?? ""));
            Firebase.Analytics.FirebaseAnalytics.LogEvent(eventName, pars.ToArray());
        }
    }

#if FIREBASE_SDK
    internal static class FirebaseProviderRegistration
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        private static void Register()
        {
            AnalyticsRegistry.Register("Firebase", () => new FirebaseProvider(string.Empty));
        }
    }
#endif
}
