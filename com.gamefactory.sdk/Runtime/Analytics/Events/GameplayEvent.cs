namespace GameFactory.Analytics.Events
{
    /// <summary>
    /// Factory for the common gameplay / lifecycle events E13.2.7 must standardize.
    /// Usage:
    ///   Analytics.LogEvent(GameplayEvent.LevelStart(3));
    ///   Analytics.LogEvent(GameplayEvent.AdComplete("reward", "reward_01", true));
    /// </summary>
    public class GameplayEvent : GameEvent
    {
        public GameplayEvent(string name) : base(name) { }

        public static GameplayEvent Install() => new GameplayEvent("install");
        public static GameplayEvent SessionStart() => new GameplayEvent("session_start");

        public static GameplayEvent AdRequest(string format, string placement, string network = "")
        {
            var e = new GameplayEvent("ad_request");
            e.props["ad_format"] = format;
            e.props["placement"] = placement;
            e.props["network"] = network;
            return e;
        }

        public static GameplayEvent AdShow(string format, string placement)
        {
            var e = new GameplayEvent("ad_show");
            e.props["ad_format"] = format;
            e.props["placement"] = placement;
            return e;
        }

        public static GameplayEvent AdComplete(string format, string placement, bool completed)
        {
            var e = new GameplayEvent("ad_complete");
            e.props["ad_format"] = format;
            e.props["placement"] = placement;
            e.props["completed"] = completed;
            return e;
        }

        public static GameplayEvent LevelStart(int level)
        {
            var e = new GameplayEvent("level_start");
            e.props["level"] = level;
            return e;
        }

        public static GameplayEvent LevelComplete(int level, double score = 0)
        {
            var e = new GameplayEvent("level_complete");
            e.props["level"] = level;
            e.props["score"] = score;
            return e;
        }

        public static GameplayEvent Purchase(string productId, double price, string currency)
        {
            var e = new GameplayEvent("purchase");
            e.props["product_id"] = productId;
            e.props["price"] = price;
            e.props["currency"] = currency;
            return e;
        }
    }
}
