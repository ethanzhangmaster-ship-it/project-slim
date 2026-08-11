# BusStopDemo — GameFactory SDK Integration Sample

A minimal Unity project skeleton showing how to wire the GameFactory SDK into a new game.
This is the reference template every new game copies (the "5-minute onboarding" target).

## Assemble the scene (Unity 2022.3+)

1. Install the SDK: add to `Packages/manifest.json`
   ```json
   { "dependencies": { "com.gamefactory.sdk": "file:../../launchforge/com.gamefactory.sdk" } }
   ```
2. **GameFactory → Setup Project** (menu). This creates `Assets/Resources/GameFactory/gamefactory_config.json`
   and enables scripting defines for any detected SDK (MAX / LevelPlay / Adjust / Firebase).
3. Generate the runtime config from your `product.yaml`:
   ```bash
   python ../../launchforge/src/config_generator.py --config ../../launchforge/samples/busstop.yaml \
       --out "Assets/Resources/GameFactory/gamefactory_config.json"
   ```
4. Create a `Boot` scene with:
   - A GameObject `Bootstrap` carrying **DemoBootstrap** (initializes the SDK).
   - A Canvas with:
     - **Reward** button + **Interstitial** button → assign to **DemoAdsButton**
     - **Level Complete** button → assign to **DemoAnalytics**
     - A **Text** → assign to **DemoRemoteConfig**
5. Install the SDKs you enabled (AppLovin MAX / ironSource LevelPlay / Adjust / Firebase) and fill the
   real `app_key` / placement ids / tokens in `gamefactory_config.json`.

## Verify

- Click **Reward** → MAX (or LevelPlay) rewarded ad shows → `reward complete=True` logged → grant prize.
- Click **Level Complete** → `level_complete` event fans out to Adjust + Firebase.
- `ads.reward_frequency` text shows the value from remote config (edit in `product.yaml` and regenerate
  to change without rebuilding).
- Ad impression revenue is auto-routed to `Analytics.Track("ad_revenue", ...)` → Adjust `trackAdRevenue`.

> These scripts live outside the SDK package and compile against the SDK's public facade
> (`GameFactory`, `GameFactory.Ads`, `GameFactory.Analytics`, `GameFactory.RemoteConfig`).
