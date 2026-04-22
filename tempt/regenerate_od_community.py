import os
"""
重新生成OD流线图和社区发现图（使用项目标准比例尺和指北针）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(r"E:\00_Commute_Scenario_Research")))

import pandas as pd
import geopandas as gpd
import transbigdata as tbd
import igraph as ig
import seaborn as sns
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import plotly.graph_objects as go

from src import OD_FEATURE_CSV, SHP_PATH, get_result_path
from src.data_prep import load_fence
from src.visualization import _add_scalebar_auto, add_north_arrow

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")\nif not MAPBOX_TOKEN:\n    raise RuntimeError("MAPBOX_TOKEN is not set")
BOUNDS = [112.703, 27.92, 113.284, 28.5]  # 更新后的四至点
OUTPUT_SECTION = '3.Situation_Diagnosis/3.1Holistic_Diagnosis/3.1.2Dynamic_Stats'

tbd.set_mapboxtoken(MAPBOX_TOKEN)
tbd.set_imgsavepath(str(Path(r'E:\00_Commute_Scenario_Research\tempt\tileimg')))

print("加载数据...")
fence = load_fence(SHP_PATH)
df_od_full = pd.read_csv(OD_FEATURE_CSV, encoding='utf-8-sig')
df_od_full = df_od_full.rename(columns={'Htaz': 'o', 'Jtaz': 'd'})

fence_pts = fence[['taz', 'center_x', 'center_y']].copy()
fence_pts['taz'] = fence_pts['taz'].astype(int)

people_col = [c for c in df_od_full.columns if '人数' in c][0]
df_od = df_od_full[['o', 'd']].copy()
df_od['count'] = df_od_full[people_col]
df_od['o'] = df_od['o'].astype(int)
df_od['d'] = df_od['d'].astype(int)
df_od = df_od.merge(fence_pts.rename(columns={'taz': 'o', 'center_x': 'slon', 'center_y': 'slat'}), on='o', how='inner')
df_od = df_od.merge(fence_pts.rename(columns={'taz': 'd', 'center_x': 'elon', 'center_y': 'elat'}), on='d', how='inner')

print(f"OD数据: {len(df_od)} 条, 总流量: {df_od['count'].sum():.0f}")

# ==================== 1. OD流线图（keplergl + mincount=2） ====================
print("\n=== 1. 生成OD流线图（keplergl，mincount=2）===")

try:
    # 使用 keplergl
    vmap = tbd.visualization_od(
        df_od,
        col=['slon', 'slat', 'elon', 'elat', 'count'],
        zoom='auto',
        height=800,
        accuracy=500,
        mincount=2  # 只显示流量>=2的OD对
    )

    html_path = get_result_path(OUTPUT_SECTION, 'star_OD流线图_实际格局.html')
    vmap.save_to_html(str(html_path))
    print(f"OD流线图HTML已保存（keplergl）: {html_path}")

    # 使用 playwright 截图
    try:
        from playwright.sync_api import sync_playwright

        png_path = get_result_path(OUTPUT_SECTION, 'star_OD流线图_实际格局.png')

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 1920, 'height': 1080})
            page.goto(f'file:///{html_path.as_posix()}')
            page.wait_for_timeout(8000)  # 等待地图加载
            page.screenshot(path=str(png_path), full_page=False)
            browser.close()

        print(f"OD流线图PNG已保存: {png_path}")

    except Exception as e:
        print(f"playwright截图失败: {e}")
        print("请手动打开HTML文件并截图")

except ImportError:
    print("keplergl未安装，使用plotly fallback...")

    # Plotly fallback
    html_path = get_result_path(OUTPUT_SECTION, 'star_OD流线图_实际格局.html')

    # 筛选 mincount>=2
    df_filtered = df_od[df_od['count'] >= 2].copy()
    df_top = df_filtered.nlargest(2000, 'count').copy()

    print(f"筛选后OD对数（count>=2）: {len(df_filtered)}")
    print(f"可视化前{len(df_top)}条")

    val_min = df_top['count'].min()
    val_max = df_top['count'].max()
    if val_max == val_min:
        val_max = val_min + 1

    fig_od = go.Figure()
    for _, row in df_top.iterrows():
        norm = (row['count'] - val_min) / (val_max - val_min)
        width = 1.0 + norm * 6.0
        alpha = 0.2 + norm * 0.7
        fig_od.add_trace(go.Scattermapbox(
            lon=[row['slon'], row['elon']],
            lat=[row['slat'], row['elat']],
            mode='lines',
            line=dict(width=width, color=f'rgba(46,125,154,{alpha:.2f})'),
            showlegend=False,
            hoverinfo='skip',
        ))

    center_lon = (BOUNDS[0] + BOUNDS[2]) / 2
    center_lat = (BOUNDS[1] + BOUNDS[3]) / 2
    fig_od.update_layout(
        mapbox=dict(accesstoken=MAPBOX_TOKEN, style='light', center=dict(lon=center_lon, lat=center_lat), zoom=9),
        margin=dict(l=0, r=0, t=0, b=0), width=1920, height=1080,
    )
    fig_od.write_html(str(html_path))
    print(f"OD流线图HTML已保存（plotly）: {html_path}")

    # Playwright截图
    try:
        from playwright.sync_api import sync_playwright
        png_path = get_result_path(OUTPUT_SECTION, 'star_OD流线图_实际格局.png')
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 1920, 'height': 1080})
            page.goto(f'file:///{html_path.as_posix()}')
            page.wait_for_timeout(5000)
            page.screenshot(path=str(png_path), full_page=False)
            browser.close()
        print(f"OD流线图PNG已保存: {png_path}")
    except Exception as e:
        print(f"playwright截图失败: {e}")

# ==================== 2. 社区发现图（使用项目标准比例尺和指北针）====================
print("\n=== 2. 重新生成社区发现图（使用项目标准比例尺和指北针）===")

# 读取已有的社区发现结果
csv_community = get_result_path(OUTPUT_SECTION, '社区发现_04_社区分配.csv')
node = pd.read_csv(csv_community, encoding='utf-8-sig')

print(f"读取社区分配结果: {len(node)} 个节点")

# 重新生成几何（使用新的BOUNDS）
params = tbd.area_to_params(location=BOUNDS, accuracy=500, method='rect')

group_counts = node['group'].value_counts()
large_groups = group_counts[group_counts > 10].index
node_filtered = node[node['group'].isin(large_groups)].copy()

print(f"大社区数（>10网格）: {len(large_groups)}")
print(f"保留网格数: {len(node_filtered)}")

node_filtered['LONCOL'] = node_filtered['grid'].apply(lambda r: int(r.split(',')[0]))
node_filtered['LATCOL'] = node_filtered['grid'].apply(lambda r: int(r.split(',')[1]))

node_filtered['geometry'] = node_filtered.apply(
    lambda row: tbd.grid_to_polygon([row['LONCOL'], row['LATCOL']], params)[0],
    axis=1
)

node_gdf = gpd.GeoDataFrame(node_filtered, crs='EPSG:4326')

# 合并多边形
node_community = tbd.merge_polygon(node_gdf, 'group')
node_community = tbd.polyon_exterior(node_community, minarea=0.0001)

print(f"合并后社区数: {len(node_community)}")

# 可视化（使用项目标准函数）
n_communities = len(node_community)
cmap_colors = sns.hls_palette(n_colors=n_communities, l=0.7, s=0.8)

fig = plt.figure(figsize=(14, 14), dpi=300)
ax = plt.subplot(111)
plt.sca(ax)

# 加载底图
tbd.plot_map(plt, bounds=BOUNDS, zoom=11, style=6)

# 绘制社区
node_community.sample(frac=1, random_state=42).plot(
    cmap=ListedColormap(cmap_colors), ax=ax, edgecolor='#333', linewidth=1.5, alpha=0.7
)

# 使用项目标准比例尺和指北针函数
# 创建临时GeoDataFrame用于_add_scalebar_auto判断坐标系
temp_gdf = gpd.GeoDataFrame(geometry=[node_community.geometry.iloc[0]], crs='EPSG:4326')

right_edge_pos = 0.985
_add_scalebar_auto(ax, temp_gdf, label_fontsize=24, right_edge_pos=right_edge_pos)
add_north_arrow(ax, right_edge_pos=right_edge_pos)

plt.axis('off')
plt.xlim(BOUNDS[0], BOUNDS[2])
plt.ylim(BOUNDS[1], BOUNDS[3])

png_path = get_result_path(OUTPUT_SECTION, 'star_社区发现结果.png')
plt.savefig(png_path, dpi=300, bbox_inches='tight', facecolor='white')
plt.close(fig)

print(f"社区发现PNG已保存: {png_path}")

print("\n" + "="*60)
print("全部完成！")
print("="*60)
print(f"\n输出文件:")
print(f"1. OD流线图HTML: {get_result_path(OUTPUT_SECTION, 'star_OD流线图_实际格局.html')}")
print(f"2. OD流线图PNG: {get_result_path(OUTPUT_SECTION, 'star_OD流线图_实际格局.png')}")
print(f"3. 社区发现PNG: {get_result_path(OUTPUT_SECTION, 'star_社区发现结果.png')}")
print(f"\n更新内容:")
print(f"- OD流线图: mincount=2（只显示流量>=2的OD对）")
print(f"- 底图四至点: {BOUNDS}")
print(f"- 比例尺和指北针: 使用项目标准函数（_add_scalebar_auto, add_north_arrow）")
