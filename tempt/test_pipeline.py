import os
"""
测试动态行为层可视化完整流程
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

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")\nif not MAPBOX_TOKEN:\n    raise RuntimeError("MAPBOX_TOKEN is not set")
BOUNDS = [112.703, 27.8, 113.284, 28.5]
OUTPUT_SECTION = '3.Situation_Diagnosis/3.1Holistic_Diagnosis/3.1.2Dynamic_Stats'

tbd.set_mapboxtoken(MAPBOX_TOKEN)
tbd.set_imgsavepath(str(Path(r'E:\00_Commute_Scenario_Research\tempt')))

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

# --- OD流线图 ---
print("\n生成OD流线图...")
html_path = get_result_path(OUTPUT_SECTION, 'star_OD流线图_实际格局.html')

df_top = df_od.nlargest(2000, 'count').copy()
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
print(f"OD流线图HTML已保存: {html_path}")

# --- 社区发现 ---
print("\n开始社区发现...")
params = tbd.area_to_params(location=BOUNDS, accuracy=500, method='rect')
od_gdf = tbd.odagg_grid(df_od, params, col=['slon', 'slat', 'elon', 'elat'])

od_gdf['S'] = od_gdf['SLONCOL'].astype(str) + ',' + od_gdf['SLATCOL'].astype(str)
od_gdf['E'] = od_gdf['ELONCOL'].astype(str) + ',' + od_gdf['ELATCOL'].astype(str)

node = set(od_gdf['S']) | set(od_gdf['E'])
node = pd.DataFrame(node, columns=['grid'])
node['node_id'] = range(len(node))

node_s = node.copy()
node_s.columns = ['S', 'S_id']
od_gdf = pd.merge(od_gdf, node_s, on=['S'])
node_e = node.copy()
node_e.columns = ['E', 'E_id']
od_gdf = pd.merge(od_gdf, node_e, on=['E'])
edge = od_gdf[['S_id', 'E_id', 'count']]

# 保存中间CSV
od_gdf[['SLONCOL', 'SLATCOL', 'ELONCOL', 'ELATCOL', 'count']].to_csv(
    get_result_path(OUTPUT_SECTION, '社区发现_01_网格化OD.csv'), index=False, encoding='utf-8-sig'
)
node.to_csv(get_result_path(OUTPUT_SECTION, '社区发现_02_节点.csv'), index=False, encoding='utf-8-sig')
edge.to_csv(get_result_path(OUTPUT_SECTION, '社区发现_03_边.csv'), index=False, encoding='utf-8-sig')

g = ig.Graph()
g.add_vertices(len(node))
g.add_edges(edge[['S_id', 'E_id']].values)
edge_weights = edge['count'].values
for i in range(len(edge_weights)):
    g.es[i]['weight'] = edge_weights[i]

g_clustered = g.community_multilevel(weights=edge_weights, return_levels=False)
modularity = g_clustered.modularity
node['group'] = g_clustered.membership
node.columns = ['grid', 'node_id', 'group']
node.to_csv(get_result_path(OUTPUT_SECTION, '社区发现_04_社区分配.csv'), index=False, encoding='utf-8-sig')

print(f"模块度: {modularity:.6f}, 社区数: {node['group'].nunique()}")

group_counts = node['group'].value_counts()
large_groups = group_counts[group_counts > 10].index
node_filtered = node[node['group'].isin(large_groups)].copy()
node_filtered['LONCOL'] = node_filtered['grid'].apply(lambda r: int(r.split(',')[0]))
node_filtered['LATCOL'] = node_filtered['grid'].apply(lambda r: int(r.split(',')[1]))
node_filtered['geometry'] = node_filtered.apply(
    lambda row: tbd.grid_to_polygon([row['LONCOL'], row['LATCOL']], params)[0],
    axis=1
)
node_gdf = gpd.GeoDataFrame(node_filtered, crs='EPSG:4326')

node_community = tbd.merge_polygon(node_gdf, 'group')
node_community = tbd.polyon_exterior(node_community, minarea=0.0001)

# 保存最终CSV
node_community_export = node_community.copy()
node_community_export['geometry_wkt'] = node_community_export['geometry'].apply(lambda g: g.wkt)
node_community_export[['group', 'geometry_wkt']].to_csv(
    get_result_path(OUTPUT_SECTION, 'star_社区发现_最终结果.csv'), index=False, encoding='utf-8-sig'
)

# 可视化
print("\n生成社区发现地图...")
n_communities = len(node_community)
cmap_colors = sns.hls_palette(n_colors=n_communities, l=0.7, s=0.8)

fig = plt.figure(figsize=(14, 14), dpi=300)
ax = plt.subplot(111)
plt.sca(ax)
tbd.plot_map(plt, bounds=BOUNDS, zoom=11, style=6)
node_community.sample(frac=1, random_state=42).plot(
    cmap=ListedColormap(cmap_colors), ax=ax, edgecolor='#333', linewidth=1.5, alpha=0.7
)
tbd.plotscale(ax, bounds=BOUNDS, textsize=10, compasssize=1, textcolor='black', accuracy=2000, rect=[0.06, 0.03], zorder=10)
plt.axis('off')
plt.xlim(BOUNDS[0], BOUNDS[2])
plt.ylim(BOUNDS[1], BOUNDS[3])

png_path = get_result_path(OUTPUT_SECTION, 'star_社区发现结果.png')
plt.savefig(png_path, dpi=300, bbox_inches='tight', facecolor='white')
plt.close(fig)

# 保存报告
report_path = get_result_path(OUTPUT_SECTION, '社区发现_模块度报告.txt')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(f"社区发现结果报告\n")
    f.write(f"{'='*40}\n")
    f.write(f"算法: Louvain (igraph.community_multilevel)\n")
    f.write(f"网格精度: 500m\n")
    f.write(f"节点数: {len(node)}\n")
    f.write(f"边数: {len(edge)}\n")
    f.write(f"模块度: {modularity:.6f}\n")
    f.write(f"总社区数: {node['group'].nunique()}\n")
    f.write(f"大社区数(>10网格): {len(large_groups)}\n")
    f.write(f"最大社区网格数: {group_counts.max()}\n")
    f.write(f"最小社区网格数: {group_counts.min()}\n")

print(f"\n社区发现PNG已保存: {png_path}")
print(f"模块度报告已保存: {report_path}")
print(f"\n模块度: {modularity:.6f}, 大社区数: {len(large_groups)}")
print("\n全部完成！")
