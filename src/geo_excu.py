"""
地理处理模块
包含标准差椭圆、社区发现等地理分析功能
"""
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.ops import unary_union

from .config import VISUAL_CONFIG, MAP_ELEMENTS, CRS_UTM
from .utils import logger

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def compute_std_ellipse(
    coords: np.ndarray,
    weights: Optional[np.ndarray] = None,
) -> dict:
    """
    计算加权标准差椭圆参数。

    Args:
        coords:  形状 (N, 2) 的坐标数组，列顺序为 [x, y]（经度/横坐标在前）
        weights: 长度为 N 的权重数组，None 时等权

    Returns:
        dict:
            center_x, center_y  — 加权均值坐标
            semi_major           — 长半轴（与坐标单位相同）
            semi_minor           — 短半轴
            angle_deg            — 长轴与 x 轴正方向的夹角（度，逆时针为正）
            ellipse_x, ellipse_y — 椭圆轮廓点坐标（各 360 个点）
    """
    coords = np.asarray(coords, dtype=float)
    if coords.ndim != 2 or coords.shape[1] != 2:
        raise ValueError("coords 必须是形状 (N, 2) 的数组")

    if weights is None:
        weights = np.ones(len(coords))
    weights = np.asarray(weights, dtype=float)
    if weights.sum() == 0:
        raise ValueError("权重之和为 0")
    weights = weights / weights.sum()

    # 加权均值
    cx = float(np.sum(weights * coords[:, 0]))
    cy = float(np.sum(weights * coords[:, 1]))

    # 加权协方差矩阵
    dx = coords[:, 0] - cx
    dy = coords[:, 1] - cy
    cov_xx = float(np.sum(weights * dx * dx))
    cov_xy = float(np.sum(weights * dx * dy))
    cov_yy = float(np.sum(weights * dy * dy))
    cov = np.array([[cov_xx, cov_xy], [cov_xy, cov_yy]])

    # 特征值/特征向量
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # eigh 返回升序特征值，取最大对应长轴
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    semi_major = float(2.0 * np.sqrt(max(eigenvalues[0], 0)))
    semi_minor = float(2.0 * np.sqrt(max(eigenvalues[1], 0)))

    # 长轴方向角（与 x 轴夹角，逆时针为正）
    angle_rad = float(np.arctan2(eigenvectors[1, 0], eigenvectors[0, 0]))
    angle_deg = float(np.degrees(angle_rad))

    # 生成椭圆轮廓点
    t = np.linspace(0, 2 * np.pi, 360)
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
    ex = (semi_major * np.cos(t) * cos_a - semi_minor * np.sin(t) * sin_a) + cx
    ey = (semi_major * np.cos(t) * sin_a + semi_minor * np.sin(t) * cos_a) + cy

    return {
        'center_x': cx,
        'center_y': cy,
        'semi_major': semi_major,
        'semi_minor': semi_minor,
        'angle_deg': angle_deg,
        'ellipse_x': ex,
        'ellipse_y': ey,
    }


