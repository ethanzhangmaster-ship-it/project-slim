using GameFactory;
using UnityEngine;

namespace GameFactory.Samples.BusStopDemo
{
    /// <summary>
    /// Attach to a GameObject in your Boot scene. Initializes the SDK and logs the ready event.
    /// In a real game you'd also DontDestroyOnLoad this object.
    /// </summary>
    public class DemoBootstrap : MonoBehaviour
    {
        private void Awake()
        {
            GameFactory.Initialize();
            GameFactory.OnReady += () => Debug.Log("[Demo] GameFactory Ready");
        }
    }
}
