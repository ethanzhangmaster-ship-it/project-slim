using GameFactory.Ads;
using UnityEngine;
using UnityEngine.UI;

namespace GameFactory.Samples.BusStopDemo
{
    /// <summary>
    /// Wire two UI buttons: one shows a rewarded ad, one an interstitial.
    /// Drag this onto a Canvas with two Buttons and assign them in the inspector.
    /// </summary>
    public class DemoAdsButton : MonoBehaviour
    {
        public Button rewardButton;
        public Button interstitialButton;

        private void Start()
        {
            rewardButton?.onClick.AddListener(() =>
                AdsManager.ShowReward(complete => Debug.Log("[Demo] reward complete=" + complete)));
            interstitialButton?.onClick.AddListener(() => AdsManager.ShowInterstitial());
        }
    }
}
