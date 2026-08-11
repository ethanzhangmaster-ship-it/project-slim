# Facebook 广告创建常见问题与解决方案

## 背景
本文档记录在新广告账户创建广告时可能遇到的各类问题及对应解决方案，避免重复踩坑。

---

## 问题清单

### 1. APP_INSTALLS 平台不匹配 (Mobile Targeting Mismatch)

**错误码**: `error_subcode: 1487678`

**错误信息**:
```
The app you're trying to create an ad for is on a different operating system than targeting settings for this ad set.
```

**原因**:
- App ID 在 Facebook 后台只配置了 iOS 平台，但尝试投放 Android 广告
- 或者反之（只配置了 Android，尝试投放 iOS）

**解决方案**:

**方案 A - 修复平台配置（推荐用于正式投放）**
- 在 Facebook 开发者后台为 App ID 同时配置 iOS 和 Android 平台
- 配置完成后等待同步（可能需要 10-30 分钟）

**方案 B - 使用 OUTCOME_TRAFFIC 绕过（快速验证方案）**
- 放弃 `OUTCOME_APP_PROMOTION` + `APP_INSTALLS` 组合
- 改用 `OUTCOME_TRAFFIC` + `LINK_CLICKS` 目标
- 直接通过广告链接跳转到应用商店
- 优点：无需配置 App ID 平台，快速创建广告
- 缺点：无法追踪安装归因，优化目标不同

**方案 C - 强制指定设备平台**
- 在 targeting 中添加 `device_platforms: ["mobile"]` 或 `user_os` 限制
- 但如果 App 本身没配置对应平台，此方法无效

---

### 2. LINK_CLICKS 目标已弃用

**错误码**: `code: 100`

**错误信息**:
```
Objective LINK_CLICKS is invalid. Use one of: OUTCOME_LEADS, OUTCOME_SALES, OUTCOME_ENGAGEMENT, OUTCOME_AWARENESS, OUTCOME_TRAFFIC, OUTCOME_APP_PROMOTION.
```

**原因**:
- Facebook Marketing API 已弃用旧版 `LINK_CLICKS` 目标
- 新 API 使用 `OUTCOME_*` 系列目标

**解决方案**:
- Campaign 目标使用 `OUTCOME_TRAFFIC`（替代旧的 LINK_CLICKS）
- Adset 优化目标仍可使用 `LINK_CLICKS`

```python
# Campaign 层级
"objective": "OUTCOME_TRAFFIC"

# Adset 层级
"optimization_goal": "LINK_CLICKS"
```

---

### 3. 新账户需要广告主信息 (DSA Beneficiary)

**错误码**: `error_subcode: 3858081`

**错误信息**:
```
未指明广告主 - 请输入广告推广的个人或组织。
```

**原因**:
- 新广告账户首次创建广告时需要配置数字服务法（DSA）相关信息
- 欧盟地区要求披露广告主和付费方

**解决方案**:
在 Campaign 和 Adset 层级添加 `dsa_beneficiary` 参数：

```python
"dsa_beneficiary": json.dumps({
    "name": "Merge Witches",
    "category": "APP",
})
```

---

### 4. 新账户需要付费方信息 (DSA Payor)

**错误码**: `error_subcode: 3858079`

**错误信息**:
```
未指明付费方 - 请输入为这个广告组的广告付费的个人或组织。
```

**原因**:
- 与 DSA Beneficiary 类似，新账户还需要付费方信息

**解决方案**:
在 Campaign 和 Adset 层级添加 `dsa_payor` 参数：

```python
"dsa_payor": json.dumps({
    "name": "Merge Witches",
    "category": "APP",
})
```

**注意**: `dsa_beneficiary` 和 `dsa_payor` 需要同时在 Campaign 和 Adset 两个层级都设置。

---

### 5. Page 照片上传需要 Page Token

**错误码**: `code: 200`

**错误信息**:
```
Unpublished posts must be posted to a page as the page itself.
```

**原因**:
- 使用 User Token 上传未发布（published=false）的照片到 Page 时会失败
- 必须使用 Page 自己的 Token

**解决方案**:
1. 通过 User Token 获取 Page Token：

```python
r = requests.get(
    f"{BV}/me/accounts",
    params={"access_token": USER_TOKEN},
)
pages = r.json()["data"]
# 找到对应 Page 的 access_token
page_token = [p for p in pages if p["id"] == page_id][0]["access_token"]
```

