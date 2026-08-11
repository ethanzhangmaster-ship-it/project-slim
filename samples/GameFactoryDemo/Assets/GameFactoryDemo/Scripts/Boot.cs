using GameFactory;
using UnityEngine;

namespace GameFactory.Samples.GameFactoryDemo
{
    /// <summary>
    /// E13.2.6 Integration Validation Layer — entry point.
    ///
    /// Self-initializes via [RuntimeInitializeOnLoadMethod(AfterSceneLoad)] so the demo runs even
    /// on a completely blank scene (no need to attach scripts to scene GameObjects). This keeps the
    /// GameFactoryDemo project friction-free: just open it in Unity and hit Play.
    ///
    /// If you prefer explicit scene wiring, attach this to a GameObject in Boot.unity — the Awake
    /// path is guarded by the same static flag, so double-init is impossible.
    ///
    /// Chain verified by E13.2.6.2:
    ///   Boot -> GameFactoryBootstrap -> Load Config -> Init Core -> Init Ads -> Init Analytics -> Ready
    /// </summary>
    [AddComponentMenu("GameFactory/Demo/Boot")]
    public class Boot : MonoBehaviour
    {
        private static bool _booted;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadMethod.AfterSceneLoad)]
        private static void AutoBoot()
        {
            if (_booted) return;
            _booted = true;

            GameFactory.Initialize();   // guarded inside; loads config + inits every subsystem

            // Spawn the validation harness once (idempotent: skip if a GameLoop already exists).
            if (Object.FindObjectOfType<GameLoop>() == null)
            {
                var go = new GameObject("GameFactoryDemo");
                Object.DontDestroyOnLoad(go);
                go.AddComponent<GameLoop>();
                go.AddComponent<AdTestController>();
                go.AddComponent<AnalyticsTest>();
                go.AddComponent<RemoteConfigTest>();
            }
        }

        private void Awake() => AutoBoot();
    }
}
