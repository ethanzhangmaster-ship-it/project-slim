# GameFactory SDK

Unified game infrastructure SDK for the **LaunchForge** pipeline. Drop it into a Unity project, run
`GameFactory > Setup Project` once, and you get ads (AppLovin MAX / ironSource LevelPlay), analytics
(Firebase / Adjust), remote config, IAP and user management — all config-driven via a single
`gamefactory_config.json`.

This is the "plug-and-play" layer of a Lean Game Factory: every new game copies a template, edits
`product.yaml`, and the LaunchForge CLI generates the config. No per-game SDK wiring.

## Install

1. Add to `Packages/manifest.json`:
   ```json
   {
     "dependencies": {
       "com.gamefactory.sdk": "file:../../launchforge/com.gamefactory.sdk"
     }
   }
   ```
   (or use a git submodule / scoped registry)
2. In Unity: **GameFactory → Auto Setup Everything** (recommended, one click)
   - auto-installs every required package via the Package Manager — AppLovin MAX, Google AdMob,
     Unity IAP, Adjust, Firebase, **and all 8 MAX mediation adapter packages** (Meta / Unity Ads /
     Vungle / Mintegral / Pangle / Amazon APS / InMobi / Chartboost)
   - then copies the config, enables scripting defines, injects asmdef references, and prints the
     EU/US channel readiness report
   - **the only step it can't do for you**: logging into the AppLovin MAX dashboard to *enable* each
     network (that needs your account credentials). Once enabled there, the imported adapter packages
     make every channel `✓` code-ready.
   - **Track it all in one place**: open **GameFactory → Readiness** — a single Unity window
     that shows live code-readiness for every subsystem (ad channels, IAP, analytics, RemoteConfig),
     any `REPLACE_WITH_*` placeholders still left in the config, a one-click *Auto Setup Everything*,
     an *Open MAX Dashboard* button, and a tick-box per mediated network you check off as you enable
     it in MAX (persisted in EditorPrefs). [`MAX_DASHBOARD_ENABLE.md`](MAX_DASHBOARD_ENABLE.md) has the exact
     credentials to paste for each of the 8 networks, and [`Open MAX Dashboard`](#) jumps you there.
   - If you'd rather install packages yourself, the older **GameFactory → Setup Project** menu still
     configures only the already-imported SDKs (no auto-install).
3. Generate runtime config from your `product.yaml`:
   ```bash
   python src/config_generator.py --config samples/busstop.yaml \
       --out "YourProject/Assets/Resources/GameFactory/gamefactory_config.json"
   ```
4. Add `GameFactoryBootstrap` to your boot scene (or call `GameFactory.Initialize()` once).

## Usage

```csharp
using GameFactory;
using GameFactory.Ads;
using GameFactory.Analytics;
using GameFactory.IAP;
using GameFactory.RemoteConfig;

// bootstrap (or call manually)
GameFactory.OnReady += () => Debug.Log("GameFactory Ready");

// ads (provider selected by config.ads.provider: MAX / LevelPlay / AdMob)
AdsManager.ShowReward(onComplete => { if (onComplete) GrantPrize(); });
AdsManager.ShowInterstitial();

// IAP (Unity IAP; catalog comes from config.iap.products)
IAPManager.Purchase("remove_ads");
IAPManager.Restore(); // iOS

// analytics
Analytics.Track("level_complete", new() { ["level"] = 10 });

// remote config (dot-path from nested product.yaml)
float freq = RemoteConfigManager.GetFloat("ads.reward_frequency");
```

## Architecture

Each subsystem is its own assembly definition so the host project never recompiles all of GameFactory,
and conditional providers only compile when their SDK + scripting define are present
(`defineConstraints` in the `.asmdef`):

```
GameFactory.Runtime      Core: config, ServiceLocator
GameFactory             Orchestrator: GameFactory facade + bootstrap
GameFactory.Ads          AdsManager + IAdProvider + AdChannelRegistry
  .Ads.Max              MaxAdProvider        (APPLOVIN_MAX + MaxSdk)        — standalone
  .Ads.LevelPlay        LevelPlayProvider    (MODULE_LEVELPLAY + IronSource) — standalone
  .Ads.AdMob            AdMobProvider        (GOOGLE_MOBILE_ADS + GoogleMobileAds) — standalone
GameFactory.Analytics   Analytics + IAnalyticsProvider
  .Analytics.Adjust     AdjustProvider       (ADJUST_SDK + Adjust)
  .Analytics.Firebase   FirebaseProvider     (FIREBASE_SDK + Firebase.Analytics)
GameFactory.RemoteConfig / .IAP (Unity IAP: UNITY_PURCHASING) / .User
```

Providers self-register via `AdProviderRegistry` / `AnalyticsRegistry` under
`[RuntimeInitializeOnLoadMethod(BeforeSceneLoad)]`, so the facade resolves them by config key with no
static cross-assembly dependency.

## Event Stream → Backend (E15.2.7)

Structured gameplay/ad events flow through `EventBuffer` (offline JSONL cache + replay) and are
flushed through an `IEventUploader`:

- **`AnalyticsEventUploader`** (default): forwards to the enabled Adjust / Firebase providers.
- **`RemoteEventUploader`** (E15.2.7): POSTs the buffered batch to `AnalyticsConfig.event_endpoint`
  via `UnityWebRequest` (fire-and-forget, non-blocking). **Disabled by default** — when `event_endpoint`
  is empty the SDK makes no network calls and events stay in the offline cache for replay.

`RemoteEventUploader` is drop-in safe: it **auto-appends `/events`** to whatever endpoint you paste
(no need to remember the path) and sends the game's `app_id` as the **`X-Game-Id` header** so the
receiver routes events into `data/player_events/<app_id>.jsonl`. `app_id` comes from
`analytics.app_id` (set by `config_generator.py` from `product.app_id`/`bundle_id`/`slug`), falling
back to `Analytics.GameSlug`.

### Wire it up (zero manual JSON editing)

1. Generate runtime config (already fills `event_endpoint` + `app_id`):
   ```bash
   python src/config_generator.py --config samples/busstop.yaml \
       --out "YourProject/Assets/Resources/GameFactory/gamefactory_config.json"
   ```
2. In Unity, **GameFactory → Configure Event Backend** (new one-click menu): paste the receiver URL
   (e.g. `http://10.0.0.5:8765`) and the App ID, hit **Apply**. That writes them into the copied
   `gamefactory_config.json`. Leave the endpoint blank to stay offline-only.
3. Add `GameFactoryBootstrap` to your boot scene.

Set the endpoint in `gamefactory_config.json` (generated by `config_generator.py`):

```json
"analytics": {
  "providers": ["Firebase","Adjust"],
  "event_endpoint": "https://your-host",
  "app_id": "com.yourstudio.yourgame"
}
```

> **Contract is verified without Unity.** `tests/e15_2_8/test_p4_sdk_contract.py` replicates the exact
> envelope `GameFactory.Analytics.Events.GameEvent.ToDictionary()` emits (props **flattened** to the
> top level), POSTs it to a real in-process receiver, and asserts every event is accepted, `ad_type` /
> `network` / `revenue` survive normalization, and `X-Game-Id` routes events to the right app sink.
> Run `pytest tests/e15_2_8/test_p4_sdk_contract.py`.

The matching Lean receiver lives in the LaunchForge OS (Python stdlib only, no Flask/FastAPI):

```bash
python -m operation.player_monetization.ingest serve            # run receiver on :8765
python -m operation.player_monetization.ingest collect --app <app_id>   # events -> PlayerProfiles
```

Unity envelopes are normalized to the `player` / `ad` / `game` contract by
`operation/player_monetization/normalize.py` (which accepts the SDK's flattened `props` layout),
validated, and appended to `data/player_events/<app_id>.jsonl` — which `SDKProvider` reads so the
events reach `EventCollector` → `PlayerProfile` → Ad Experience Optimizer / frequency / user-value models.

## EU/US Channel Coverage

"Connect all mainstream EU/US channels" maps to two models. Run **GameFactory → Setup Project**; the
installer prints a readiness report for every channel below, then **scans the imported AppLovin MAX
mediation adapter packages** (`com.applovin.mediation.adapters.*`) and marks each mediated channel
`✓` (adapter package already imported — just enable in the MAX dashboard) or `•` (needs the adapter
package imported + dashboard enable).

| Channel | Mode | How it's connected |
|---|---|---|
| **AppLovin MAX** | Standalone | `provider:"MAX"` — mediation hub; recommended. Mediates all networks below. |
| **ironSource LevelPlay** | Standalone | `provider:"LevelPlay"` — alternative mediation. |
| **Google AdMob** | Standalone **and** mediated | `provider:"AdMob"` for direct (Google Mobile Ads SDK), or via MAX. |
| Meta Audience Network | Mediated | Enable in MAX dashboard + import MAX adapter pkg. |
| Unity Ads | Mediated | Enable in MAX dashboard + import MAX adapter pkg. |
| Vungle (Liftoff) | Mediated | Enable in MAX dashboard + import MAX adapter pkg. |
| Mintegral | Mediated | Enable in MAX dashboard + import MAX adapter pkg. |
| Pangle (TikTok) | Mediated | Enable in MAX dashboard + import MAX adapter pkg. |
| Amazon APS | Mediated | Enable in MAX dashboard + import MAX adapter pkg. |
| InMobi | Mediated | Enable in MAX dashboard + import MAX adapter pkg. |
| Chartboost | Mediated | Enable in MAX dashboard + import MAX adapter pkg. |
| **Unity IAP** (in-app purchases) | Standalone | `IAPManager` wired to `UnityEngine.Purchasing`; catalog from `config.iap.products`. |

> **Why no per-network C# adapter for Meta/Vungle/Mintegral/Pangle/UnityAds/Amazon/InMobi/Chartboost?**
> They are *mediated networks* under MAX/LevelPlay. AppLovin's MAX adapter package already bundles
> each network's own SDK; writing a separate adapter here would be redundant (and would re-implement
> what the mediation layer does). "Connecting" them = enable in the MAX dashboard + import the MAX
> network adapter package into the Unity project. The standalone adapters (MAX/LevelPlay/AdMob) and
> `AdChannelRegistry.EuUsChannels` are the only native code.

> Note: C# is written to Unity 2022.3 conventions but not compiled in this repo (no Unity here).
> Verify callback signatures against the exact SDK versions you install; the conditional assembly
> pattern guarantees it still compiles standalone when an SDK is absent.
