# Marketing Data Inventory Audit

审计时间：2026-06-05

审计范围：

- `src/market_ops` 全部核心代码
- 当前环境配置 `.env`
- 当前归一化产物 `output/normalized/*.csv`
- Adjust 本地回退数据 `C:\Users\ethan\Downloads\revenue_breakdown_day_2026-06-04.csv`
- 当前实际读取的飞书 Sheet 结构

审计结论先看：

- 当前主链路不是广告平台 API 直连，而是 `飞书投放表 + 飞书素材表 + Adjust revenue / recovery`
- 当前系统已经支持 `项目ROI / 平台ROI / 渠道ROI`
- 当前系统还不支持 `稳定可信的国家ROI分析`
- 当前系统还没有真正打通 `Creative ID / Ad ID / Campaign / Adset` 到付费回收链路
- 当前素材分析是 `素材资产表分析`，不是 `广告创意归因分析`
- Adjust 明细分解目前依赖本地 CSV 回退，稳定性不够，这是当前最大的 P0 缺口

---

## 1. Adjust 目前抓到了哪些字段

说明：

- 下面的状态按“当前系统真实运行链路”判断，不按未来理论能力判断。
- `已接入` = 已进入当前分析链路
- `部分接入` = 原始接口或某一侧有，但没有稳定落到最终分析链路
- `未接入` = 当前没有进入链路

| 字段 | 状态 | 当前来源 | 说明 |
| --- | --- | --- | --- |
| Date | 已接入 | Adjust daily revenue / breakdown / recovery | `day` 或 CSV `日期/周期` 已实际使用 |
| App | 已接入 | Adjust daily revenue / breakdown / recovery | `app` / `应用名称` 已实际使用 |
| Platform（iOS/Android） | 部分接入 | Adjust breakdown `store_type` + Feishu sheet title | Adjust 日收入落库文件里没有平台列；当前平台分析主要靠 Feishu sheet 名和 breakdown CSV |
| Country | 部分接入 | Adjust breakdown `geo` / CSV `国家/地区` | 架构预留了国家字段，但当前活跃样本里大量是 `Global`；同时广告表里的 `country` 还被混用成 `Android/iOS` |
| Network（Facebook/Google 等） | 部分接入 | Adjust breakdown `network` / CSV `合作伙伴` + Feishu sheet title | 当前可以做渠道层分析，但日收入总表不保留 network |
| Campaign | 未接入 | 无 | 当前 Adjust 客户端和归一化模型都没有 campaign 字段 |
| Adset | 未接入 | 无 | 当前 Adjust 客户端和归一化模型都没有 adset 字段 |
| Creative ID | 部分接入 | 飞书素材表 `asset_id` | 只有素材资产侧有 `asset_id`；Adjust 和广告表现链路没有真正接到创意归因级 |
| Creative Name | 未接入 | 无 | 当前没有单独的 creative name 字段 |
| Ad ID | 未接入 | 无 | `ads_performance.csv` 虽然有 `ad_id` 列，但当前 0 条有效值 |
| Ad Name | 未接入 | 无 | 当前没有 ad name 字段 |
| Cost | 已接入 | Adjust daily revenue / breakdown / recovery + 飞书投放表 | 当前主分析链路已使用 |
| Installs | 部分接入 | Adjust daily revenue 原始字段 + 飞书素材表 | Adjust 原始接口能拉到 installs，但当前 `adjust_revenue.csv` 没有保留 installs 列 |
| Revenue | 已接入 | Adjust daily revenue / breakdown / recovery | `all_revenue` / `总收入(Gross)` 已使用 |
| IAP Revenue | 部分接入 | Adjust breakdown / 回退 CSV | breakdown 层有 `revenue` / `内购收入(Gross)`，但当前最终日收入总表没有单独落 IAP revenue |
| Ad Revenue | 部分接入 | Adjust daily revenue / breakdown / recovery | 原始接口有 `ad_revenue`，但当前最终日收入总表没有单独落 ad revenue |
| ROI 相关字段 | 已接入 | Adjust recovery `roas_dX` + breakdown ROI + 飞书 ROI sheet | 已进入分析链路，尤其是 Actual Recovery / Forecast 体系 |

