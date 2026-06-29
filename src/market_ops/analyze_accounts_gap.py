"""分析50个账户的活跃情况,找出需要补抓的账户"""
import json
import os

with open('output/facebook_accounts.json', 'r', encoding='utf-8') as f:
    all_accs = json.load(f)

with open('output/facebook_ads_data/summary.json', 'r', encoding='utf-8') as f:
    summary = json.load(f)

# 已抓取的账户ID集合(用account_id,11位数字)
done_ids = {a['account_id'] for a in summary['accounts']}
print(f"已抓取账户: {len(done_ids)} 个")
print(f"全量账户: {len(all_accs)} 个\n")

status_map = {1: 'ACTIVE', 2: 'DISABLED', 3: 'UNSETTLED', 7: 'PENDING_RISK_REVIEW', 9: 'IN_GRACE_PERIOD'}

active_to_pull = []
disabled = []
already = []

for acc in all_accs:
    acc_id = acc.get('account_id', '')
    status = status_map.get(acc.get('account_status'), str(acc.get('account_status')))
    spent = float(acc.get('amount_spent', 0) or 0)
    name = acc.get('name', 'N/A')

    if acc_id in done_ids:
        already.append(acc)
    elif status == 'ACTIVE' and spent > 0:
        active_to_pull.append(acc)
    else:
        disabled.append(acc)

print(f"=== 已抓取 ({len(already)}) ===")
for a in already:
    print(f"  {a.get('account_id'):<20} {a.get('name','')[:30]:<30} spent={float(a.get('amount_spent',0) or 0):.2f}")

print(f"\n=== 待补抓 (ACTIVE + 有花费, {len(active_to_pull)}) ===")
for a in active_to_pull:
    print(f"  {a.get('account_id'):<20} {a.get('name','')[:30]:<30} spent={float(a.get('amount_spent',0) or 0):.2f} {a.get('currency','')}")

print(f"\n=== 跳过 (非活跃或0花费, {len(disabled)}) ===")
for a in disabled:
    status = status_map.get(a.get('account_status'), '?')
    print(f"  {a.get('account_id'):<20} {a.get('name','')[:30]:<30} status={status} spent={float(a.get('amount_spent',0) or 0):.2f}")

# 保存待抓取清单
with open('output/facebook_ads_data/accounts_to_pull.json', 'w', encoding='utf-8') as f:
    json.dump(active_to_pull, f, indent=2, ensure_ascii=False)
print(f"\n待抓取清单已保存: output/facebook_ads_data/accounts_to_pull.json ({len(active_to_pull)}个)")