2. 使用 Page Token 上传照片：

```python
r_upload = requests.post(
    f"{BV}/{page_id}/photos",
    data={
        "access_token": PAGE_TOKEN,  # 使用 Page Token
        "published": "false",
    },
    files={"source": img_file},
)
image_hash = r_upload.json()["image_hash"]
```

---

### 6. 广告账户图片库上传失败

**错误码**: `error_subcode: 33`

**错误信息**:
```
Unsupported post request. Object with ID 'act_XXX' does not exist, cannot be loaded due to missing permissions, or does not support this operation.
```

**原因**:
- 直接向 `act_{account_id}/images` 上传图片可能因权限问题失败
- 特别是新账户或权限配置不完整时

**解决方案**:
- 改用 Page 照片上传（见问题 5）
- 获取 image_hash 后在 creative 中使用
- 功能效果相同，都是获取图片哈希用于创建创意

---

### 7. App 开发模式限制

**错误码**: `error_subcode: 1885183`

**错误信息**:
- App 处于开发模式，无法创建正式广告

**解决方案**:
- 确认 App 是否为 Live 模式
- 开发模式 App 只能用于测试广告
- 正式投放请使用已上线（Live）的 App ID

---

### 8. 账户身份验证限制

**错误码**: `error_subcode: 3858385`

**错误信息**:
```
账户身份验证相关错误，阻止广告创建或修改
```

**原因**:
- Facebook 安全机制，新账户或异常操作触发验证
- 需要完成企业验证或身份验证

**解决方案**:
1. 登录 Facebook Business Manager
2. 进入账户设置，完成身份验证
3. 或更换已完成验证的广告账户

---

### 9. CTA 与目标不匹配（应用链接不兼容）

**错误信息**:
```
创意行动号召不兼容应用广告: 应用广告必须包含有效的行动号召 (CTA) 按钮。
请选择有效的行动号召 (CTA) 按钮。
```

```
指定创意需要更换目标: 应用链接只适用于应用安装量目标。
请移除应用链接，或将营销目标改为"应用安装量"。
```

**原因**:
- 使用 `OUTCOME_TRAFFIC` 目标（流量目标）
- 但 Creative 中使用了 `INSTALL_MOBILE_APP`、`USE_APP`、`DOWNLOAD` 等应用类 CTA
- 或链接是应用商店链接，Facebook 识别为应用广告
- 两者不匹配导致投放错误

**解决方案**:

**方案 A - 使用 APP_INSTALLS 目标（推荐用于正式投放）**
- 如果 App 平台配置完整，直接用 `OUTCOME_APP_PROMOTION` + `APP_INSTALLS`
- 这样可以使用应用类 CTA，也能追踪安装归因

**方案 B - 使用普通 CTA（TRAFFIC 目标下可用）**
- 继续使用 `OUTCOME_TRAFFIC` 目标
- CTA 改用 `LEARN_MORE`、`SHOP_NOW` 等非应用类 CTA
- 链接仍可指向应用商店，但 CTA 不能是应用安装类

```python
# 正确的 TRAFFIC + LEARN_MORE 组合
"object_story_spec": {
    "page_id": page_id,
    "link_data": {
        "image_hash": image_hash,
        "link": store_url,
        "message": "Play Now!",
        "call_to_action": {
            "type": "LEARN_MORE",  # 不用 INSTALL_MOBILE_APP
            "value": {"link": store_url}
        },
    },
}
```

**TRAFFIC 目标下可用的 CTA 类型**:
- `LEARN_MORE`（了解更多）
- `SHOP_NOW`（立即购物）
- `SIGN_UP`（注册）
- `GET_OFFER`（获取优惠）

**APP_INSTALLS 目标下才可用的 CTA 类型**:
- `INSTALL_MOBILE_APP`（安装应用）
- `USE_APP`（使用应用）
- `DOWNLOAD`（下载）

---

### 10. 图片上传获取 image_hash 的正确方式

**问题**: Page 照片上传接口（`/{page_id}/photos`）不返回 `image_hash` 字段，导致无法正确创建 Creative。

**现象**:
- 使用 Page Token 上传照片成功，返回 photo_id
- 但响应中没有 `image_hash` 字段
- 直接用空 hash 创建 Creative，会导致所有广告复用同一张默认图

