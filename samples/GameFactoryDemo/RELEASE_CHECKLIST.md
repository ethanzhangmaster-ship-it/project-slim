# Release Checklist — 新游戏上线路线（E13.2.6 收尾交付物）

> E13.2.6 结束后你拥有的四件套：
> 1. **GameFactory SDK**（`com.gamefactory.sdk`，可插拔 UPM 包）
> 2. **参考游戏**（`samples/GameFactoryDemo`，最小真实验证工程）
> 3. **集成测试**（init / ads / revenue / analytics / remote_config 验证脚本 + `integration_report.json`）
> 4. **Release Checklist**（本文件）

从此每款新游戏不再「重新调试 SDK」，而是走下面这条 5 步流：

---

## 新游戏 5 步流

- [ ] **1. 复制模板**
  `python ../../cli.py init --name "Word Puzzle 02" --genre word --platform android,ios --ads MAX --analytics Firebase,Adjust`
  → 生成 `launchforge/games/<slug>/`（product.yaml / monetization.yaml / release.yaml / gamefactory_config.json）

- [ ] **2. 改 product.yaml**
  - `product.name` / `package_name` / `bundle_id` / `unity_version`
  - `monetization.sdk_keys` / `monetization.placements`（真 MAX App Key / 广告位）
  - `analytics.firebase_key` / `analytics.adjust_token`
  - `remote_config`（激励频率、难度系数等）
  - `iap_products`（如需内购）

- [ ] **3. 生成配置**
  `python ../../src/config_generator.py --config product.yaml --out "<YourUnityProject>/Assets/Resources/GameFactory/gamefactory_config.json"`

- [ ] **4. 替换素材 / 写游戏**
  - 把 `GameFactoryDemo` 的脚本/场景结构作为模板，替换为你自己的玩法素材
  - 首场景确保 `GameFactory.Initialize()` 被调用（挂 `GameFactoryBootstrap` 或本 demo 的 `Boot.cs` 自启动）
  - 接广告：`AdsManager.ShowReward(...)` / `ShowInterstitial()`；分析：`Analytics.Track(...)`；配置：`RemoteConfigManager.GetInt(...)`

- [ ] **5. 上线**
  - Unity 里 `GameFactory > Setup Project` → 装 SDK 包 → 开宏
  - `launchforge/src/orchestrator.py --config product.yaml --project <YourUnityProject> --apply`（构建/上传/送审，送审前有确认门）

---

## E13.2.6 验收 Gate（在 Unity 里逐项打勾）

- [ ] **Bootstrap 初始化**：Console 出现 `Config Loaded / Ads Provider / Analytics / SDK Ready`
- [ ] **Reward 广告**：真出激励视频，`OnRewardGranted granted=True`
- [ ] **Interstitial**：真出插屏，`OnInterstitialDisplayed` + `OnInterstitialHidden`
- [ ] **Ad Revenue 闭环**：Adjust 后台出现 `ad_revenue`（USD）
- [ ] **Analytics**：Firebase + Adjust 后台均出现 `test_event`
- [ ] **RemoteConfig**：`GetInt("ads.reward_frequency")` == 3
- [ ] **Android Build**：APK 启动无 Crash，面板可点广告
- [ ] **integration_report.json**：上面 7 项 runtime 由 `PENDING_USER_UNITY` 改为 `PASS`

---

## 真机/账号一次性准备

- [ ] Apple 开发者账号 + App Store Connect API（p8/issuer/key_id）—— iOS 必需
- [ ] Google Play 开发者账号 + Service Account JSON —— Android 必需
- [ ] AppLovin / LevelPlay 账号 + API Key，且应用/广告位已在后台建好
- [ ] MAX 测试设备已加白（避免真量污染）
- [ ] 隐私政策托管页（商店强制）
- [ ] Mac / Mac 云（iOS 构建签名上传必需；Android 在 Windows 即可）
