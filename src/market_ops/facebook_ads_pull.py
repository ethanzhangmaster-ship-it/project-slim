"""完整拉取P02/P04/P07所有在投账户数据 - 区分图片/视频素材

升级点:
1. 新增P07账户 736136435514410 (CMCM_项目07_20251126_AND)
2. adcreatives 带上 video_id 字段,准确区分图片/视频
3. 解析 platform (Android/iOS) 从 account_name 或 ad_name
4. 保留 creative_id 用于Facebook后台查找
"""
import requests
import json
import os
import time
import re
import shutil
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# 优先用FB_TOKEN,回退到META_ACCESS_TOKEN
TOKEN = os.environ.get('FB_TOKEN', '') or os.environ.get('META_ACCESS_TOKEN', '')
BASE = f"https://graph.facebook.com/{os.environ.get('META_API_VERSION', 'v19.0')}"

# P02/P04/P07 所有活跃且有花费的账户 (排除MergeLand - 非P2/P4/P7项目)
ACTIVE_ACCOUNTS = [
    # P04 - 5个账户
    {"id": "1959429141294402", "name": "GAMEGZZ_CMCM_04_4_AND", "project": "P04", "platform": "Android"},
    {"id": "1379499207181514", "name": "GAMEGZZ_Tec_Do_04_260312_IOS_2", "project": "P04", "platform": "iOS"},
    {"id": "1423660739468966", "name": "GAMEGZZ_Tec_Do_04_260115_IOS_1", "project": "P04", "platform": "iOS"},
    {"id": "1455525822955003", "name": "GAMEGZZ_Tec_Do_04_260115_AND_1", "project": "P04", "platform": "Android"},
    {"id": "1628583695016910", "name": "GAMEGZZ_Tec_Do_04_260312_IOS_3", "project": "P04", "platform": "iOS"},
    # P02 - 1个账户
    {"id": "907214188838822", "name": "GAMEGZZ_Tec_Do_02_260227_IOS_2", "project": "P02", "platform": "iOS"},
    # P07 - 2个账户 (新增 736136435514410)
    {"id": "25912976875001336", "name": "GAMEGZZ_Tec_Do_07_260205_AND_1", "project": "P07", "platform": "Android"},
    {"id": "736136435514410", "name": "GAMEGZZ_CMCM_项目07_20251126_AND", "project": "P07", "platform": "Android"},
]

OUTPUT_DIR = "output/facebook_ads_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def fb_get_all(act_id, path, fields=None, limit=100, extra_params=None):
    """用act_前缀获取所有数据(含分页)"""
    all_data = []
    url = f"{BASE}/act_{act_id}/{path}"
    params = {'access_token': TOKEN, 'limit': limit}
    if fields:
        params['fields'] = fields
    if extra_params:
        params.update(extra_params)

    page = 0
    while url:
        try:
            r = requests.get(url, params=params if page == 0 else None, timeout=60)
            data = r.json()
        except Exception as e:
            print(f"    ⚠ 请求异常: {e}")
            break

        if 'data' not in data:
            if 'error' in data:
                return all_data, data['error']
            return all_data, data
        all_data.extend(data['data'])
        paging = data.get('paging', {})
        next_url = paging.get('next')
        url = next_url if next_url else None
        params = None
        page += 1

    return all_data, None


def detect_platform(ad_name, acc_platform):
    """从ad_name或账户平台推断: 优先ad_name里的And/IOS标记"""
    # ad_name 格式: P4-And-T1-A413-0609 或 P4-IOS-T1-A413-0609
    m = re.search(r'-(And|IOS|AOS|AND)-', ad_name, re.IGNORECASE)
    if m:
        tag = m.group(1).upper()
        if tag in ('AND', 'AOS'):
            return 'Android'
        if tag == 'IOS':
            return 'iOS'
    return acc_platform