def plot_std_ellipse(
    fence: gpd.GeoDataFrame,
    static_csv_path,
    output_path,
) -> None:
    """
    绘制居住地（O端）和工作地（D端）的标准差椭圆，叠加在 TAZ 底图上。

    Args:
        fence:           TAZ 边界 GeoDataFrame（含 taz, center_x, center_y 列）
        static_csv_path: [主城区]TAZ4-static.csv 路径，含 taz/人口类型/人数 列
        output_path:     输出 PNG 路径
    """
    from .visualization import _prepare_map_for_plot, _add_scalebar_auto, add_north_arrow

    static_csv_path = Path(static_csv_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df_static = pd.read_csv(static_csv_path, encoding='utf-8-sig')

    # 合并坐标
    fence_pts = fence[['taz', 'center_x', 'center_y']].copy()
    fence_pts['taz'] = fence_pts['taz'].astype(int)
    df_static['taz'] = df_static['taz'].astype(int)

    df_home = df_static[df_static['人口类型'] == 'home'].merge(fence_pts, on='taz', how='inner')
    df_work = df_static[df_static['人口类型'] == 'work'].merge(fence_pts, on='taz', how='inner')

    # 投影坐标系（米）用于椭圆计算
    fence_proj = fence.copy()
    if fence_proj.crs and fence_proj.crs.is_geographic:
        fence_proj = fence_proj.to_crs(CRS_UTM)

    # 将经纬度中心点转为投影坐标
    from pyproj import Transformer
    transformer = Transformer.from_crs('EPSG:4326', CRS_UTM, always_xy=True)

    def _to_proj(df):
        x, y = transformer.transform(df['center_x'].values, df['center_y'].values)
        return np.column_stack([x, y]), df['人数'].values

    coords_home, w_home = _to_proj(df_home)
    coords_work, w_work = _to_proj(df_work)

    ell_home = compute_std_ellipse(coords_home, w_home)
    ell_work = compute_std_ellipse(coords_work, w_work)

    # 绘图
    fig, ax = plt.subplots(figsize=(14, 14))

    fence_proj.plot(ax=ax, color='#F5F5F5', edgecolor='#CCCCCC', linewidth=0.3, alpha=0.6)
    boundary = gpd.GeoSeries([unary_union(fence_proj.geometry)], crs=fence_proj.crs)
    boundary.boundary.plot(ax=ax, color='#333333', linewidth=1.5)

    # 居住地椭圆（蓝色）
    ax.plot(ell_home['ellipse_x'], ell_home['ellipse_y'],
            color='#2E7D9A', linewidth=5.0, label='居住地（O端）')
    ax.plot(ell_home['center_x'], ell_home['center_y'],
            'o', color='#2E7D9A', markersize=8)

    # 工作地椭圆（红色）
    ax.plot(ell_work['ellipse_x'], ell_work['ellipse_y'],
            color='#C65A4A', linewidth=5.0, linestyle='--', label='工作地（D端）')
    ax.plot(ell_work['center_x'], ell_work['center_y'],
            's', color='#C65A4A', markersize=8)

    bounds = fence_proj.total_bounds
    x_span = bounds[2] - bounds[0]
    y_span = bounds[3] - bounds[1]
    ax.set_xlim(bounds[0] - x_span * 0.02, bounds[2] + x_span * 0.06)
    ax.set_ylim(bounds[1] - y_span * 0.05, bounds[3] + y_span * 0.05)
    ax.set_aspect('equal', adjustable='box')

    ax.legend(
        prop={'family': 'SimHei', 'size': VISUAL_CONFIG['legend_fontsize']},
        loc='lower left',
        frameon=True, fancybox=True, shadow=True,
        edgecolor='#CCCCCC', facecolor='white', framealpha=0.95
    )

    right_edge_pos = 0.985
    _add_scalebar_auto(ax, fence_proj, label_fontsize=VISUAL_CONFIG['legend_fontsize'],
                       right_edge_pos=right_edge_pos)
    add_north_arrow(ax, right_edge_pos=right_edge_pos)
    ax.set_axis_off()
    plt.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.98)

    plt.savefig(output_path, dpi=VISUAL_CONFIG['dpi'],
                bbox_inches=None, pad_inches=0.15,
                facecolor='white', edgecolor='none')
    plt.close(fig)
    logger.info(f"标准差椭圆图已保存: {output_path}")


