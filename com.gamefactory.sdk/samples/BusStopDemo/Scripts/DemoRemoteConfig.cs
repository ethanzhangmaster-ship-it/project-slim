using GameFactory.RemoteConfig;
using UnityEngine;
using UnityEngine.UI;

namespace GameFactory.Samples.BusStopDemo
{
    /// <summary>
    /// Reads a remote-config value at runtime and shows it on a Text.
    /// Change the value in product.yaml -> gamefactory_config.json (or via AI push) without a rebuild.
    /// </summary>
    public class DemoRemoteConfig : MonoBehaviour
    {
        public Text output;
        private const string Key = "ads.reward_frequency";

        private void Start()
        {
            float freq = RemoteConfigManager.GetFloat(Key);
            if (output != null) output.text = Key + " = " + freq;
            Debug.Log("[Demo] " + Key + " = " + freq);
        }
    }
}