def extract_perf(insights):
    """提取性能指标"""
    results = []
    for ins in insights:
        spend = float(ins.get('spend', 0))
        impressions = int(ins.get('impressions', 0))
        clicks = int(ins.get('clicks', 0))
        ctr = float(ins.get('ctr', 0))
        cpc = float(ins.get('cpc', 0))
        cpm = float(ins.get('cpm', 0))

        installs = 0
        for act in ins.get('actions', []):
            if 'install' in act.get('action_type', ''):
                installs += int(float(act.get('value', 0)))

        ipm = round(installs / impressions * 1000, 2) if impressions > 0 else 0

        cpi = 0
        for cost in ins.get('cost_per_action_type', []):
            if 'install' in cost.get('action_type', ''):
                cpi = float(cost.get('value', 0))

        roas = 0
        roas_list = ins.get('purchase_roas', [])
        if roas_list:
            roas = float(roas_list[0].get('value', 0))

        results.append({
            'ad_name': ins.get('ad_name', ''),
            'ad_id': ins.get('ad_id', ''),
            'campaign_name': ins.get('campaign_name', ''),
            'adset_name': ins.get('adset_name', ''),
            'spend': round(spend, 2),
            'impressions': impressions,
            'clicks': clicks,
            'ctr': round(ctr, 2),
            'cpc': round(cpc, 4),
            'cpm': round(cpm, 2),
            'installs': installs,
            'ipm': ipm,
            'cpi': round(cpi, 2),
            'roas': round(roas, 2),
            'date_start': ins.get('date_start', ''),
            'date_stop': ins.get('date_stop', ''),
        })
    return results


def enrich_ad_with_media_type(ad, acc_platform):
    """给ad添加 media_type, creative_id, platform 字段"""
    creative_data = ad.get('adcreatives', {}).get('data', [])
    if not creative_data:
        ad['creative_id'] = ''
        ad['media_type'] = 'unknown'
        ad['platform'] = acc_platform
        return ad

    c = creative_data[0]
    ad['creative_id'] = c.get('id', '')

    # 区分图片/视频: video_id存在=视频; 否则看image_url
    if c.get('video_id'):
        ad['media_type'] = 'video'
    elif c.get('image_url'):
        ad['media_type'] = 'image'
    elif c.get('thumbnail_url'):
        # 没有video_id但有thumbnail_url - 检查URL特征
        url = c.get('thumbnail_url', '')
        if 'p64x64' in url or '/v/t15.' in url:
            ad['media_type'] = 'video'  # 视频缩略图
        else:
            ad['media_type'] = 'image'
    else:
        ad['media_type'] = 'unknown'

    ad['platform'] = detect_platform(ad.get('name', ''), acc_platform)
    return ad


