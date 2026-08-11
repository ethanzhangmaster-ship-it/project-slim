using GameFactory;
using UnityEngine;

namespace GameFactory
{
    /// <summary>
    /// Attach to a GameObject in your first (boot) scene. Calls GameFactory.Initialize()
    /// once, then persists across scene loads.
    /// Alternatively subscribe to GameFactory.OnReady for the "ready" moment:
    ///   GameFactory.OnReady += () => Debug.Log("GameFactory Ready");
    /// </summary>
    [AddComponentMenu("GameFactory/GameFactory Bootstrap")]
    public class GameFactoryBootstrap : MonoBehaviour
    {
        private void Awake()
        {
            GameFactory.Initialize();
            DontDestroyOnLoad(gameObject);
        }
    }
}
