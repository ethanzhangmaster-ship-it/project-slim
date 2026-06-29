"""分析P04 Top Winners的视觉DNA - 颜色/构图/亮度 + 心理驱动推断

按项目记忆要求:
- Visual DNA包含心理驱动(Collection, Progress, Mystery)
- 不只是视觉元素,要分析深层心理hook
"""
import json
import os
from collections import Counter
from PIL import Image
import numpy as np

CREATIVES_FILE = 'output/facebook_top_creatives/all_image_creatives_with_perf.json'
OUTPUT = 'output/facebook_ads_data/p04_winner_dna.json'


def analyze_image_colors(img_path):
    """分析图片颜色分布"""
    try:
        img = Image.open(img_path).convert('RGB')
        img_small = img.resize((100, 100))
        pixels = np.array(img_small).reshape(-1, 3)

        # 颜色聚类(简单分桶)
        colors = []
        for r, g, b in pixels:
            # 判断主色相
            if r > 150 and g > 150 and b > 150:
                colors.append('white/light')
            elif r < 60 and g < 60 and b < 60:
                colors.append('black/dark')
            elif r > 150 and g < 100 and b < 100:
                colors.append('red')
            elif r > 150 and g > 150 and b < 100:
                colors.append('yellow/gold')
            elif r < 100 and g > 150 and b < 100:
                colors.append('green')
            elif r < 100 and g < 100 and b > 150:
                colors.append('blue')
            elif r > 100 and g < 150 and b > 150:
                colors.append('purple/violet')
            elif r > 200 and g > 150 and b > 150:
                colors.append('pink/rose')
            elif r > 150 and g > 100 and b < 100:
                colors.append('orange')
            elif r > 100 and g > 80 and b < 80:
                colors.append('brown/warm')
            else:
                colors.append('gray/neutral')

        counter = Counter(colors)
        total = len(colors)
        return {k: round(v / total * 100, 1) for k, v in counter.most_common(5)}
    except Exception as e:
        return {'error': str(e)}


def analyze_brightness(img_path):
    """分析亮度和饱和度"""
    try:
        img = Image.open(img_path).convert('RGB')
        img_small = img.resize((100, 100))
        pixels = np.array(img_small).reshape(-1, 3).astype(float)

        brightness = pixels.mean(axis=1).mean()
        max_rgb = pixels.max(axis=1)
        min_rgb = pixels.min(axis=1)
        saturation = np.where(max_rgb > 0, (max_rgb - min_rgb) / max_rgb, 0).mean()

        return {
            'brightness': round(float(brightness) / 255, 2),
            'saturation': round(float(saturation), 2),
            'level': 'bright' if brightness > 150 else ('medium' if brightness > 80 else 'dark')
        }
    except Exception as e:
        return {'error': str(e)}


