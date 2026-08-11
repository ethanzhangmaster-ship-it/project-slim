using System;

namespace GameFactory.Analytics.Events
{
    /// <summary>
    /// Unified ad-revenue impression. Mirrors the E13.2.7 canonical schema:
    ///   event, game, platform, country,
    ///   ad_format, network, placement, ad_unit,
    ///   ecpm, revenue, latency, timestamp
    ///
    /// <c>ecpm</c> is the per-impression proxy (revenue * 1000); aggregate eCPM over a cohort /
    /// time window is computed downstream in the Dataset (E13.3). <c>latency</c> is the
    /// request→revenue gap in ms (approximate; one outstanding request per format).
    /// </summary>
    public class AdRevenueEvent : GameEvent
    {
        public AdRevenueEvent() : base("ad_revenue") { }

        public void Set(string adFormat, string network, string placement, string adUnit,
                        double revenue, string country, long latencyMs = 0)
        {
            props["ad_format"] = adFormat;
            props["network"] = network;
            props["placement"] = placement;
            props["ad_unit"] = adUnit;
            props["revenue"] = Math.Round(revenue, 6);
            props["ecpm"] = Math.Round(revenue * 1000.0, 4);
            props["latency"] = latencyMs;
            this.country = country;
        }
    }
}