### 当前真实拉到的 Adjust 原始字段

#### Adjust `fetch_daily_revenue`

当前实际拉取字段：

- `app`
- `app_token`
- `day`
- `cost`
- `all_revenue`
- `revenue`
- `ad_revenue`
- `installs`
- `first_paying_users_d0`
- `all_revenue_total_d0`

#### Adjust `fetch_revenue_breakdown`

设计上拉取字段：

- 维度：`app`, `app_token`, `store_type`, `network`, `geo`, `day`
- 指标：`cost`, `all_revenue`, `revenue`, `ad_revenue`, `daus`, `sessions`

当前现实情况：

- 直接 API 调用目前不稳定，现阶段实际依赖本地回退文件 `revenue_breakdown_day_2026-06-04.csv`
- 本地回退文件字段为：
  - `日期/周期`
  - `应用名称`
  - `商店`
  - `合作伙伴`
  - `国家/地区`
  - `消耗`
  - `内购收入(Gross)`
  - `净内购(Net)`
  - `广告收入`
  - `总收入(Gross)`
  - `净总收入(Net Total)`
  - `DAU`
  - `Sessions`
  - `ROI (Gross)`
  - `净 ROI (Net)`
  - `利润 (Gross)`
  - `净利润 (Net)`

#### Adjust `fetch_recovery_cohort_rows`

当前实际拉取字段：

- 维度：`app`, `app_token`, `day`
- 某些调用会扩到：`app`, `app_token`, `store_type`, `network`, `day`
- 指标：
  - `cost`
  - `roas_d0`, `roas_d1`, `roas_d2`, `roas_d3`, `roas_d4`, `roas_d5`, `roas_d6`, `roas_d7`, `roas_d8`, `roas_d9`, `roas_d13`, `roas_d20`, `roas_d29`, `roas_d59`, `roas_d89`, `roas_d99`, `roas_d119`, `roas_d120`
  - 对应的 `revenue_total_dX`
  - 对应的 `ad_revenue_total_dX`

结论：

- Actual Recovery 相关字段是当前接得最完整的一层
- 但 recovery 层仍然没有 `campaign / adset / ad / creative / geo`

---

## 2. 素材维度是否已经抓到

这是当前系统最大的误区点，结论先说：

- `Creative ID`：只有素材资产侧部分拿到
- `Creative Name`：没有
- `Ad ID`：没有
- `Ad Name`：没有
- 当前系统还没有真正打通“素材 -> 广告 -> 花费 -> 回收”这条归因链

### 当前是否拿到了关键创意字段

| 字段 | 是否拿到 | 说明 |
| --- | --- | --- |
| Creative ID | 部分拿到 | 仅飞书素材表里的 `asset_id`，如 `A10`, `A100`, `A229` |
| Creative Name | 没有 | 没有独立字段，当前只有 `video_path` 或链接 |
| Ad ID | 没有 | `ads_performance.csv` 有列但全部为空 |
| Ad Name | 没有 | 当前没有独立字段 |

### 实际样例

当前 `creative_library.csv` 有素材资产样例：

- `asset_id = A10`
- `asset_id = A100`
- `asset_id = A101`
- `video_path = P4-v2601010-mg-2d-wanfashipin-en-30s-9X16.mp4`
- `game = P04 Witch`
- `country = iOS`
- `channel = All`

当前 `ads_performance.csv` 的付费表现样例里：

- `ad_id = ""`
- `creative_id = ""`

也就是：

- 素材库里有“素材资产编号”
- 但广告表现表里没有真正落地的 `creative_id / ad_id`
- 所以当前并不能做“某个创意真实带来多少花费、多少收入、多少回本”的分析

### 当前系统最多能分析到哪一级

按当前活跃链路，真实可分析层级如下：

