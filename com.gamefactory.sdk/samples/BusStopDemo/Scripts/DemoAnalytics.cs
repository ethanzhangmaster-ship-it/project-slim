using GameFactory.Analytics;
using UnityEngine;
using UnityEngine.UI;

namespace GameFactory.Samples.BusStopDemo
{
    /// <summary>
    /// Wire a button that fires a "level_complete" analytics event.
    /// With Adjust + Firebase providers enabled, the event fans out to both backends.
    /// </summary>
    public class DemoAnalytics : MonoBehaviour
    {
        public Button levelCompleteButton;
        private int _level = 1;

        private void Start()
        {
            levelCompleteButton?.onClick.AddListener(() =>
            {
                Analytics.Track("level_complete", new() { ["level"] = _level });
                _level++;
            });
        }
    }
}
