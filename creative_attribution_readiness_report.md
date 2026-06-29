# Creative Attribution Readiness Report

审计时间：2026-06-05

审计范围：

- 当前代码
- 当前环境配置
- 当前依赖包
- 当前 API client 设计

明确不看：

- 飞书表内容
- 飞书素材表
- 飞书回写结果

---

## 结论先看

当前项目代码里，`Meta Marketing API Client` 和 `Google Ads Client` 都已经存在。

但按“当前代码 + 当前配置 + 当前 API 权限状态”来判断：

- 当前 **不具备** 实际拉取 Meta 素材级数据的运行条件
- 当前 **不具备** 实际拉取 Google Ads 素材级数据的运行条件
- 当前即使补上凭证，也 **还不能直接完成 Creative Attribution 闭环**

原因不是一个，而是三层：

1. 代码层：client 已存在，但字段持久化模型不完整
2. 配置层：当前 Meta / Google Ads 凭证全部未配置
3. 归因层：当前没有把 `Creative / Ad / Campaign / Adset` 与 `Adjust revenue` 通过统一主键串起来

一句话判断：

**当前是“有 client 原型，但没有可运行权限，也没有完整归因落库模型”。**

---

## 1. 当前代码里是否已经存在 API Client

### Meta Marketing API Client

结论：**YES**

已存在文件：

- `src/market_ops/clients/meta_ads.py`

当前代码能力：

- 调 Meta Insights API，`level=ad`
- 调 Ads API，读取 ad metadata 和 creative metadata
- 按 creative 聚合 spend / click / conversion / conversion value

### Google Ads Client

结论：**YES**

已存在文件：

- `src/market_ops/clients/google_ads.py`

当前代码能力：

- 通过 `google-ads` SDK 读取 `ad_group_ad_asset_view`
- 通过 `google-ads` SDK 读取 `asset_group_asset`
- 按 asset 聚合 cost / clicks / conversions / conversions_value

### 依赖包状态

结论：**代码依赖已安装**

本地已可导入：

- `requests`
- `google.ads.googleads.client`

说明：

- Meta client 依赖 `requests`
- Google client 依赖 `google-ads`
- 依赖层不是当前阻塞点

---

## 2. 当前配置是否已经具备运行条件

当前环境结论：

- `using_meta_creative_source = False`
- `using_google_creative_source = False`

原因是下面这些配置当前都没有填：

### Meta 当前配置状态

| 配置项 | 当前状态 |
| --- | --- |
| `META_ACCESS_TOKEN` | 未配置 |
| `META_AD_ACCOUNT_ID` | 未配置 |

### Google 当前配置状态

| 配置项 | 当前状态 |
| --- | --- |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | 未配置 |
| `GOOGLE_ADS_CLIENT_ID` | 未配置 |
| `GOOGLE_ADS_CLIENT_SECRET` | 未配置 |
| `GOOGLE_ADS_REFRESH_TOKEN` | 未配置 |
| `GOOGLE_ADS_CUSTOMER_ID` | 未配置 |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | 未配置 |

审计结论：

- 当前不是“权限不够但已连接”
- 而是“**根本没有进入 API creative source 模式**”

---

## 3. Meta(Facebook) 素材级数据 readiness

### 3.1 代码层能拿哪些字段

按当前 `meta_ads.py` 实际请求字段看：

| 字段 | 代码是否请求 | 备注 |
| --- | --- | --- |
| Creative ID | YES | `creative{id,...}` |
| Creative Name | YES | `creative{name,...}` |
| Ad ID | YES | `ad_id` |
| Ad Name | YES | `ad_name` |
| Campaign | YES | `campaign_name` / `campaign{name}` |
| Adset | YES | `adset_name` / `adset{name}` |
| Spend | YES | `spend` |
| Click | YES | `clicks` |
| Install | PARTIAL | 从 `actions` 中尝试提取 `mobile_app_install / app_install / omni_app_install` |
| CTR | YES | `ctr` |
| Impression | YES | `impressions` |
| Purchase / Revenue Value | PARTIAL | 从 `action_values` 提取 purchase value，不是 Adjust revenue |

### 3.2 当前代码能否稳定输出这些字段

结论：**不能完整输出**

原因：

当前 Meta client 最终只会落成 `CreativeAssetRow`，这个模型只有：

- `asset_id`
- `creative_type`
- `video_path`
- `game`
- `country`
- `channel`
- `ctr`
- `cvr`
- `roas`
- `spend`
- `status`
- `hook_type`
- `duration`

也就是说，下面这些字段虽然代码请求了，但**没有进入最终标准化输出**：

- `creative_name`
- `ad_id`
- `ad_name`
- `campaign`
- `adset`
- `install`

### 3.3 当前是否具备实际 API 权限

