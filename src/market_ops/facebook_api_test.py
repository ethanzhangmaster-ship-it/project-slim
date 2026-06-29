"""Facebook Graph API 数据拉取"""
import requests
import json
import os
import sys

# 从环境变量获取token
TOKEN = os.environ.get('FB_TOKEN', '')
BASE = 'https://graph.facebook.com/v19.0'

if not TOKEN:
    print("ERROR: 未设置FB_TOKEN环境变量")
    sys.exit(1)

def fb_get(path, fields=None, limit=10, extra_params=None):
    """封装Facebook Graph API GET请求"""
    params = {'access_token': TOKEN, 'limit': limit}
    if fields:
        params['fields'] = fields
    if extra_params:
        params.update(extra_params)
    r = requests.get(f"{BASE}/{path}", params=params)
    return r.json()

def main():
    # 1. 验证Token
    print("=== 1. 验证Token ===")
    data = fb_get('me')
    print(f"  用户: {data.get('name', 'N/A')}")
    print(f"  ID: {data.get('id', 'N/A')}")

    # 2. 获取广告账户
    print("\n=== 2. 获取广告账户 ===")
    data = fb_get('me/adaccounts', fields='id,name,account_id,account_status,currency,amount_spent,spend_cap')
    accounts = data.get('data', [])
    print(f"  找到 {len(accounts)} 个广告账户:")
    for acc in accounts:
        status_map = {1: 'ACTIVE', 2: 'DISABLED', 3: 'UNSETTLED', 7: 'PENDING_RISK_REVIEW'}
        status = status_map.get(acc.get('account_status'), acc.get('account_status', ''))
        print(f"    - {acc.get('name', '')} | account_id={acc.get('account_id', '')} | {status} | spent={acc.get('amount_spent', '')} {acc.get('currency', '')}")

    if not accounts:
        print("  (无广告账户)")
        return

    # 3. 对每个账户获取广告系列
    for acc in accounts[:3]:  # 最多查3个账户
        acc_id = acc['id']
        acc_name = acc.get('name', '')
        print(f"\n=== 3. 广告系列 ({acc_name}) ===")
        data = fb_get(f"{acc_id}/campaigns", fields='id,name,status,objective,daily_budget,lifetime_budget,buying_type')
        campaigns = data.get('data', [])
        print(f"  找到 {len(campaigns)} 个广告系列:")
        for camp in campaigns[:5]:
            print(f"    - {camp.get('name', '')} | status={camp.get('status', '')} | objective={camp.get('objective', '')}")

        # 4. 获取广告组
        print(f"\n=== 4. 广告组 ({acc_name}) ===")
        data = fb_get(f"{acc_id}/adsets", fields='id,name,status,daily_budget,lifetime_budget,targeting')
        adsets = data.get('data', [])
        print(f"  找到 {len(adsets)} 个广告组:")
        for aset in adsets[:5]:
            print(f"    - {aset.get('name', '')} | status={aset.get('status', '')}")

        # 5. 获取广告素材
        print(f"\n=== 5. 广告素材 ({acc_name}) ===")
        data = fb_get(f"{acc_id}/ads", fields='id,name,status,adcreatives{image_url,thumbnail_url,body,title,link,calls_to_action}', limit=25)
        ads = data.get('data', [])
        print(f"  找到 {len(ads)} 个广告:")
        for ad in ads[:10]:
            print(f"    - {ad.get('name', '')} | status={ad.get('status', '')}")
            creative = ad.get('adcreatives', {}).get('data', [])
            if creative:
                c = creative[0]
                print(f"      标题: {c.get('title', 'N/A')}")
                print(f"      正文: {c.get('body', 'N/A')[:80]}")
                print(f"      图片: {c.get('image_url', c.get('thumbnail_url', 'N/A'))}")

        # 6. 获取广告洞察数据(性能)
        print(f"\n=== 6. 性能数据 ({acc_name}) ===")
        data = fb_get(f"{acc_id}/insights", fields='campaign_name,ad_name,spend,impressions,clicks,ctr,cpc,cpm,actions,action_values', extra_params={'level': 'ad', 'date_preset': 'last_30d'})
        insights = data.get('data', [])
        print(f"  找到 {len(insights)} 条性能记录:")
        for ins in insights[:10]:
            spend = ins.get('spend', '0')
            impr = ins.get('impressions', '0')
            clicks = ins.get('clicks', '0')
            ctr = ins.get('ctr', '0')
            cpc = ins.get('cpc', '0')
            print(f"    - {ins.get('ad_name', '')} | spend={spend} | impr={impr} | clicks={clicks} | ctr={ctr}% | cpc={cpc}")

            # 提取安装数
            actions = ins.get('actions', [])
            for act in actions:
                if act.get('action_type') in ('mobile_app_install', 'app_install', 'offsite_conversion.fb_app_install'):
                    print(f"      安装: {act.get('value', '0')}")

    print("\n=== 完成 ===")

if __name__ == "__main__":
    main()