def main():
    # 安全检查: token必须存在
    if not TOKEN:
        print("ERROR: 没有找到token (FB_TOKEN 或 META_ACCESS_TOKEN)")
        print("请检查.env文件是否配置了META_ACCESS_TOKEN")
        return

    print(f"Token长度: {len(TOKEN)} | API: {BASE}")

    # 备份现有summary.json
    summary_path = f"{OUTPUT_DIR}/summary.json"
    if os.path.exists(summary_path) and os.path.getsize(summary_path) > 10000:
        backup = f"{OUTPUT_DIR}/summary_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        shutil.copy2(summary_path, backup)
        print(f"已备份现有summary.json → {backup}")

    all_results = []

    for acc in ACTIVE_ACCOUNTS:
        acc_id = acc['id']
        acc_name = acc['name']
        project = acc['project']
        acc_platform = acc['platform']

        print(f"\n{'='*80}")
        print(f"账户: {acc_name} | {project} | {acc_platform} | ID: {acc_id}")
        print(f"{'='*80}")

        result = {
            "account_id": acc_id,
            "account_name": acc_name,
            "project": project,
            "platform": acc_platform,
            "campaigns": [],
            "ads": [],
            "insights_30d": [],
            "insights_7d": [],
            "error": None
        }

        # 1. 广告系列
        campaigns, err = fb_get_all(acc_id, 'campaigns', fields='id,name,status,objective,daily_budget')
        print(f"广告系列: {len(campaigns)} 个")
        result['campaigns'] = campaigns

        # 2. 广告素材 - 带video_id区分图片/视频
        ads, err = fb_get_all(acc_id, 'ads',
            fields='id,name,status,adcreatives{id,image_url,thumbnail_url,video_id,body,title,call_to_action_type,object_url}')
        print(f"广告: {len(ads)} 个")

        # 统计图片/视频分布
        img_count = 0
        vid_count = 0
        for ad in ads:
            ad = enrich_ad_with_media_type(ad, acc_platform)
            if ad['media_type'] == 'image':
                img_count += 1
            elif ad['media_type'] == 'video':
                vid_count += 1
        print(f"  图片素材: {img_count} | 视频素材: {vid_count}")

        # 显示前5个
        for ad in ads[:5]:
            c = ad.get('adcreatives', {}).get('data', [{}])[0] if ad.get('adcreatives', {}).get('data') else {}
            print(f"  - {ad.get('name', '')[:35]:<35} | {ad['media_type']:<6} | cid={ad['creative_id']:<18} | {ad.get('status','')}")
        result['ads'] = ads

        # 3. 性能数据 - 30天 (带ad_id)
        insights_30d, err = fb_get_all(acc_id, 'insights',
            fields='campaign_name,ad_name,ad_id,adset_name,spend,impressions,clicks,ctr,cpc,cpm,actions,cost_per_action_type,purchase_roas',
            extra_params={'level': 'ad', 'date_preset': 'last_30d'})
        perf_30d = extract_perf(insights_30d)
        total_spend = sum(p['spend'] for p in perf_30d)
        total_installs = sum(p['installs'] for p in perf_30d)
        print(f"性能(30天): {len(perf_30d)} 条 | 花费: ${total_spend:,.2f} | 安装: {total_installs}")
        result['insights_30d'] = perf_30d

        # 4. 性能数据 - 7天
        insights_7d, err = fb_get_all(acc_id, 'insights',
            fields='campaign_name,ad_name,ad_id,adset_name,spend,impressions,clicks,ctr,cpc,cpm,actions,cost_per_action_type,purchase_roas',
            extra_params={'level': 'ad', 'date_preset': 'last_7d'})
        perf_7d = extract_perf(insights_7d)
        print(f"性能(7天): {len(perf_7d)} 条")
        result['insights_7d'] = perf_7d

        # 保存单个账户
        safe_name = acc_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
        with open(f"{OUTPUT_DIR}/{safe_name}.json", 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        all_results.append(result)
        time.sleep(1)

    # === 汇总 ===
    print(f"\n{'='*80}")
    print(f"=== 汇总 ===")
    print(f"{'='*80}")

    total_campaigns = sum(len(r['campaigns']) for r in all_results)
    total_ads = sum(len(r['ads']) for r in all_results)
    total_insights = sum(len(r['insights_30d']) for r in all_results)
    total_spend_30d = sum(p['spend'] for r in all_results for p in r['insights_30d'])
    total_installs = sum(p['installs'] for r in all_results for p in r['insights_30d'])

    # 按项目和平台统计
    by_project = {}
    by_media = {'image': 0, 'video': 0, 'unknown': 0}
    for r in all_results:
        proj = r['project']
        plat = r['platform']
        key = f"{proj}_{plat}"
        by_project.setdefault(key, {'accounts': 0, 'ads': 0, 'spend': 0, 'installs': 0, 'insights': 0})
        by_project[key]['accounts'] += 1
        by_project[key]['ads'] += len(r['ads'])
        by_project[key]['spend'] += sum(p['spend'] for p in r['insights_30d'])
        by_project[key]['installs'] += sum(p['installs'] for p in r['insights_30d'])
        by_project[key]['insights'] += len(r['insights_30d'])
        for ad in r['ads']:
            by_media[ad.get('media_type', 'unknown')] += 1

    print(f"\n账户数: {len(all_results)}")
    print(f"广告系列: {total_campaigns}")
    print(f"广告数: {total_ads} (图片: {by_media['image']} | 视频: {by_media['video']} | 未知: {by_media['unknown']})")
    print(f"性能记录(30天): {total_insights}")
    print(f"30天总花费: ${total_spend_30d:,.2f}")
    print(f"30天总安装: {total_installs}")
    if total_installs > 0:
        print(f"平均CPI: ${total_spend_30d/total_installs:.2f}")

    print(f"\n=== 按项目_平台 ===")
    for key, v in sorted(by_project.items()):
        print(f"  {key:<15} 账户={v['accounts']} ads={v['ads']:<5} ins={v['insights']:<5} "
              f"spend=${v['spend']:>10,.2f} installs={v['installs']}")

    # 保存
    with open(f"{OUTPUT_DIR}/summary.json", 'w', encoding='utf-8') as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total_accounts": len(all_results),
            "total_campaigns": total_campaigns,
            "total_ads": total_ads,
            "total_insights_30d": total_insights,
            "total_spend_30d": round(total_spend_30d, 2),
            "total_installs_30d": total_installs,
            "avg_cpi": round(total_spend_30d / total_installs, 2) if total_installs > 0 else 0,
            "media_type_distribution": by_media,
            "by_project_platform": by_project,
            "accounts": all_results
        }, f, indent=2, ensure_ascii=False)

    print(f"\n已保存: {OUTPUT_DIR}/summary.json")


if __name__ == "__main__":
    main()
