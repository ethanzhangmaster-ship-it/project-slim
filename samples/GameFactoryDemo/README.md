# GameFactoryDemo — E13.2.6 Integration Validation Layer

一个**最小真实验证工程**，用来证明 `com.gamefactory.sdk` 在真实 Unity 项目里稳定工作。
它把「SDK 问题 / Watermelon 框架问题 / MAX 问题 / Adjust 问题 / 已有代码问题」隔离开——
任何报错都只可能来自 SDK 本身，不会混进 BusStop 的复杂业务。

```
GameFactorySDK  ──(package)──►  GameFactoryDemo  ──(真实广告SDK)──►  Adjust / Firebase
 (com.gamefactory.sdk)          (本工程, 最小puzzle)      (在Unity里装)
```

> 设计要点：**零场景脚本依赖**。所有验证逻辑由 `Boot.cs` 通过
> `[RuntimeInitializeOnLoadMethod(AfterSceneLoad)]` 自启动并 spawn 出验证 harness，
> 所以即使场景是空的、你也没手动挂任何脚本，点 Play 就能跑全套验证。

---

## 1. 打开工程

1. Unity Hub → **Open** → 选 `launchforge/samples/GameFactoryDemo/` 文件夹（Unity 2022.3+）。
2. 首次打开会：
   - 解析 `Packages/manifest.json` 里的 `"com.gamefactory.sdk": "file:../../com.gamefactory.sdk"`（相对路径，工程需保持在 `launchforge/samples/` 下；移动后改这一行即可）。
   - 引入 SDK 包后，**装真实 SDK 包**：AppLovin MAX（`com.applovin.mediation.max`）、Adjust（`com.adjust.unity`）、Firebase Analytics（`com.google.firebase.analytics`）。
     > 不装也能编（SDK 的条件 asmdef `defineConstraints` 会自动排除未装 provider），但广告/回传不会真跑。
3. 菜单 **GameFactory → Setup Project**：建 `Assets/Resources/GameFactory/`、扫描检测 SDK、开宏（`APPLOVIN_MAX`/`ADJUST_SDK`/`FIREBASE_SDK`）、注入 LevelPlay 引用。
   - 本工程已自带 `Assets/Resources/GameFactory/gamefactory_config.json`，安装器会保留它（不覆盖）。

> 若你把工程挪出 `launchforge/samples/` 层级，记得把 `manifest.json` 里的
> `"file:../../com.gamefactory.sdk"` 改成指向 SDK 包的真实相对/绝对路径。

---

## 2. 验证清单（对应 E13.2.6.2 – E13.2.6.6）

点 **Play**。在 Console 里应看到：

### E13.2.6.2 初始化链路
```
[GameFactory] Config Loaded: GameFactory Demo
[GameFactory] Ads Provider: MAX
[GameFactory] Analytics: Firebase,Adjust
[GameFactory] SDK Ready
```

### E13.2.6.3 Ads 真实测试
GameFactory Test 面板（左上）：
```
Reward Ads      [SHOW]
Interstitial     [SHOW]
Revenue          [READ]
```
- **Reward [SHOW]**：`MAX → Load → Show → Reward Callback → GameFactory Reward Event`；
  控制台 `OnRewardGranted granted=True`。
- **Interstitial [SHOW]**：请求后真出插屏；控制台 `OnInterstitialDisplayed` / `OnInterstitialHidden`。

### E13.2.6.4 Ad Revenue 闭环
看广告产生 impression 后，MAX/LevelPlay 的 `OnAdRevenuePaid` 自动构造 `AdRevenueEvent` 走**单一投递路径**（E13.2.7）：
```
Provider → Analytics.LogEvent(AdRevenueEvent) → EventBuffer → EventUploader → Adjust.trackAdRevenue + Firebase.logEvent
```
（不再是旧的 `Analytics.Track("ad_revenue")` 直发，杜绝重复回传。）验收：**Adjust 后台看到 `ad_revenue`**（USD）。

### E13.2.6.5 Analytics 验证
Analytics 面板 **Send Test Event** → `Analytics.Track("test_event", {source:gamefactory_demo})`。
验收：**Firebase 后台有 `test_event`**；**Adjust 后台有 `test_event`**（SDK 已为它配占位 token `testevt`，上线前换成你的真实 token）。