def analyze_composition(img_path):
    """9宫格构图分析 - 找视觉焦点"""
    try:
        img = Image.open(img_path).convert('RGB')
        w, h = img.size
        img_small = img.resize((90, 90))
        pixels = np.array(img_small).reshape(9, 10, 10, 3).astype(float)

        # 每个grid的亮度和饱和度
        grids = []
        for i in range(3):
            for j in range(3):
                block = pixels[i * 3 + j // 3]  # 不对,reshape后索引方式不同
                pass

        # 重新计算 - 3x3 grid
        arr = np.array(img_small)  # 90x90x3
        grid_scores = []
        for i in range(3):
            for j in range(3):
                block = arr[i*30:(i+1)*30, j*30:(j+1)*30]
                # 焦点 = 高对比度区域
                contrast = block.std()
                grid_scores.append({
                    'grid': f"{i+1}{j+1}",
                    'contrast': round(float(contrast), 1)
                })

        # 找最亮的grid(视觉焦点)
        top_grid = max(grid_scores, key=lambda x: x['contrast'])
        return {
            'focus_grid': top_grid['grid'],
            'focus_contrast': top_grid['contrast'],
            'all_grids': grid_scores
        }
    except Exception as e:
        return {'error': str(e)}


def infer_psychological_hook(ad_name, title, body):
    """从ad_name/title/body推断心理驱动类型"""
    text = f"{ad_name} {title} {body}".lower()

    hooks = []

    # Collection - 收集
    coll_keywords = ['collect', 'collection', 'creature', '200+', '300+', 'hatch', 'gather', 'merge']
    if any(k in text for k in coll_keywords):
        hooks.append('collection')

    # Progress - 成长/进化
    prog_keywords = ['evolve', 'evolution', 'grow', 'upgrade', 'progress', '→', 'level', 'tier',
                     'shack', 'castle', 'empire', 'egg', 'dragon', 'build']
    if any(k in text for k in prog_keywords):
        hooks.append('progress')

    # Mystery - 神秘/好奇心
    myst_keywords = ['mystery', 'mysterious', 'secret', 'hidden', 'unknown', 'magic', 'magical',
                     'dark', 'night', 'moon', 'shadow', 'discover']
    if any(k in text for k in myst_keywords):
        hooks.append('mystery')

    # Reward - 奖励
    rew_keywords = ['reward', 'bonus', 'free', 'gift', 'prize', 'treasure', 'win']
    if any(k in text for k in rew_keywords):
        hooks.append('reward')

    # Cute - 可爱
    cute_keywords = ['cute', 'baby', 'adorable', 'kawaii', 'chibi', 'sweet']
    if any(k in text for k in cute_keywords):
        hooks.append('cute')

    # Magic - 魔法
    magic_keywords = ['magic', 'magical', 'spell', 'witch', 'wizard', 'enchant', 'potion']
    if any(k in text for k in magic_keywords):
        hooks.append('magic')

    return hooks if hooks else ['unknown']


def main():
    with open(CREATIVES_FILE, 'r', encoding='utf-8') as f:
        creatives = json.load(f)

    # P04 Top 10 by spend
    p04 = sorted([c for c in creatives if c['project'] == 'P04'], key=lambda x: x['spend'], reverse=True)[:10]

    print("="*70)
    print("  P04 Top 10 Winners - Visual DNA Analysis")
    print("="*70)

    results = []
    for i, c in enumerate(p04, 1):
        img_path = c.get('local_path', '')
        if not os.path.exists(img_path):
            print(f"\n[{i}] {c['ad_name']} - 图片文件不存在")
            continue

        print(f"\n[{i}] {c['ad_name']}")
        print(f"    CID: {c['creative_id']} | ${c['spend']:.0f} | CTR {c['ctr']}% | IPM {c['ipm']} | CPI ${c['cpi']}")

        colors = analyze_image_colors(img_path)
        brightness = analyze_brightness(img_path)
        composition = analyze_composition(img_path)
        hooks = infer_psychological_hook(c['ad_name'], c.get('title', ''), c.get('body', ''))

        print(f"    颜色分布: {colors}")
        print(f"    亮度: {brightness}")
        print(f"    构图焦点: {composition.get('focus_grid', '?')} (contrast={composition.get('focus_contrast', 0)})")
        print(f"    心理驱动: {hooks}")
        print(f"    标题: {c.get('title', '')[:60]}")
        print(f"    文案: {c.get('body', '')[:80]}")

        results.append({
            'rank': i,
            'ad_name': c['ad_name'],
            'creative_id': c['creative_id'],
            'platform': c.get('platform', ''),
            'spend': c['spend'],
            'ctr': c['ctr'],
            'ipm': c['ipm'],
            'cpi': c['cpi'],
            'installs': c['installs'],
            'title': c.get('title', ''),
            'body': c.get('body', ''),
            'call_to_action': c.get('call_to_action', ''),
            'local_path': img_path,
            'visual_dna': {
                'colors': colors,
                'brightness': brightness,
                'composition': composition,
                'psychological_hooks': hooks,
            }
        })

    # 汇总模式
    print(f"\n{'='*70}")
    print(f"  P04 Winner 模式汇总")
    print(f"{'='*70}")

    # 颜色模式
    all_colors = {}
    for r in results:
        for color, pct in r['visual_dna']['colors'].items():
            if color not in all_colors:
                all_colors[color] = []
            all_colors[color].append(pct)

    print(f"\n主色分布(平均占比):")
    for color, pcts in sorted(all_colors.items(), key=lambda x: -np.mean(x[1])):
        print(f"  {color:<20} 平均 {np.mean(pcts):.1f}% (出现{len(pcts)}次)")

    # 亮度模式
    bright_levels = [r['visual_dna']['brightness']['level'] for r in results]
    print(f"\n亮度分布: {Counter(bright_levels)}")

    # 心理驱动
    all_hooks = []
    for r in results:
        all_hooks.extend(r['visual_dna']['psychological_hooks'])
    print(f"\n心理驱动分布: {Counter(all_hooks)}")

    # 构图焦点
    focus_grids = [r['visual_dna']['composition']['focus_grid'] for r in results]
    print(f"\n构图焦点分布: {Counter(focus_grids)}")

    # 保存
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump({
            'project': 'P04',
            'analyzed_count': len(results),
            'winners': results,
            'patterns': {
                'color_distribution': {k: round(np.mean(v), 1) for k, v in all_colors.items()},
                'brightness_levels': dict(Counter(bright_levels)),
                'psychological_hooks': dict(Counter(all_hooks)),
                'focus_grids': dict(Counter(focus_grids)),
            }
        }, f, indent=2, ensure_ascii=False)
    print(f"\n已保存: {OUTPUT}")


if __name__ == "__main__":
    main()