结论：**NO**

当前缺少：

- `META_ACCESS_TOKEN`
- `META_AD_ACCOUNT_ID`

在未填这两个配置之前，当前系统不能发起真实 Meta creative 拉取。

### 3.4 当前还缺哪些权限信息

从代码设计推断，至少需要：

- 有效的 Meta user access token
- token 具备读取广告数据的 scope
- token 所属用户有目标广告账户访问权限
- 广告账户所在 Business 对该用户开放可读权限

保守判断：

- 至少需要 `ads_read`
- 如果账户归属复杂，还需要确认 Business asset access

当前审计状态：

- **代码有入口**
- **配置没有**
- **实际 scope / 广告账户权限 / Business 权限 都无法验证**

---

## 4. Google Ads 素材级数据 readiness

### 4.1 代码层能拿哪些字段

按当前 `google_ads.py` 实际查询字段看：

| 字段 | 代码是否请求 | 备注 |
| --- | --- | --- |
| Asset ID | YES | `asset.id` |
| Asset Name | YES | `asset.name` |
| Ad ID | NO | 当前没有查 `ad_group_ad.ad.id` 或等价字段 |
| Ad Name | NO | 当前没有查 ad name |
| Ad Group | YES | `ad_group.name` |
| Asset Group | YES | `asset_group.name` |
| Campaign | YES | `campaign.name` |
| Cost | YES | `metrics.cost_micros` |
| Click | YES | `metrics.clicks` |
| Conversion | YES | `metrics.conversions` |
| Conversion Value | YES | `metrics.conversions_value` |
| Install | PARTIAL | 没有显式 install 字段，只能把 conversions 当作“可能的安装”或其他转化 |

### 4.2 当前代码能否稳定输出这些字段

结论：**不能完整输出**

和 Meta 一样，Google client 最终也只会落成 `CreativeAssetRow`。

因此下列字段虽然代码查询到了部分，但**没有进入最终标准化输出**：

- `asset_name`
- `ad_group`
- `campaign`
- `conversions`
- `conversion_value`

下列字段当前代码根本没查：

- `ad_id`
- `ad_name`

### 4.3 当前是否具备实际 API 权限

结论：**NO**

当前缺少：

- `GOOGLE_ADS_DEVELOPER_TOKEN`
- `GOOGLE_ADS_CLIENT_ID`
- `GOOGLE_ADS_CLIENT_SECRET`
- `GOOGLE_ADS_REFRESH_TOKEN`
- `GOOGLE_ADS_CUSTOMER_ID`

所以当前系统不能发起真实 Google Ads creative 拉取。

### 4.4 当前还缺哪些权限信息

从代码设计推断，至少需要：

- 有效的 Google Ads developer token
- OAuth client
- refresh token
- 对目标 customer account 的访问权限
- 如果是 MCC 场景，可能还需要 `login_customer_id`

当前审计状态：

- **代码有入口**
- **依赖已装**
- **配置没有**
- **customer account 访问权限无法验证**

---

## 5. 当前是否已经具备“素材级数据可获取”能力

这里分两层回答。

### 5.1 从“代码原型是否存在”看

结论：**YES，部分具备**

因为：

- Meta client 已写
- Google client 已写
- pipeline 里也已经有切换逻辑

### 5.2 从“当前环境是否真的能拉下来”看

结论：**NO，不具备**

因为：

- 当前所有 Meta 凭证都没配
- 当前所有 Google Ads 凭证都没配
- 当前 creative output 模型也不保留归因关键字段

所以真实状态不是“差一点”，而是：

**现在只能说‘代码层预留了入口’，不能说‘已经具备素材级采集能力’。**

---

## 6. 如果要把 Creative -> Spend -> Install -> Adjust Revenue 串起来，最小开发方案是什么

虽然当前还不具备运行权限，但最小开发方案已经比较明确。

### 最小方案目标

把下面这条链路串起来：

`Creative`
-> `Spend / Click / Install`
-> `Ad / Campaign / Adset`
-> `Adjust cohort revenue`
-> `Creative payback / Creative ROI`

### 最小开发方案

#### Step 1. 扩展 creative 标准化模型

当前 `CreativeAssetRow` 不够。

至少新增：

- `creative_id`
- `creative_name`
- `ad_id`
- `ad_name`
- `campaign_name`
- `adset_name` 或 `ad_group_name`
- `impressions`
- `clicks`
- `installs`
- `conversions`
- `conversion_value`
- `source_platform`

#### Step 2. 单独落一张 paid creative performance 明细表

不要继续复用现在的 `creative_library.csv`。

应该新增类似：

- `creative_performance.csv`

主键建议：

- `date`
- `platform`
- `network`
- `campaign`
- `adset_or_ad_group`
- `ad_id`
- `creative_id`

