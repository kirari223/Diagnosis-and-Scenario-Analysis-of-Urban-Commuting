import os
"""
重新生成OD流线图和社区发现图
使用 tbd.plot_map 直接叠加底图，输出PNG（不使用HTML）
"""
import sys
from pathlib import Path
sys.path.insert(0, r'E:\00_Commute_Scenario_Research')

import pandas as pd
import geopandas as gpd
import transbigdata as tbd
import seaborn as sns
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import matplotlib as mpl

from src import OD_FEATURE_CSV, SHP_PATH, get_result_path
from src.data_prep import load_fence
from src.visualization import _add_scalebar_auto, add_north_arrow

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

# 配置
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")\nif not MAPBOX_TOKEN:\n    raise RuntimeError("MAPBOX_TOKEN is not set")
BOUNDS = [112.703, 27.92, 113.284, 28.5]
OUTPUT_SECTION = '3.Situation_Diagnosis/3.1Holistic_Diagnosis/3.1.2Dynamic_Stats'
TILE_CACHE_DIR = Path(r'E:\00_Commute_Scenario_Research\tempt\tileimg')

tbd.set_mapboxtoken(MAPBOX_TOKEN)
TILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
tbd.set_imgsavepath(str(TILE_CACHE_DIR))

print("="*60)
print("加载数据...")
print("="*60)

fence = load_fence(SHP_PATH)
df_od_full = pd.read_csv(OD_FEATURE_CSV, encoding='utf-8-sig')
df_od_full = df_od_full.rename(columns={'Htaz': 'o', 'Jtaz': 'd'})

fence_pts = fence[['taz', 'center_x', 'center_y']].copy()
fence_pts['taz'] = fence_pts['taz'].astype(int)

# ==================== 1. OD流线图 ====================
print("\n" + "="*60)
print("1. 生成OD流线图（tbd.plot_map + matplotlib，mincount=2）")
print("="*60)

df_od = df_od_full[['o', 'd', '人数']].copy()
df_od['o'] = df_od['o'].astype(int)
df_od['d'] = df_od['d'].astype(int)

df_od = df_od.merge(
    fence_pts.rename(columns={'taz': 'o', 'center_x': 'S_x', 'center_y': 'S_y'}),
    on='o', how='inner'
)
df_od = df_od.merge(
    fence_pts.rename(columns={'taz': 'd', 'center_x': 'E_x', 'center_y': 'E_y'}),
    on='d', how='inner'
)

# 筛选 mincount>=2
df_od = df_od[df_od['人数'] >= 2].copy()
print(f"筛选后OD对数（人数>=2）: {len(df_od)}")

# 按人数排序（小的先画，大的后画）
df_od = df_od.sort_values(by='人数')

# 创建图
fig = plt.figure(figsize=(14, 14), dpi=300)
ax = plt.subplot(111)
plt.sca(ax)

# 加载底图（style=6: light-ch 浅色中文版）
print("加载底图（style=6: light-ch）...")
tbd.plot_map(plt, bounds=BOUNDS, zoom=11, style=6)

# 绘制TAZ边界（半透明）
fence.plot(ax=ax, edgecolor='#666666', facecolor='none', linewidth=0.3, alpha=0.5)

# 设置colormap
vmax = df_od['人数'].max()
vmin = df_od['人数'].min()
norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
cmapname = 'YlOrRd'
cmap = matplotlib.cm.get_cmap(cmapname)

# 绘制OD流线
print(f"绘制 {len(df_od)} 条OD流线...")
for i in range(len(df_od)):
    row = df_od.iloc[i]
    color_i = cmap(norm(row['人数']))
    linewidth_i = 0.3 + norm(row['人数']) * 3.0
    plt.plot(
        [row['S_x'], row['E_x']],
        [row['S_y'], row['E_y']],
        color=color_i,
        linewidth=linewidth_i,
        alpha=0.6
    )

