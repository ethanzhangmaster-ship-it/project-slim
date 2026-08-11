using GameFactory.Ads;
using UnityEngine;

namespace GameFactory.Samples.GameFactoryDemo
{
    /// <summary>
    /// E13.2.6.3 / E13.2.6.4 — Ads real-test panel + Ad Revenue closed-loop observation.
    ///
    /// Panel (OnGUI):
    ///   Reward Ads      [SHOW]
    ///   Interstitial     [SHOW]
    ///   Revenue          [READ]
    ///
    /// Subscribes to AdsManager lifecycle events so the console shows:
    ///   OnInterstitialDisplayed / OnInterstitialHidden / OnRewardGranted
    /// and (E13.2.6.4) the MAX OnAdRevenuePaidEvent -> Analytics -> Adjust/Firebase path runs
    /// automatically inside the SDK's MaxAdProvider.
    /// </summary>
    [AddComponentMenu("GameFactory/Demo/Ad Test Controller")]
    public class AdTestController : MonoBehaviour
    {
        private Vector2 _scroll;

        private void OnEnable()
        {
            AdsManager.OnInterstitialDisplayed += () => Debug.Log("[AdTest] OnInterstitialDisplayed");
            AdsManager.OnInterstitialHidden += () => Debug.Log("[AdTest] OnInterstitialHidden");
            AdsManager.OnRewardGranted += granted => Debug.Log("[AdTest] OnRewardGranted granted=" + granted);
        }

        private void OnGUI()
        {
            GUILayout.BeginArea(new Rect(10, 10, 320, 220), "GameFactory Test", GUI.skin.box);
            GUILayout.Label("Reward Ads");
            if (GUILayout.Button("SHOW")) ShowReward();
            GUILayout.Space(6);

            GUILayout.Label("Interstitial");
            if (GUILayout.Button("SHOW")) ShowInterstitial();
            GUILayout.Space(6);

            GUILayout.Label("Revenue");
            if (GUILayout.Button("READ")) ReadRevenue();
            GUILayout.EndArea();
        }

        private void ShowReward()
        {
            Debug.Log("[AdTest] Reward: MAX -> Load -> Show -> Reward Callback -> GameFactory Reward Event");
            AdsManager.ShowReward(complete =>
                Debug.Log("[AdTest] Reward callback complete=" + complete));
        }

        private void ShowInterstitial()
        {
            Debug.Log("[AdTest] Interstitial [SHOW] requested");
            AdsManager.ShowInterstitial();
        }

        private void ReadRevenue()
        {
            double rev = AdsManager.GetRevenue();
            Debug.Log("[AdTest] Revenue read = " + rev.ToString("F6"));
        }
    }
}
