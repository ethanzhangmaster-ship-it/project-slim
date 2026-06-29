"""拉取所有Facebook广告账户"""
import requests
import json
import os

TOKEN = os.environ.get('FB_TOKEN', '')
BASE = 'https://graph.facebook.com/v19.0'

def get_all_accounts():
    """获取所有广告账户（含分页）"""
    all_accounts = []
    url = f"{BASE}/me/adaccounts"
    params = {
        'access_token': TOKEN,
        'fields': 'id,name,account_id,account_status,currency,amount_spent,spend_cap,timezone_name',
        'limit': 100
    }
    
    page = 1
    while url:
        r = requests.get(url, params=params if page == 1 else None)
        data = r.json()
        
        if 'data' not in data:
            print(f"错误: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
            break
            
        all_accounts.extend(data['data'])
        print(f"第{page}页: 获取到 {len(data['data'])} 个账户，累计 {len(all_accounts)} 个")
        
        # 检查是否有下一页
        paging = data.get('paging', {})
        next_url = paging.get('next')
        if next_url:
            url = next_url
            params = None  # next URL已包含所有参数
            page += 1
        else:
            break
    
    return all_accounts

def main():
    print("=== 拉取所有Facebook广告账户 ===\n")
    accounts = get_all_accounts()
    
    print(f"\n=== 总计: {len(accounts)} 个广告账户 ===\n")
    print(f"{'#':<4} {'账户名称':<50} {'账户ID':<20} {'状态':<10} {'花费':<15} {'币种':<6}")
    print("-" * 110)
    
    status_map = {1: 'ACTIVE', 2: 'DISABLED', 3: 'UNSETTLED', 7: 'PENDING_RISK_REVIEW', 9: 'IN_GRACE_PERIOD'}
    
    for i, acc in enumerate(accounts, 1):
        name = acc.get('name', 'N/A')
        acc_id = acc.get('account_id', 'N/A')
        status = status_map.get(acc.get('account_status'), str(acc.get('account_status', 'N/A')))
        spent = acc.get('amount_spent', '0')
        currency = acc.get('currency', '')
        timezone = acc.get('timezone_name', '')
        
        print(f"{i:<4} {name:<50} {acc_id:<20} {status:<10} {spent:<15} {currency:<6}")
    
    # 保存到文件
    with open('output/facebook_accounts.json', 'w', encoding='utf-8') as f:
        json.dump(accounts, f, indent=2, ensure_ascii=False)
    print(f"\n已保存到 output/facebook_accounts.json")

if __name__ == "__main__":
    main()