# 添加colorbar
plt.imshow([[vmin, vmax]], cmap=cmap)
cax = plt.axes([0.08, 0.35, 0.02, 0.3])
cbar = plt.colorbar(cax=cax)
cbar.set_label('通勤人数', fontsize=24, fontweight='bold')
cbar.ax.tick_params(labelsize=20)

# 使用项目标准比例尺和指北针
temp_gdf = gpd.GeoDataFrame(geometry=[fence.geometry.iloc[0]], crs='EPSG:4326')
right_edge_pos = 0.985
_add_scalebar_auto(ax, temp_gdf, label_fontsize=24, right_edge_pos=right_edge_pos)
add_north_arrow(ax, right_edge_pos=right_edge_pos)

plt.axis('off')
ax.set_xlim(BOUNDS[0], BOUNDS[2])
ax.set_ylim(BOUNDS[1], BOUNDS[3])

# 保存PNG（bbox_inches=None 避免白边）
png_path = get_result_path(OUTPUT_SECTION, 'star_OD流线图_实际格局.png')
plt.savefig(png_path, dpi=300, bbox_inches=None, pad_inches=0, facecolor='white')
plt.close(fig)

print(f"OD流线图PNG已保存: {png_path}")

# ==================== 2. 社区发现图 ====================
print("\n" + "="*60)
print("2. 重新生成社区发现图（tbd.plot_map + matplotlib）")
print("="*60)

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
print("合并多边形...")
node_community = tbd.merge_polygon(node_gdf, 'group')
node_community = tbd.polyon_exterior(node_community, minarea=0.0001)
print(f"合并后社区数: {len(node_community)}")

# 可视化
n_communities = len(node_community)
cmap_colors = sns.hls_palette(n_colors=n_communities, l=0.7, s=0.8)

fig = plt.figure(figsize=(14, 14), dpi=300)
ax = plt.subplot(111)
plt.sca(ax)

# 加载底图（style=6: light-ch 浅色中文版）
print("加载底图（style=6: light-ch）...")
tbd.plot_map(plt, bounds=BOUNDS, zoom=11, style=6)

# 绘制社区
node_community.sample(frac=1, random_state=42).plot(
    cmap=ListedColormap(cmap_colors), ax=ax, edgecolor='#333', linewidth=1.5, alpha=0.7
)

# 使用项目标准比例尺和指北针
temp_gdf = gpd.GeoDataFrame(geometry=[node_community.geometry.iloc[0]], crs='EPSG:4326')
right_edge_pos = 0.985
_add_scalebar_auto(ax, temp_gdf, label_fontsize=24, right_edge_pos=right_edge_pos)
add_north_arrow(ax, right_edge_pos=right_edge_pos)

plt.axis('off')
ax.set_xlim(BOUNDS[0], BOUNDS[2])
ax.set_ylim(BOUNDS[1], BOUNDS[3])

# 保存PNG（bbox_inches=None 避免白边）
png_path = get_result_path(OUTPUT_SECTION, 'star_社区发现结果.png')
plt.savefig(png_path, dpi=300, bbox_inches=None, pad_inches=0, facecolor='white')
plt.close(fig)

print(f"社区发现PNG已保存: {png_path}")

print("\n" + "="*60)
print("全部完成！")
print("="*60)
print(f"\n输出文件:")
print(f"1. OD流线图PNG: {get_result_path(OUTPUT_SECTION, 'star_OD流线图_实际格局.png')}")
print(f"2. 社区发现PNG: {get_result_path(OUTPUT_SECTION, 'star_社区发现结果.png')}")
print(f"\n更新内容:")
print(f"- OD流线图: mincount=2（只显示人数>=2的OD对）")
print(f"- 底图: style=6（light-ch 浅色中文版）")
print(f"- 底图四至点: {BOUNDS}")
print(f"- 比例尺和指北针: 使用项目标准函数")
print(f"- 输出格式: 直接PNG（无白边，bbox_inches=None）")