def plot_std_ellipse_flow(
    df_od: pd.DataFrame,
    fence: gpd.GeoDataFrame,
    output_path,
    o_col: str = 'o',
    d_col: str = 'd',
    value_col: str = '人数',
) -> None:
    """
    基于OD流绘制标准差椭圆（以OD对中点为坐标，人数为权重）。

    Args:
        df_od:       OD DataFrame（含o_col, d_col, value_col列）
        fence:       TAZ边界GeoDataFrame（含taz, center_x, center_y列）
        output_path: 输出PNG路径
        o_col:       起点列名
        d_col:       终点列名
        value_col:   权重列名（人数）
    """
    from .visualization import _prepare_map_for_plot, _add_scalebar_auto, add_north_arrow
    from pyproj import Transformer

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fence_pts = fence[['taz', 'center_x', 'center_y']].copy()
    fence_pts['taz'] = fence_pts['taz'].astype(int)

    df = df_od[[o_col, d_col, value_col]].copy()
    df[o_col] = df[o_col].astype(int)
    df[d_col] = df[d_col].astype(int)

    df = df.merge(fence_pts.rename(columns={'taz': o_col, 'center_x': 'o_x', 'center_y': 'o_y'}),
                  on=o_col, how='inner')
    df = df.merge(fence_pts.rename(columns={'taz': d_col, 'center_x': 'd_x', 'center_y': 'd_y'}),
                  on=d_col, how='inner')

    df['mid_lon'] = (df['o_x'] + df['d_x']) / 2
    df['mid_lat'] = (df['o_y'] + df['d_y']) / 2

    transformer = Transformer.from_crs('EPSG:4326', CRS_UTM, always_xy=True)
    mx, my = transformer.transform(df['mid_lon'].values, df['mid_lat'].values)
    coords = np.column_stack([mx, my])
    weights = df[value_col].values.astype(float)

    ell = compute_std_ellipse(coords, weights)

    fence_proj = fence.copy()
    if fence_proj.crs and fence_proj.crs.is_geographic:
        fence_proj = fence_proj.to_crs(CRS_UTM)

    fig, ax = plt.subplots(figsize=(14, 14))
    fence_proj.plot(ax=ax, color='#F5F5F5', edgecolor='#CCCCCC', linewidth=0.3, alpha=0.6)
    boundary = gpd.GeoSeries([unary_union(fence_proj.geometry)], crs=fence_proj.crs)
    boundary.boundary.plot(ax=ax, color='#333333', linewidth=1.5)

    ax.plot(ell['ellipse_x'], ell['ellipse_y'],
            color='#8B6914', linewidth=5.0, label='通勤流分布椭圆')
    ax.plot(ell['center_x'], ell['center_y'],
            'D', color='#8B6914', markersize=10)

    bounds = fence_proj.total_bounds
    x_span = bounds[2] - bounds[0]
    y_span = bounds[3] - bounds[1]
    ax.set_xlim(bounds[0] - x_span * 0.02, bounds[2] + x_span * 0.06)
    ax.set_ylim(bounds[1] - y_span * 0.05, bounds[3] + y_span * 0.05)
    ax.set_aspect('equal', adjustable='box')

    ax.legend(
        prop={'family': 'SimHei', 'size': VISUAL_CONFIG['legend_fontsize']},
        loc='lower left', frameon=True, fancybox=True, shadow=True,
        edgecolor='#CCCCCC', facecolor='white', framealpha=0.95
    )

    right_edge_pos = 0.985
    _add_scalebar_auto(ax, fence_proj, label_fontsize=VISUAL_CONFIG['legend_fontsize'],
                       right_edge_pos=right_edge_pos)
    add_north_arrow(ax, right_edge_pos=right_edge_pos)
    ax.set_axis_off()
    plt.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.98)

    plt.savefig(output_path, dpi=VISUAL_CONFIG['dpi'],
                bbox_inches=None, pad_inches=0.15,
                facecolor='white', edgecolor='none')
    plt.close(fig)
    logger.info(f"通勤流标准差椭圆图已保存: {output_path}")

    return {
        'semi_major': ell['semi_major'],
        'semi_minor': ell['semi_minor'],
        'angle_deg': ell['angle_deg'],
        'center_x': ell['center_x'],
        'center_y': ell['center_y'],
    }