- 投放表现：`项目 × 平台/版本标签 × 渠道`
- 素材资产：`asset_id × creative_type × 平台`

不能稳定分析到：

- `Campaign` 级
- `Adset` 级
- `Creative` 归因级
- `Ad` 级

因此当前素材分析本质上是：

- 有素材资产表
- 有素材 CTR / CVR / ROAS / spend
- 但没有和广告投放明细做稳定的一对一归因

结论：

- 当前素材分析是 `Creative Library 分析`
- 不是 `Paid Creative Attribution 分析`

---

## 3. 国家维度是否已经抓到

结论先说：

- 国家字段在架构上存在
- 但当前活跃数据链路里，国家维度还不可信
- 现阶段不建议把它当成正式“国家ROI分析”来源

### 当前支持到的国家字段

#### 在 Adjust breakdown 设计层

有：

- `geo`
- 回退 CSV 里对应 `国家/地区`

#### 在当前归一化广告表

当前 `ads_performance.csv` 的 `country` 实际唯一值是：

- `All`
- `Android`
- `iOS`

这说明当前广告表里的 `country` 不是地理国家，而是被混用了平台标签。

#### 在当前素材表

当前 `creative_library.csv` 的 `country` 实际唯一值是：

- `Android`
- `iOS`

这里同样不是地理国家。

#### 在当前 Adjust breakdown 回退样例

当前样例里可见的是：

- `Global`

说明当前拿到的 breakdown 样本并没有稳定落出真实国家列表。

### 是否支持 `国家 × 平台 × 渠道` 三级分析

当前答案：

- 不支持稳定的三级分析

原因：

- 国家字段不稳定
- 广告表的 `country` 被当成平台用
- breakdown 目前依赖本地 CSV 回退，不是稳定 API
- 当前样本里大量仍是 `Global`

结论：

- `国家分析` 当前应判定为 `未正式接通`

---

## 4. 平台维度是否已经抓到

结论：

- `iOS`：已进入分析链路
- `Android`：已进入分析链路
- 但平台维度目前来自两套来源，语义还没有彻底统一

### 当前平台是怎么来的

来源 1：飞书投放表

- 通过 sheet 标题推断平台
- 例如：
  - `每日数据-FB-IOS` -> `iOS`
  - `每日数据-FB-AND` -> `Android`
  - `每日数据-GG-AND` -> `Android`

来源 2：Adjust breakdown

- `store_type` / 回退 CSV `商店`
- 样例：
  - `app_store`
  - `google_play`

### 当前是否已经进入分析链路

是，已经进入。

当前已支持：

- `项目 × 平台`
- `项目 × 平台 × 渠道`

但要注意：

- 目前平台字段没有独立标准化列统一贯穿所有归一化文件
- 有一部分地方仍通过 `country` 字段承载平台语义

结论：

- 平台 ROI 分析：当前可用
- 平台字段治理：当前还没收口

---

## 5. 渠道维度是否已经抓到

结论：

- 当前已支持：
  - `Facebook`
  - `Google`
- 当前可做渠道 ROI 分析

### 当前渠道是怎么来的

来源 1：飞书投放表

- 通过 sheet 标题推断：
  - `FB` -> `Facebook`
  - `GG` / `GOOGLE` -> `Google`

来源 2：Adjust breakdown

- `network` / 回退 CSV `合作伙伴`
- 样例：
  - `Facebook`
  - `Google Ads`
  - `Organic`
  - `Instagram Installs`

### 当前是否支持未来新增渠道

分两种情况：

#### 情况 A：只做渠道层 ROI / 收入 / 成本分析

如果新渠道能在 Adjust breakdown 或飞书投放表里稳定出现，例如：

- TikTok
- Applovin
- ASA
- Unity
- Mintegral

那么大体上：

- 不需要推翻当前架构
- 需要补 `channel normalization` 映射
- 需要确保数据源里真的能稳定拿到该渠道名字

这一层更像“配置 + 映射治理”。

#### 情况 B：要做渠道下的创意级分析