#### Step 3. 统一 Install / Revenue 归因口径

最小闭环通常需要：

- 广告侧：`creative_id -> ad_id -> install/conversion`
- Adjust 侧：按 campaign / network / tracker / creative parameter 回传安装与收入

如果 Adjust 当前没有带回 creative 级参数，那就需要补：

- tracker parameter mapping
- callback / raw export
- 或至少保证 creative_id 被传进 MMP

#### Step 4. 新增 creative attribution join 层

最小 join 逻辑应明确：

- 同一 `date`
- 同一 `network`
- 同一 `campaign`
- 同一 `ad_id`
- 同一 `creative_id`

如果 Adjust 只能到 ad 或 campaign 级，就只能先做到：

- `Creative -> Ad -> Spend`
- `Ad / Campaign -> Adjust Revenue`

这时 creative revenue 只能做分摊，不是真实闭环。

### 审计判断

当前距离“最小闭环”还差两类东西：

1. 权限和凭证
2. 归因落库模型

不是只差一个 token。

---

## 7. 当前缺少什么

### Meta 当前缺少

- `Access Token`
- `Ad Account ID`
- token scope 验证
- 广告账户访问权限验证
- Business 资产权限验证
- 持久化字段扩展开发

### Google 当前缺少

- `Developer Token`
- `Client ID`
- `Client Secret`
- `Refresh Token`
- `Customer ID`
- 账户访问权限验证
- 可选 `Login Customer ID`
- 持久化字段扩展开发

### 两边共同缺少

- creative attribution 明细落库模型
- 与 Adjust creative/ad 级收入的连接键
- creative revenue join 逻辑

---

## 8. Readiness Matrix

| 项目 | Meta | Google |
| --- | --- | --- |
| 代码里已有 client | YES | YES |
| 当前环境已配置凭证 | NO | NO |
| 当前可真实发起 API 拉取 | NO | NO |
| 当前可拿到素材主键 | PARTIAL | PARTIAL |
| 当前可拿到广告主键 | PARTIAL | NO |
| 当前可拿到 campaign / adset / ad group | PARTIAL | PARTIAL |
| 当前可拿到 spend / click | YES | YES |
| 当前可拿到 install / conversion | PARTIAL | PARTIAL |
| 当前可落到标准化输出 | NO | NO |
| 当前可直接做 creative attribution | NO | NO |

---

## 9. P0 / P1 / P2

### P0 必须补的数据

- Meta `META_ACCESS_TOKEN`
- Meta `META_AD_ACCOUNT_ID`
- Google `DEVELOPER_TOKEN / CLIENT_ID / CLIENT_SECRET / REFRESH_TOKEN / CUSTOMER_ID`
- Meta / Google 广告账户读权限确认
- creative 归因标准化字段：
  - `creative_id`
  - `ad_id`
  - `campaign`
  - `adset_or_ad_group`
  - `spend`
  - `clicks`
  - `installs_or_conversions`
- Adjust 侧可用于 join 的创意或广告维度键

### P1 建议补的数据

- `creative_name`
- `ad_name`
- `asset_name`
- `impressions`
- `ctr`
- `cvr`
- `conversion_value`
- `country`
- `platform`
- `store_type`

### P2 未来扩展的数据

- creative first-frame / hook 标签
- asset format
- placement
- publisher platform
- audience / bid strategy
- 分国家 creative payback
- 分平台 creative payback

---

## 10. 数据补齐路线图（P0 / P1 / P2 / P3）

### P0

- 补全 Meta / Google Ads 凭证，并验证至少能跑通一次素材级拉取
- 扩展 creative performance 数据模型，不再只保留 `CreativeAssetRow`
- 明确 Adjust 侧是否能回传 `creative_id / ad_id / campaign`

### P1

- 新增 `creative_performance` 明细表或 CSV
- 把 Meta / Google 拉取结果落地成统一 schema
- 保留 install / conversion 原始值，不要只折成 CVR

### P2

- 建立 `creative -> ad -> campaign -> adjust revenue` 的 join 层
- 先做 deterministic join，做不到再明确哪些地方只能分摊
- 输出 creative spend / install / revenue / payback 报表

### P3

- 做 creative 维度国家 / 平台 / 渠道拆解
- 做 hook / format / template 的收益归因
- 形成 creative 放量与停投门槛

---

## 最终结论

当前系统不是“已经可以拉素材级数据，只差开关没打开”。

更准确的说法是：

- **Meta / Google 的素材级 client 已经写了**
- **但当前没有任何可用凭证**
- **而且现有标准化模型也装不下创意归因必需字段**

所以当前 readiness 级别应判定为：

**代码预备完成，运行 readiness 未完成，归因 readiness 未完成。**
