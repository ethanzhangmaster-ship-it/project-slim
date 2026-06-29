# Creative Attribution Data Roadmap

基于当前代码、当前配置、当前依赖、当前 API client 设计整理。

不含飞书侧内容。

---

## P0

### 必须补的凭证与权限

- Meta `META_ACCESS_TOKEN`
- Meta `META_AD_ACCOUNT_ID`
- Meta 广告账户读权限确认
- Meta Business 资产访问权限确认
- Google `GOOGLE_ADS_DEVELOPER_TOKEN`
- Google `GOOGLE_ADS_CLIENT_ID`
- Google `GOOGLE_ADS_CLIENT_SECRET`
- Google `GOOGLE_ADS_REFRESH_TOKEN`
- Google `GOOGLE_ADS_CUSTOMER_ID`
- Google 账户访问权限确认
- Google `GOOGLE_ADS_LOGIN_CUSTOMER_ID`（如走 MCC）

### 必须补的数据字段

- `creative_id`
- `creative_name`
- `ad_id`
- `ad_name`
- `campaign`
- `adset_or_ad_group`
- `date`
- `network`
- `platform`
- `spend`
- `clicks`
- `installs_or_conversions`

### 必须补的归因前提

- Adjust 侧确认是否能回传：
  - `creative_id`
  - `ad_id`
  - `campaign`
  - `network`

---

## P1

### 建议补的明细表

- 新增 `creative_performance.csv` 或等价表

建议字段：

- `date`
- `source_platform`
- `network`
- `campaign`
- `adset_or_ad_group`
- `ad_id`
- `ad_name`
- `creative_id`
- `creative_name`
- `asset_name`
- `spend`
- `impressions`
- `clicks`
- `installs`
- `conversions`
- `conversion_value`

### 建议补的标准化工作

- Meta / Google creative 字段统一 schema
- `Facebook / Google Ads` 命名统一
- install 与 conversion 分开保留
- 不再只保留 CVR / ROAS 聚合值

---

## P2

### 建议补的 join 层

- `creative -> ad -> campaign -> adjust revenue` join 逻辑
- 优先 deterministic join
- 做不到 deterministic 时，明确哪些地方只能分摊

### 建议补的输出能力

- creative spend
- creative install
- creative revenue
- creative ROI
- creative payback

---

## P3

### 未来扩展

- creative × country
- creative × platform
- creative × channel
- hook / format / template 收益归因
- creative 放量门槛
- creative 停投门槛

---

## 当前状态一句话

当前处于：

- `client 已存在`
- `凭证未配置`
- `字段未落全`
- `creative attribution join 未建立`
