using System.Collections.Generic;

namespace GameFactory.Analytics
{
    /// <summary>
    /// Adapter contract for analytics backends (Firebase, Adjust, ...).
    /// </summary>
    public interface IAnalyticsProvider
    {
        void Track(string eventName, Dictionary<string, object> parameters);
    }
}