### E13.2.6.6 RemoteConfig 验证
RemoteConfig 面板应显示：
```
ads.reward_frequency = 3
ads.interstitial_gap = 2
gameplay.level_difficulty = 1.2
gameplay.reward_multiplier = 2
```
`RemoteConfigManager.GetInt("ads.reward_frequency")` 返回 **3**。GameLoop 每 5 关按此值提示发奖。

### E13.2.7 事件层验证（MonetizationTest）
点 **Play** 后，`MonetizationTest.cs` 会自动发齐 9 类标准事件并 Flush（E13.2.7 统一事件层）：
```
install / session_start / level_start / level_complete
ad_request / ad_show / ad_complete
ad_revenue (reward, applovin, US, revenue=0.0325, ecpm=32.5, latency=350)
purchase (remove_ads, 2.99, USD)
```
Console 出现 `[MonetizationTest] ... Buffered events flushed.`，且 Adjust / Firebase 后台应能看到这些事件。
这让本验证工程同时成为 **E13.2.7 事件层 harness**——以后任何 SDK 修改，先跑它 + `events/validate_events.py` 即可。

---

## 3. E13.2.6.7 Android Build 验证（Windows 可跑）

1. `launchforge init`（可选）或本工程自带的 `product.yaml` → 已是标准 schema。
2. Unity 里 **File → Build Settings → 选 Android → 把 `Boot.unity`、`Main.unity` Add Open Scenes → Build**。
3. 装 APK、运行、点 Play 后的面板测广告。验收：**APK 启动无 Crash**。

> iOS 包需要在 macOS / Mac 云跑（Windows 无法打 iOS），见主 README 前提。

---

## 4. E13.2.6.8 Integration Report

`integration_report.json` 由 `validate.py` 生成：Python 侧（配置生成、remote_config 拍平、文件结构、SDK 包）标 **PASS**；
Runtime 项（init / 广告 / 回传 / 分析 / RC / 构建）标 **PENDING_USER_UNITY**，需你在 Unity 里跑完上面清单后手动改成 PASS。

```bash
python validate.py        # 重新生成 config + integration_report.json
```

---

## 5. 已知 Unity 环境限制（诚实清单）

- ⚠️ **本机无 Unity Editor**：所有 C# 按 Unity 2022.3 惯例编写，**未编译验证**。依赖项（asmdef、`defineConstraints`、注册表、安装器、`MaxSdk`/`IronSource`/`Adjust`/`Firebase` API）均按官方写法包裹；个别回调签名请对照你装的 SDK 版本微调（尤其是 `MaxSdkCallbacks.Interstitial.OnAdDisplayedEvent`/`OnAdHiddenEvent` 命名，老版本叫 `OnAdShownEvent`/`OnAdClosedEvent`）。
- ⚠️ **场景文件为最小骨架**：`Boot.unity`/`Main.unity` 只含一个空 GameObject（无 Camera/Light），避免手写复杂序列化出错。运行时由 `Boot.cs` 自启动 spawn harness，因此场景里没有挂任何脚本也能跑（控制台会有一条 "No cameras rendering" 的警告，无害）。
- ⚠️ **广告真跑需真机 + 真 SDK key**：占位 `REPLACE_WITH_*` 必须换成 MAX App Key / 广告位 / Adjust token / Firebase 配置，且测试设备需在该 MAX 应用里加为测试设备。
- ⛔ **iOS 包需 Mac**：Phase4 构建上传送审需在 macOS / Mac 云。
- ⛔ **MAX/LevelPlay 聚合网络首次绑定**多需在后台手动操作一次。

---

## 6. 下一步

E13.2.6 通过 = 你拥有：`GameFactory SDK` + `参考游戏(GameFactoryDemo)` + `集成测试` + `Release Checklist`。
之后任何新游戏不再是「重新调试 SDK」，而是：

```
复制模板 → 改 product.yaml → 生成配置 → 替换素材 → 上线
```

随后进入 **E13.3 Autonomous Monetization Agent**（建立在真实广告收入数据闭环上）。
