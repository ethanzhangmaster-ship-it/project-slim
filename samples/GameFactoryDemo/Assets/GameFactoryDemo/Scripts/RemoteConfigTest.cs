using GameFactory.RemoteConfig;
using UnityEngine;

namespace GameFactory.Samples.GameFactoryDemo
{
    /// <summary>
    /// E13.2.6.6 — RemoteConfig validation panel.
    /// Reads the dot-path keys flattened from product.yaml's nested remote_config and shows them.
    /// Expected (per demo product.yaml): ads.reward_frequency = 3.
    /// </summary>
    [AddComponentMenu("GameFactory/Demo/RemoteConfig Test")]
    public class RemoteConfigTest : MonoBehaviour
    {
        private void Awake()
        {
            int freq = RemoteConfigManager.GetInt("ads.reward_frequency");
            int gap = RemoteConfigManager.GetInt("ads.interstitial_gap");
            float diff = RemoteConfigManager.GetFloat("gameplay.level_difficulty");
            float mult = RemoteConfigManager.GetFloat("gameplay.reward_multiplier");
            Debug.Log($"[RemoteConfig] ads.reward_frequency={freq} ads.interstitial_gap={gap} " +
                      $"gameplay.level_difficulty={diff} gameplay.reward_multiplier={mult}");
            if (freq != 3) Debug.LogWarning("[RemoteConfig] ads.reward_frequency expected 3, got " + freq);
        }

        private void OnGUI()
        {
            GUILayout.BeginArea(new Rect(10, 340, 320, 120), "RemoteConfig", GUI.skin.box);
            GUILayout.Label("ads.reward_frequency = " + RemoteConfigManager.GetInt("ads.reward_frequency"));
            GUILayout.Label("ads.interstitial_gap = " + RemoteConfigManager.GetInt("ads.interstitial_gap"));
            GUILayout.Label("gameplay.level_difficulty = " + RemoteConfigManager.GetFloat("gameplay.level_difficulty"));
            GUILayout.Label("gameplay.reward_multiplier = " + RemoteConfigManager.GetFloat("gameplay.reward_multiplier"));
            GUILayout.EndArea();
        }
    }
}