**解决方案**: 使用广告账户图片库接口 `adimages` 上传

```python
# 正确方式：act_{account_id}/adimages
with open(image_path, 'rb') as img_file:
    r = requests.post(
        f"{BV}/act_{ad_account_id}/adimages",
        data={"access_token": USER_TOKEN, "filename": "image.png"},
        files={"source": img_file},
        timeout=60,
    )
d = r.json()
# 返回格式: {"images": {"image.png": {"hash": "xxx", "url": "xxx", ...}}}
image_hash = list(d["images"].values())[0]["hash"]
```

**优点**:
- 直接返回 image_hash
- 图片在广告账户图片库中管理
- 不需要 Page Token

---

## 新账户广告创建完整流程（避坑版）

适用于：新广告账户 + App 平台配置不完整 的场景

### 步骤 1: 使用 OUTCOME_TRAFFIC 目标

```python
# 创建 Campaign
r_camp = requests.post(
    f"{BV}/act_{ad_account_id}/campaigns",
    data={
        "access_token": USER_TOKEN,
        "name": "Campaign Name",
        "objective": "OUTCOME_TRAFFIC",
        "status": "PAUSED",
        "is_adset_budget_sharing_enabled": True,
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "special_ad_categories": json.dumps([]),
        "dsa_beneficiary": json.dumps({"name": "App Name", "category": "APP"}),
        "dsa_payor": json.dumps({"name": "App Name", "category": "APP"}),
    },
)
```

### 步骤 2: 创建 Adset

```python
r_aset = requests.post(
    f"{BV}/act_{ad_account_id}/adsets",
    data={
        "access_token": USER_TOKEN,
        "name": "Adset Name",
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "optimization_goal": "LINK_CLICKS",
        "billing_event": "IMPRESSIONS",
        "daily_budget": 2000,
        "targeting": json.dumps({
            "geo_locations": {"countries": ["US", "GB", "DE", "FR", "CA", "AU"]},
            "device_platforms": ["mobile"],
        }),
        "dsa_beneficiary": json.dumps({"name": "App Name", "category": "APP"}),
        "dsa_payor": json.dumps({"name": "App Name", "category": "APP"}),
    },
)
```

### 步骤 3: 上传图片获取 image_hash（推荐用 adimages 接口）

```python
# 推荐方式：广告账户图片库，直接返回 image_hash
with open(image_path, 'rb') as img_file:
    r_upload = requests.post(
        f"{BV}/act_{ad_account_id}/adimages",
        data={"access_token": USER_TOKEN, "filename": "image.png"},
        files={"source": img_file},
        timeout=60,
    )
d_upload = r_upload.json()
image_hash = list(d_upload["images"].values())[0]["hash"]
```

### 步骤 4: 创建 Creative 和 Ad（注意 CTA 类型与目标匹配）

```python
# 创建 Creative (OUTCOME_TRAFFIC 目标下用 LEARN_MORE CTA)
r_cre = requests.post(
    f"{BV}/act_{ad_account_id}/adcreatives",
    data={
        "access_token": USER_TOKEN,
        "name": "Creative Name",
        "object_story_spec": json.dumps({
            "page_id": page_id,
            "link_data": {
                "image_hash": image_hash,
                "link": store_url,
                "message": "Play Now!",
                "call_to_action": {
                    "type": "LEARN_MORE",  # TRAFFIC 目标用普通 CTA
                    "value": {"link": store_url}
                },
            },
        }),
    },
)
creative_id = r_cre.json()["id"]

# 创建 Ad
r_ad = requests.post(
    f"{BV}/act_{ad_account_id}/ads",
    data={
        "access_token": USER_TOKEN,
        "name": "Ad Name",
        "adset_id": adset_id,
        "creative": json.dumps({"creative_id": creative_id}),
        "status": "PAUSED",
    },
)
```

---

## 完整参考脚本

脚本位置: `scripts/_create_p04_with_selfcheck.py`

该脚本实现了完整的 OUTCOME_TRAFFIC + LINK_CLICKS + LEARN_MORE CTA 广告创建流程，包含所有避坑点和自检步骤。

---

## 更新记录

- **2026-07-01**: 初始版本，记录新账户创建 P04 Witch 广告时遇到的 8 个问题及解决方案
- **2026-07-01**: 补充问题 9（CTA 与目标不匹配）和问题 10（image_hash 正确获取方式），更新完整流程步骤
