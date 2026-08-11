using GameFactory.Analytics;
using UnityEngine;

namespace GameFactory.Samples.GameFactoryDemo
{
    /// <summary>
    /// E13.2.6.5 — Analytics validation panel.
    /// "Send Test Event" fires Analytics.Track("test_event", {source:gamefactory_demo})
    /// which fans out to every enabled provider (Firebase + Adjust).
    ///   - Firebase backend:  event "test_event" appears
    ///   - Adjust backend:    event "test_event" appears (token "testevt" in AdjustProvider.EventTokens)
    /// </summary>
    [AddComponentMenu("GameFactory/Demo/Analytics Test")]
    public class AnalyticsTest : MonoBehaviour
    {
        private void OnGUI()
        {
            GUILayout.BeginArea(new Rect(10, 240, 320, 90), "Analytics", GUI.skin.box);
            if (GUILayout.Button("Send Test Event"))
            {
                Analytics.Track("test_event", new() { ["source"] = "gamefactory_demo" });
                Debug.Log("[AnalyticsTest] sent 'test_event' -> Firebase + Adjust");
            }
            GUILayout.EndArea();
        }
    }
}