如果要拿到：

- creative id
- ad id
- ad name
- campaign
- adset

那就不是纯配置了。

当前代码只实现了：

- Meta creative client
- Google Ads creative client

如果未来要加：

- TikTok
- Applovin
- ASA
- Unity
- Mintegral

就需要新增对应 client、字段映射、落库模型和归因逻辑。

结论：

- 只做渠道维度汇总分析：大体不用改架构
- 做渠道下创意归因：需要开发，不是直接配一下就行

---

## 6. 飞书里面有哪些数据被使用

这里区分两类：

- 读取型数据源：当前系统真的在读
- 写回型目标表：当前主要用于写回，不是输入源

### 6.1 当前实际读取的飞书表

| 表名 / Sheet | 关键字段 | 用途 |
| --- | --- | --- |
| `每日数据(总)` | `日期`, `消耗($)`, `新增用户`, `CPI`, `首日ROI`, `总收入`, `1日留存` | 生成项目级广告表现基础数据 |
| `每日数据-FB-AND` | 同上 | 生成 `Android × Facebook` 投放表现 |
| `每日数据-FB-IOS` | 同上 | 生成 `iOS × Facebook` 投放表现 |
| `每日数据-GG-AND` | 同上 | 生成 `Android × Google` 投放表现 |
| `ROI（总）` / `ROI(总)` | `日期`, `首日ROI`, `2日ROI`, `3日ROI`, `7日ROI`, `14日ROI`, `30日ROI`, `2日倍率`, `3日倍率`, `4日倍率`, `5日倍率` | 给项目投放表现补 ROI / recovery 参考 |
| `ROI-FB-AND` | 同上 | 对应 `Android × Facebook` ROI |
| `ROI-FB-IOS` | 同上 | 对应 `iOS × Facebook` ROI |
| `ROI-GG-AND` | 同上 | 对应 `Android × Google` ROI |
| `视频制作需求` | `编号`, `状态`, `项目`, `类型`, `完成视频链接`, `命名格式` | 提供素材元信息，如 `asset_id`, `creative_type`, `video_path`, `duration` |
| `视频-投放数据-AND` | `素材编号`, `素材链接`, `Cost($)`, `CTR`, `Install`, `CPI`, `CVR`, `Roas`, `D0/D3/D7 ROAS`, `D1/D3/D7 留存率` | 生成 Android 素材资产表现 |
| `视频-投放数据-IOS` | `素材编号`, `素材链接`, `Cost($)`, `CTR`, `Install`, `CPI`, `CVR`, `Roas`, `D0/D3/D7 ROAS`, `D1/D3/D7 留存率` | 生成 iOS 素材资产表现 |
| `基础数据-发行-市场部门` | `日期`, `消耗($)`, `新增用户`, `CPI`, `DAU`, `首日ROI`, `新增 arpu` | 公司层总体花费等汇总 |
| `ROI-发行-市场部门` | `日期`, `消耗($)`, `7日回收金额`, `14回收金额`, `21日回收金额`, `首日ROI`, `2日ROI` | 公司层 ROI 汇总 |
| `基础数据-IOS-FB` / `基础数据-GP-FB` 等明细表 | `日期`, `消耗($)` 等 | 公司层分平台分渠道 breakdown |
| `ROI-IOS-FB` / `ROI-GP-FB` 等明细表 | `日期`, `首日ROI` 等 | 公司层分平台分渠道 ROI breakdown |

### 当前读取的飞书来源地址

当前环境里实际配置并使用的飞书来源包括：

- 总览书：`FEISHU_OVERVIEW_URL`
- 默认项目日表：`FEISHU_DAILY_DATA_URL`
- 默认项目 ROI 表：`FEISHU_ROI_URL`
- 项目级覆盖：
  - `P02 Mermaid` -> 固定项目书
  - `P07 Vampire` -> 固定项目书
- 素材书：`FEISHU_CREATIVE_URL`

说明：

