"""分析Top素材的Visual DNA"""
import json
import os
from PIL import Image
from datetime import datetime

IMAGE_DIR = "output/facebook_top_creatives"
OUTPUT_DIR = "output/facebook_ads_data"

def analyze_image(filepath, ad_name, project, perf):
    """分析单张图片的Visual DNA"""
    img = Image.open(filepath)
    img_rgb = img.convert('RGB')
    w, h = img.size
    
    # 1. 主色调分析
    small = img_rgb.resize((100, 100))
    pixels = list(small.getdata())
    
    # 统计颜色分布
    color_counts = {}
    for r, g, b in pixels:
        # 量化到主要色系
        if r > 200 and g > 200 and b > 200:
            color = 'white/light'
        elif r < 50 and g < 50 and b < 50:
            color = 'black/dark'
        elif r > 150 and g < 100 and b > 150:
            color = 'purple/magenta'
        elif r > 200 and g > 150 and b < 100:
            color = 'gold/yellow'
        elif r < 100 and g > 100 and b < 100:
            color = 'green'
        elif r > 200 and g < 100 and b < 100:
            color = 'red'
        elif r < 100 and g < 150 and b > 150:
            color = 'blue'
        elif r > 200 and g > 150 and b > 100:
            color = 'warm/beige'
        else:
            color = 'mixed'
        color_counts[color] = color_counts.get(color, 0) + 1
    
    # 取Top3颜色
    top_colors = sorted(color_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    
    # 2. 亮度分析
    gray = img_rgb.convert('L')
    extrema = gray.getextrema()
    avg_brightness = sum(gray.getdata()) / (w * h)
    
    # 3. 饱和度分析
    total_sat = 0
    for r, g, b in pixels:
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        sat = (max_c - min_c) / max_c if max_c > 0 else 0
        total_sat += sat
    avg_saturation = total_sat / len(pixels)
    
    # 4. 构图分析（简单版）
    # 将图片分成9宫格，计算每个区域的亮度
    grid_brightness = []
    cell_w, cell_h = w // 3, h // 3
    for ry in range(3):
        for rx in range(3):
            cell = gray.crop((rx * cell_w, ry * cell_h, (rx + 1) * cell_w, (ry + 1) * cell_h))
            cell_avg = sum(cell.getdata()) / (cell_w * cell_h)
            grid_brightness.append(round(cell_avg, 1))
    
    # 判断焦点位置
    max_cell = grid_brightness.index(max(grid_brightness))
    focus_positions = ['左上', '中上', '右上', '左中', '正中', '右中', '左下', '中下', '右下']
    focus = focus_positions[max_cell]
    
    # 5. 综合DNA
    dna = {
        "ad_name": ad_name,
        "project": project,
        "image_size": f"{w}x{h}",
        "dominant_colors": [{"color": c, "ratio": round(n / len(pixels) * 100, 1)} for c, n in top_colors],
        "brightness": {
            "avg": round(avg_brightness, 1),
            "range": f"{extrema[0]}-{extrema[1]}",
            "level": "bright" if avg_brightness > 150 else "medium" if avg_brightness > 80 else "dark"
        },
        "saturation": {
            "avg": round(avg_saturation * 100, 1),
            "level": "high" if avg_saturation > 0.5 else "medium" if avg_saturation > 0.3 else "low"
        },
        "composition": {
            "focus_position": focus,
            "grid_brightness": grid_brightness,
            "layout": "hero_center" if max_cell == 4 else "top_focus" if max_cell < 3 else "bottom_focus" if max_cell > 5 else "side_focus"
        },
        "performance": {
            "spend": perf.get('spend', 0),
            "ctr": perf.get('ctr', 0),
            "ipm": perf.get('ipm', 0),
            "cpi": perf.get('cpi', 0),
            "installs": perf.get('installs', 0),
            "roas": perf.get('roas', 0),
        }
    }
    
    return dna

def main():
    # 读取素材记录
    with open(f"{IMAGE_DIR}/top_creatives.json", 'r', encoding='utf-8') as f:
        creatives = json.load(f)
    
    # 筛选有效图片（>5KB）
    valid_creatives = [c for c in creatives if os.path.exists(c.get('local_path', '')) and os.path.getsize(c['local_path']) > 5000]
    
    print(f"=== 分析 {len(valid_creatives)} 张有效素材 ===\n")
    
    all_dnas = []
    for c in valid_creatives:
        print(f"分析: {c['ad_name'][:40]} | spend=${c['spend']} | ctr={c['ctr']}%")
        try:
            dna = analyze_image(c['local_path'], c['ad_name'], c['project'], c)
            all_dnas.append(dna)
        except Exception as e:
            print(f"  错误: {e}")
    
    # 分析共性
    print(f"\n{'='*80}")
    print(f"=== DNA分析汇总 ===")
    print(f"{'='*80}\n")
    
    # 颜色分析
    print("--- 主色调分布 ---")
    color_stats = {}
    for d in all_dnas:
        for c in d['dominant_colors']:
            color = c['color']
            color_stats[color] = color_stats.get(color, 0) + 1
    for c, n in sorted(color_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  {c}: {n}张")
    
    # 亮度分析
    print("\n--- 亮度分布 ---")
    bright_stats = {}
    for d in all_dnas:
        level = d['brightness']['level']
        bright_stats[level] = bright_stats.get(level, 0) + 1
    for l, n in sorted(bright_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  {l}: {n}张")
    
    # 饱和度分析
    print("\n--- 饱和度分布 ---")
    sat_stats = {}
    for d in all_dnas:
        level = d['saturation']['level']
        sat_stats[level] = sat_stats.get(level, 0) + 1
    for s, n in sorted(sat_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  {s}: {n}张")
    
    # 构图分析
    print("\n--- 构图焦点分布 ---")
    focus_stats = {}
    for d in all_dnas:
        focus = d['composition']['focus_position']
        focus_stats[focus] = focus_stats.get(focus, 0) + 1
    for f, n in sorted(focus_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  {f}: {n}张")
    
    # 性能与DNA关联
    print("\n--- 高CTR素材特征 ---")
    high_ctr = sorted([d for d in all_dnas if d['performance']['spend'] > 100], key=lambda x: x['performance']['ctr'], reverse=True)[:5]
    for d in high_ctr:
        colors = '/'.join([c['color'] for c in d['dominant_colors'][:2]])
        print(f"  {d['ad_name'][:40]} | ctr={d['performance']['ctr']}% | 颜色: {colors} | 亮度: {d['brightness']['level']} | 焦点: {d['composition']['focus_position']}")
    
    print("\n--- 高IPM素材特征 ---")
    high_ipm = sorted([d for d in all_dnas if d['performance']['spend'] > 100], key=lambda x: x['performance']['ipm'], reverse=True)[:5]
    for d in high_ipm:
        colors = '/'.join([c['color'] for c in d['dominant_colors'][:2]])
        print(f"  {d['ad_name'][:40]} | ipm={d['performance']['ipm']} | 颜色: {colors} | 亮度: {d['brightness']['level']} | 焦点: {d['composition']['focus_position']}")
    
    # 保存完整DNA
    with open(f"{OUTPUT_DIR}/creative_dna_analysis.json", 'w', encoding='utf-8') as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total_analyzed": len(all_dnas),
            "color_distribution": color_stats,
            "brightness_distribution": bright_stats,
            "saturation_distribution": sat_stats,
            "focus_distribution": focus_stats,
            "high_ctr_creatives": high_ctr,
            "high_ipm_creatives": high_ipm,
            "all_dnas": all_dnas
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nDNA分析已保存: {OUTPUT_DIR}/creative_dna_analysis.json")

if __name__ == "__main__":
    main()