def community_detection_tbd(
    df_od: pd.DataFrame,
    fence: gpd.GeoDataFrame,
    output_path,
    mapbox_token: str,
    bounds: list,
    zoom: int = 14,
    style: int = 6,
    o_col: str = 'o',
    d_col: str = 'd',
    value_col: str = '人数',
) -> dict:
    """
    使用igraph Louvain算法进行TAZ社区发现，输出HTML可视化和模块度报告。

    Args:
        df_od:        OD DataFrame
        fence:        TAZ边界GeoDataFrame（含taz, center_x, center_y列）
        output_path:  输出路径（.html），同时生成同名.png和_模块度报告.txt
        mapbox_token: Mapbox访问令牌
        bounds:       地图范围 [lon_min, lat_min, lon_max, lat_max]
        zoom:         地图缩放级别
        style:        transbigdata地图样式编号
        o_col:        起点列名
        d_col:        终点列名
        value_col:    边权重列名（人数）

    Returns:
        dict: {'modularity': float, 'n_communities': int, 'community_sizes': list}
    """
    try:
        import igraph as ig
    except ImportError:
        logger.error("igraph 未安装，请运行: pip install igraph")
        raise

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = df_od[[o_col, d_col, value_col]].copy()
    df[o_col] = df[o_col].astype(int)
    df[d_col] = df[d_col].astype(int)
    df = df[df[value_col] > 0]

    all_taz = sorted(set(df[o_col].tolist() + df[d_col].tolist()))
    taz_to_idx = {t: i for i, t in enumerate(all_taz)}

    edges = [(taz_to_idx[r[o_col]], taz_to_idx[r[d_col]]) for _, r in df.iterrows()]
    weights = df[value_col].tolist()

    g = ig.Graph(n=len(all_taz), edges=edges, directed=False)
    g.es['weight'] = weights

    g_clustered = g.community_multilevel(weights=g.es['weight'])
    modularity = g_clustered.modularity
    membership = g_clustered.membership
    n_communities = len(set(membership))
    community_sizes = sorted([membership.count(i) for i in range(n_communities)], reverse=True)

    taz_community = {taz: membership[idx] for taz, idx in taz_to_idx.items()}

    fence_copy = fence[['taz', 'center_x', 'center_y', 'geometry']].copy()
    fence_copy['taz'] = fence_copy['taz'].astype(int)
    fence_copy['community'] = fence_copy['taz'].map(taz_community)

    report_path = output_path.parent / (output_path.stem + '_模块度报告.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"社区发现结果报告\n")
        f.write(f"{'='*40}\n")
        f.write(f"算法: Louvain (igraph.community_multilevel)\n")
        f.write(f"节点数（TAZ）: {len(all_taz)}\n")
        f.write(f"边数（OD对）: {len(edges)}\n")
        f.write(f"模块度 (Modularity): {modularity:.6f}\n")
        f.write(f"社区数: {n_communities}\n")
        f.write(f"社区规模（TAZ数，降序）: {community_sizes[:20]}\n")
        f.write(f"最大社区TAZ数: {community_sizes[0]}\n")
        f.write(f"最小社区TAZ数: {community_sizes[-1]}\n")
    logger.info(f"社区发现模块度报告已保存: {report_path}")

    try:
        import transbigdata as tbd
        import plotly.express as px

        fence_proj = fence_copy.copy()
        if fence_proj.crs and fence_proj.crs.is_geographic:
            fence_proj_m = fence_proj.to_crs('EPSG:32649')
        else:
            fence_proj_m = fence_proj

        colors_list = px.colors.qualitative.Plotly + px.colors.qualitative.Set1
        n_colors = len(colors_list)
        fence_copy['color'] = fence_copy['community'].apply(
            lambda c: colors_list[int(c) % n_colors] if pd.notna(c) else '#CCCCCC'
        )

        import plotly.graph_objects as go
        fig = go.Figure()

        for comm_id in sorted(fence_copy['community'].dropna().unique()):
            subset = fence_copy[fence_copy['community'] == comm_id]
            for _, row in subset.iterrows():
                geom = row['geometry']
                if geom is None:
                    continue
                if geom.geom_type == 'Polygon':
                    polys = [geom]
                else:
                    polys = list(geom.geoms)
                for poly in polys:
                    xs, ys = poly.exterior.xy
                    fig.add_trace(go.Scattermapbox(
                        lon=list(xs), lat=list(ys),
                        mode='lines',
                        line=dict(color=row['color'], width=1),
                        fill='toself',
                        fillcolor=row['color'],
                        opacity=0.6,
                        showlegend=False,
                        hoverinfo='skip',
                    ))

        fig.update_layout(
            mapbox=dict(
                accesstoken=mapbox_token,
                style='light',
                center=dict(lon=(bounds[0]+bounds[2])/2, lat=(bounds[1]+bounds[3])/2),
                zoom=zoom - 4,
            ),
            margin=dict(l=0, r=0, t=0, b=0),
            width=1920, height=1080,
        )
        fig.write_html(str(output_path))
        logger.info(f"社区发现HTML已保存: {output_path}")

        png_path = output_path.parent / (output_path.stem + '.png')
        try:
            from .visualization import html_to_png
            html_to_png(output_path, png_path)
        except Exception as e:
            logger.warning(f"HTML转PNG失败: {e}")

    except ImportError as e:
        logger.warning(f"transbigdata/plotly 未安装，跳过可视化: {e}")

    return {
        'modularity': modularity,
        'n_communities': n_communities,
        'community_sizes': community_sizes,
    }