- `P02 Mermaid` 和 `P07 Vampire` 使用固定项目映射，不再默认回到共享书

### 6.2 当前没有作为读取源使用，只是写回目标

| 表名 | 当前角色 | 说明 |
| --- | --- | --- |
| `Action Tracker` | 写回目标 | 当前用于把任务结果同步回飞书，不是读侧主数据源 |
| `Meeting Reports` | 写回目标 | 当前用于把生成的报告写回飞书，不是读侧主数据源 |

### 6.3 当前存在但不在活跃分析链路里的文件

| 文件 / 表 | 状态 | 说明 |
| --- | --- | --- |
| `output/normalized/geo_performance.csv` | 基本未使用 | README 有提到，但当前代码主链路几乎没有实际消费它 |

---

## 7. 最终能力评估

| 能力 | 是否支持 |
| --- | --- |
| 项目 ROI 分析 | YES |
| 国家 ROI 分析 | NO |
| 平台 ROI 分析 | YES |
| 渠道 ROI 分析 | YES |
| Campaign 分析 | NO |
| Adset 分析 | NO |
| Creative 分析 | YES |
| 素材回收分析 | NO |
| 素材类型分析 | YES |

补充说明：

- `Creative 分析 = YES` 的含义是：当前能做素材资产表的内容/类型分析
- `素材回收分析 = NO` 的含义是：当前不能把某个创意稳定归因到真实花费与真实回收
- `国家 ROI 分析 = NO` 的原因不是完全没有国家字段，而是当前国家维度不可靠，不能作为正式结论来源

---

## 8. 开发优先级

### P0

#### 1. 打通稳定的 Adjust breakdown 明细链路

当前问题：

- breakdown API 当前不稳定
- 实际依赖本地下载 CSV 回退
- 这会直接影响平台、渠道、国家层分析的可信度

目标：

- 稳定落库 `date / app / store / network / geo / cost / iap revenue / ad revenue / total revenue / ROI`

为什么是 P0：

- 这是公司 / 项目 / 平台 / 渠道 / 国家所有经营分析的底盘

#### 2. 修正 `country` 字段语义污染

当前问题：

- `ads_performance.csv.country` 实际装的是 `All / Android / iOS`
- `creative_library.csv.country` 也被混成平台标签

目标：

- 单独拆出 `platform`
- `country` 只存真实国家

为什么是 P0：

- 现在这会直接误导“国家分析”结论

### P1

#### 3. 打通素材归因主键

至少要补齐：

- `creative_id`
- `creative_name`
- `ad_id`
- `ad_name`
- `campaign`
- `adset`

为什么是 P1：

- 这是从“素材表分析”升级成“创意归因分析”的关键一步
- 也是以后接 Facebook / Google 创意真实回收分析的前提

### P2

#### 4. 建立统一维度模型

建议统一成以下主键：

- `date`
- `game`
- `platform`
- `country`
- `channel`
- `campaign`
- `adset`
- `ad_id`
- `creative_id`

为什么是 P2：

- 没有统一主键，后面越接越乱
- 但它依赖 P0 / P1 先把源头字段补齐

#### 5. 渠道标准化配置

目标：

- 统一 `Facebook / Google Ads / Organic / ASA / TikTok / Applovin / Unity / Mintegral`
- 建立 channel alias 映射

为什么是 P2：

- 未来扩渠道会频繁用到

### P3

#### 6. 清理未用资产和文档化数据契约

包括：

- `geo_performance.csv` 是否继续保留
- 哪些飞书表是输入源，哪些只是写回目标
- 哪些字段是“理论能力”，哪些是“当前活跃能力”

为什么是 P3：

- 这不会直接提升分析能力
- 但能减少后续误解和维护成本

---

## 最终一句话结论

当前系统已经具备“项目 / 平台 / 渠道”的经营分析底座，但还没有具备“国家可信分析”和“创意归因分析”的底座。最值得优先补的是：先把 Adjust breakdown 稳定落地，再把 `platform / country / creative / ad` 这些关键维度真正接通。
