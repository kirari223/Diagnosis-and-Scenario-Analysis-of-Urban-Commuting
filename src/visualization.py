"""
可视化模块
包含地图制图、图表生成等功能
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.colors import TwoSlopeNorm
from shapely.ops import unary_union

from .config import (
    VISUAL_CONFIG, MAP_ELEMENTS, COLOR_SCHEMES,
    get_result_path, CRS_WGS84, CRS_UTM
)
from .utils import StatsCollector, timer_decorator, logger

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def get_visual_config():
    """返回可视化参数配置"""
    return {
        'layout': VISUAL_CONFIG,
        'map_elements': MAP_ELEMENTS,
        'color_schemes': COLOR_SCHEMES
    }


def add_scalebar(ax, length, x_pos, y_pos, bar_height_ratio=0.08, label_fontsize=None, right_edge_pos=None):
    """
    添加比例尺。

    Args:
        ax: matplotlib axes
        length: 比例尺长度（与坐标系单位一致）
        x_pos: 默认模式下为比例尺左端在 x 方向的轴内相对位置（0-1）
        y_pos: 比例尺上边线在 y 方向的轴内相对位置（0-1）
        bar_height_ratio: 比例尺高度与长度之比
        label_fontsize: 比例尺数字字体大小；None 时使用 legend_fontsize
        right_edge_pos: 若不为 None，则将比例尺右端对齐到该轴内位置（0-1）
    """
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    y_pos_val = ylim[0] + (ylim[1] - ylim[0]) * y_pos
    x_range = xlim[1] - xlim[0]

    # 支持“按右端对齐”定位，便于与色带/指北针右侧边界统一。
    if right_edge_pos is not None:
        x_end = xlim[0] + x_range * right_edge_pos
        x_start = x_end - length
    else:
        x_start = xlim[0] + x_range * x_pos
        x_end = x_start + length

    bar_height = length * bar_height_ratio
    segment_len = length / 4
    label_fontsize = label_fontsize or VISUAL_CONFIG['legend_fontsize']

    for i in range(4):
        color = 'white' if i % 2 == 0 else 'black'
        ax.fill([x_start + i*segment_len, x_start + (i+1)*segment_len,
                x_start + (i+1)*segment_len, x_start + i*segment_len],
               [y_pos_val, y_pos_val, y_pos_val - bar_height, y_pos_val - bar_height],
               color=color, edgecolor='black', linewidth=1)

    ax.plot([x_start, x_end], [y_pos_val, y_pos_val], 'k-', linewidth=1)
    ax.plot([x_start, x_end], [y_pos_val - bar_height, y_pos_val - bar_height], 'k-', linewidth=1)
    ax.plot([x_start, x_start], [y_pos_val, y_pos_val - bar_height], 'k-', linewidth=1)
    ax.plot([x_end, x_end], [y_pos_val, y_pos_val - bar_height], 'k-', linewidth=1)

    # 左端标 0，右端标 10 km
    label_y = y_pos_val - bar_height * 1.8
    ax.text(x_start, label_y, '0',
            fontsize=label_fontsize,
            ha='center', va='top', fontweight='bold', color='black',
            bbox=dict(boxstyle='round,pad=0.1', facecolor='white', edgecolor='none', alpha=0.9))
    ax.text(x_end, label_y, '10 km',
            fontsize=label_fontsize,
            ha='center', va='top', fontweight='bold', color='black',
            bbox=dict(boxstyle='round,pad=0.1', facecolor='white', edgecolor='none', alpha=0.9))


def _add_scalebar_auto(ax, gdf, label_fontsize=None, right_edge_pos=None):
    """
    自动添加比例尺（处理地理坐标系和投影坐标系）

    Args:
        ax: matplotlib axes
        gdf: GeoDataFrame（用于判断坐标系）
    """
    length_m = MAP_ELEMENTS['scalebar_length']
    x_pos = MAP_ELEMENTS['scalebar_x']
    y_pos = MAP_ELEMENTS['scalebar_y']

    # 如果是地理坐标系（度），转换长度为度
    if gdf.crs and gdf.crs.is_geographic:
        # 在纬度28°附近，1度经度约等于98km
        length_deg = length_m / 98000
        add_scalebar(
            ax, length_deg, x_pos, y_pos,
            label_fontsize=label_fontsize, right_edge_pos=right_edge_pos
        )
    else:
        # 投影坐标系，直接使用米
        add_scalebar(
            ax, length_m, x_pos, y_pos,
            label_fontsize=label_fontsize, right_edge_pos=right_edge_pos
        )


def add_north_arrow(ax, x_pos=None, y_pos=None, size=None, right_edge_pos=None):
    """
    添加指北针

    Args:
        ax: matplotlib axes
        x_pos: x位置（0-1）
        y_pos: y位置（0-1）
        size: 大小
    """
    x_pos = x_pos or MAP_ELEMENTS['north_arrow_x']
    y_pos = y_pos or MAP_ELEMENTS['north_arrow_y']
    size = size or MAP_ELEMENTS['north_arrow_size']
    
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    y_center = ylim[0] + (ylim[1] - ylim[0]) * y_pos
    arrow_len = (ylim[1] - ylim[0]) * size
    x_range = xlim[1] - xlim[0]

    # right_edge_pos 用于将指北针最右端与其他元素右对齐。
    if right_edge_pos is not None:
        x_right = xlim[0] + x_range * right_edge_pos
        x_center = x_right - arrow_len * 0.15
    else:
        x_center = xlim[0] + x_range * x_pos
    
    # 北向三角形（黑色）
    triangle_n = plt.Polygon([
        [x_center, y_center + arrow_len*0.5],
        [x_center - arrow_len*0.15, y_center],
        [x_center + arrow_len*0.15, y_center]
    ], facecolor='black', edgecolor='black', linewidth=1)
    ax.add_patch(triangle_n)
    
    # 南向三角形（白色）
    triangle_s = plt.Polygon([
        [x_center, y_center - arrow_len*0.5],
        [x_center - arrow_len*0.15, y_center],
        [x_center + arrow_len*0.15, y_center]
    ], facecolor='white', edgecolor='black', linewidth=1)
    ax.add_patch(triangle_s)
    
    # N标签
    ax.text(x_center, y_center + arrow_len*0.65, 'N',
            ha='center', va='bottom', fontsize=VISUAL_CONFIG['label_fontsize'],
            fontweight='bold', color='black')


def _prepare_map_for_plot(gdf_data, gdf_base):
    """
    为绘图统一坐标系，避免在地理坐标(度)下等比例显示导致的视觉拉伸。

    Returns:
        tuple: (gdf_data_plot, gdf_base_plot)
    """
    if gdf_data.crs is None:
        logger.warning("gdf_data 缺少 CRS，跳过重投影，地图可能出现比例失真")
        return gdf_data, gdf_base

    target_crs = gdf_data.crs
    if gdf_data.crs.is_geographic:
        # 地理坐标系先转投影坐标系，保证 x/y 单位都是米。
        try:
            target_crs = gdf_data.estimate_utm_crs() or CRS_UTM
        except (ValueError, RuntimeError):
            target_crs = CRS_UTM
            logger.warning(f"自动估计 UTM 失败，使用默认投影 {CRS_UTM}")

    gdf_data_plot = gdf_data if gdf_data.crs == target_crs else gdf_data.to_crs(target_crs)

    if gdf_base.crs is None:
        logger.warning("gdf_base 缺少 CRS，按原坐标绘制底图")
        gdf_base_plot = gdf_base
    elif gdf_base.crs == target_crs:
        gdf_base_plot = gdf_base
    else:
        gdf_base_plot = gdf_base.to_crs(target_crs)

    return gdf_data_plot, gdf_base_plot


@timer_decorator
def create_choropleth_map(gdf_data, gdf_base, column, config_key, output_path=None,
                          title=None, save=True):
    """
    创建分级设色专题地图（单指标，使用固定分级）

    Args:
        gdf_data: 专题数据GeoDataFrame
        gdf_base: 底图GeoDataFrame
        column: 要可视化的列名
        config_key: 配色方案key（如'avg_distance', 'total_people'）
        output_path: 输出路径
        title: 地图标题（已废弃，不再显示）
        save: 是否保存

    Returns:
        matplotlib.figure.Figure: 图形对象
    """
    stats = StatsCollector("create_choropleth_map")
    stats.add('column', column)
    stats.add('config_key', config_key)
    stats.add('data_rows', len(gdf_data))

    config = COLOR_SCHEMES[config_key]
    gdf_data_plot, gdf_base_plot = _prepare_map_for_plot(gdf_data, gdf_base)

    # 使用正方形 figsize 避免横向拉伸
    fig, ax = plt.subplots(figsize=(14, 14))

    # 用底图范围统一显示窗口，避免因 gdf_data 缺失单元导致主图视觉偏移。
    bounds = gdf_base_plot.total_bounds
    x_span = bounds[2] - bounds[0]
    y_span = bounds[3] - bounds[1]
    # 左侧缩小留白、右侧增大留白（给右侧色带/注记），缓解主图整体右偏观感。
    margin_x_left = x_span * 0.01
    margin_x_right = x_span * 0.06
    margin_y = y_span * 0.05

    values = gdf_data_plot[column].values

    # 距离类指标：米转千米
    if config_key in ['avg_distance', 'diff_distance'] or 'distance' in column.lower() or '距离' in column:
        values = values / 1000.0

    valid_mask = ~np.isnan(values)
    valid_values = values[valid_mask]

    if len(valid_values) == 0:
        logger.warning(f"警告: {column} 没有有效数据")
        plt.close()
        return None

    stats.add('valid_values', len(valid_values))
    stats.add('value_min', valid_values.min())
    stats.add('value_max', valid_values.max())
    stats.add('value_mean', valid_values.mean())

    # 使用固定bins
    bins = config.get('bins', None)
    if bins is None:
        n_classes = len(config['colors'])
        quantiles = np.linspace(0, 100, n_classes + 1)
        bins = np.percentile(valid_values, quantiles)
        bins = np.unique(bins)
        n_classes = min(len(bins) - 1, len(config['colors']))
    else:
        bins = np.array(bins)
        n_classes = len(bins) - 1

    # 绘制底图
    gdf_base_plot.plot(ax=ax, color='#F5F5F5', edgecolor='#CCCCCC', linewidth=0.3, alpha=0.5)

    # 绘制专题图层
    for i in range(n_classes):
        if i == n_classes - 1:
            mask = (values >= bins[i]) & (values <= bins[i+1] + 1e-10)
        else:
            mask = (values >= bins[i]) & (values < bins[i+1])
        if mask.any():
            gdf_data_plot[mask].plot(
                ax=ax, color=config['colors'][i],
                edgecolor='white', linewidth=0.15, alpha=0.95
            )

    # 外边界
    boundary = gpd.GeoSeries([unary_union(gdf_data_plot.geometry)], crs=gdf_data_plot.crs)
    boundary.boundary.plot(ax=ax, color='#333333', linewidth=1.5, alpha=0.8)

    ax.set_xlim(bounds[0] - margin_x_left, bounds[2] + margin_x_right)
    ax.set_ylim(bounds[1] - margin_y, bounds[3] + margin_y)
    ax.set_aspect('equal', adjustable='box')

    # 图例固定在主图左下角（同轴显示），并压缩占图面积以减少遮挡。
    legend_elements = []
    for i in range(n_classes):
        if i == 0:
            label = f'≤ {bins[i+1]:.{config["decimals"]}f}'
        elif i == n_classes - 1:
            label = f'> {bins[i]:.{config["decimals"]}f}'
        else:
            label = f'{bins[i]:.{config["decimals"]}f} - {bins[i+1]:.{config["decimals"]}f}'
        legend_elements.append(mpatches.Patch(facecolor=config['colors'][i],
                                               edgecolor='#666666', linewidth=0.5, label=label))

    legend_title = f"{config['name']} ({config['unit']})"
    # 图例按 Figure 坐标定位：贴近画布左边缘，同时不需要把主图整体右移。
    legend_anchor_fig = (0.004, 0.012)
    fig.legend(
        handles=legend_elements,
        loc='lower left',
        bbox_to_anchor=legend_anchor_fig,
        bbox_transform=fig.transFigure,
        borderaxespad=0.0,
        title=legend_title,
        fontsize=VISUAL_CONFIG['legend_fontsize'],
        title_fontsize=VISUAL_CONFIG['label_fontsize'],
        frameon=True,
        fancybox=True,
        shadow=True,
        edgecolor='#CCCCCC',
        facecolor='white',
        framealpha=0.95
    )

    # 让比例尺与指北针按最右端统一对齐。
    right_edge_pos = 0.985
    _add_scalebar_auto(
        ax,
        gdf_data_plot,
        label_fontsize=VISUAL_CONFIG['legend_fontsize'],
        right_edge_pos=right_edge_pos
    )
    add_north_arrow(ax, right_edge_pos=right_edge_pos)

    ax.set_axis_off()
    # 主图维持满幅；图例左移由 Figure 锚点控制，而不是依赖增大主图左边距。
    plt.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.98)

    if save:
        if output_path is None:
            output_path = get_result_path('figures', f'map_{config_key}.png')

        # 不使用 tight 裁剪，避免导出时为“包住图例”而改变画布比例，造成横向拉伸观感。
        plt.savefig(
            output_path,
            dpi=VISUAL_CONFIG['dpi'],
            bbox_inches=None,
            pad_inches=0.15,
            facecolor='white',
            edgecolor='none'
        )
        logger.info(f"地图已保存: {output_path}")
        stats.add('output_path', str(output_path))

    stats.save('create_choropleth_map_stats.csv')

    return fig


@timer_decorator
def create_diverging_map(gdf_data, gdf_base, column, config_key=None, output_path=None,
                         title=None, save=True):
    """
    创建发散色阶专题地图（差值用）

    Args:
        gdf_data: 专题数据GeoDataFrame
        gdf_base: 底图GeoDataFrame
        column: 要可视化的列名
        config_key: 配色方案key（如'diff_distance', 'diff_people'），None 时自动推断
        output_path: 输出路径
        title: 地图标题
        save: 是否保存
    
    Returns:
        matplotlib.figure.Figure: 图形对象
    """
    stats = StatsCollector("create_diverging_map")
    stats.add('column', column)
    stats.add('data_rows', len(gdf_data))

    # 自动推断 config_key
    if config_key is None:
        if 'distance' in column.lower():
            config_key = 'diff_distance'
        elif 'ratio' in column.lower() or '比' in column:
            config_key = 'diff_ratio'
        else:
            config_key = 'diff_people'
    stats.add('config_key', config_key)

    config = COLOR_SCHEMES[config_key]
    gdf_data_plot, gdf_base_plot = _prepare_map_for_plot(gdf_data, gdf_base)

    # 图幅与 create_choropleth_map 保持一致。
    fig, ax = plt.subplots(figsize=(15.5, 14))

    bounds = gdf_data_plot.total_bounds
    # 左右对称增大边距，为主图与右侧色带之间留出更明显空隙，同时保持主图居中。
    margin_x = (bounds[2] - bounds[0]) * 0.1
    margin_y = (bounds[3] - bounds[1]) * 0.05

    values = gdf_data_plot[column].values.copy()

    # 距离类指标：米转千米
    if config_key == 'diff_distance' or 'distance' in column.lower() or '距离' in column:
        values = values / 1000.0

    valid_mask = ~np.isnan(values)
    valid_values = values[valid_mask]

    if len(valid_values) == 0:
        logger.warning(f"警告: {column} 没有有效数据")
        plt.close()
        return None

    stats.add('valid_values', len(valid_values))
    stats.add('value_min', valid_values.min())
    stats.add('value_max', valid_values.max())
    stats.add('value_mean', valid_values.mean())
    stats.add('positive_count', (valid_values > 0).sum())
    stats.add('negative_count', (valid_values < 0).sum())

    # 绘制底图
    gdf_base_plot.plot(ax=ax, color='#F5F5F5', edgecolor='#CCCCCC', linewidth=0.3, alpha=0.5)

    # 发散色阶
    vmin = valid_values.min()
    vmax = valid_values.max()

    abs_max = max(abs(vmin), abs(vmax))
    if abs_max == 0:
        abs_max = 1

    neg_colors = config.get('colors_neg', ['#0D47A1', '#1E88E5', '#90CAF9', '#E3F2FD'])
    pos_colors = config.get('colors_pos', ['#FFEBEE', '#EF9A9A', '#E53935', '#B71C1C'])

    all_colors = list(reversed(neg_colors)) + ['#FFFFFF'] + pos_colors
    cmap = LinearSegmentedColormap.from_list('diverging', all_colors, N=256)

    if vmin >= 0:
        norm = plt.Normalize(vmin=0, vmax=vmax)
    elif vmax <= 0:
        norm = plt.Normalize(vmin=vmin, vmax=0)
    else:
        norm = TwoSlopeNorm(vmin=-abs_max, vcenter=0, vmax=abs_max)

    # 绘制（用转换后的 values 列）
    gdf_plot = gdf_data_plot[valid_mask].copy()
    gdf_plot = gdf_plot.assign(_plot_val=values[valid_mask])
    gdf_plot.plot(ax=ax, column='_plot_val', cmap=cmap, norm=norm,
                  edgecolor='white', linewidth=0.15, alpha=0.95,
                  legend=False)

    # 外边界
    boundary = gpd.GeoSeries([unary_union(gdf_data_plot.geometry)], crs=gdf_data_plot.crs)
    boundary.boundary.plot(ax=ax, color='#333333', linewidth=1.5, alpha=0.8)

    ax.set_xlim(bounds[0] - margin_x, bounds[2] + margin_x)
    ax.set_ylim(bounds[1] - margin_y, bounds[3] + margin_y)
    ax.set_aspect('equal', adjustable='box')

    # 色带放在右侧并与比例尺、指北针右端对齐。
    colorbar_right_edge = 0.985
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    # 宽度保持旧版思路 0.020（x0 + w = 0.985）。
    cax = ax.inset_axes([0.965, 0.22, 0.020, 0.56])
    cax.set_facecolor((1, 1, 1, 0.9))
    cbar = fig.colorbar(sm, cax=cax, orientation='vertical')
    cbar.set_label(f"{config['name']} ({config['unit']})",
                   fontsize=VISUAL_CONFIG['label_fontsize'], fontweight='bold')
    cbar.ax.tick_params(labelsize=VISUAL_CONFIG['legend_fontsize'])
    cbar.ax.yaxis.set_ticks_position('right')
    cbar.ax.yaxis.set_label_position('right')

    # 比例尺/指北针/色带三者统一按“最右端”对齐。
    _add_scalebar_auto(
        ax,
        gdf_data_plot,
        label_fontsize=VISUAL_CONFIG['legend_fontsize'],
        right_edge_pos=colorbar_right_edge
    )
    add_north_arrow(ax, right_edge_pos=colorbar_right_edge)

    ax.set_axis_off()
    plt.subplots_adjust(left=0, right=0.96, bottom=0.02, top=0.98)

    if save:
        if output_path is None:
            output_path = get_result_path('figures', f'map_{config_key}.png')

        # 不做 tight 裁剪，保持固定画布比例，避免导出后观感横向拉伸。
        plt.savefig(
            output_path,
            dpi=VISUAL_CONFIG['dpi'],
            bbox_inches=None,
            pad_inches=0.15,
            facecolor='white',
            edgecolor='none'
        )
        logger.info(f"地图已保存: {output_path}")
        stats.add('output_path', str(output_path))

    stats.save('create_diverging_map_stats.csv')
    
    return fig


@timer_decorator
def create_comparison_maps(gdf_list, names, gdf_base, column, config_key,
                           output_dir=None, title_prefix=''):
    """
    创建多个格局的对比地图
    
    Args:
        gdf_list: GeoDataFrame列表
        names: 格局名称列表
        gdf_base: 底图
        column: 要可视化的列
        config_key: 配色方案
        output_dir: 输出目录
        title_prefix: 标题前缀
    
    Returns:
        list: 生成的文件路径列表
    """
    stats = StatsCollector("create_comparison_maps")
    stats.add('map_count', len(gdf_list))
    stats.add('names', ', '.join(names))
    
    output_files = []
    
    for gdf, name in zip(gdf_list, names):
        title = f"{title_prefix}{name}" if title_prefix else name
        
        if output_dir:
            output_path = f"{output_dir}/map_{config_key}_{name}.png"
        else:
            output_path = get_result_path('figures', f'map_{config_key}_{name}.png')
        
        fig = create_choropleth_map(
            gdf_data=gdf,
            gdf_base=gdf_base,
            column=column,
            config_key=config_key,
            output_path=output_path,
            title=title
        )
        
        if fig:
            output_files.append(output_path)
        plt.close(fig)
    
    stats.add('output_files', ', '.join(output_files))
    stats.save('create_comparison_maps_stats.csv')
    
    return output_files


@timer_decorator
def create_diff_maps(gdf_diff, gdf_base, indicator_cols=None, 
                     name_a='A', name_b='B', output_dir=None):
    """
    创建差值地图
    
    Args:
        gdf_diff: 差值GeoDataFrame
        gdf_base: 底图
        indicator_cols: 指标列列表
        name_a: 格局A名称
        name_b: 格局B名称
        output_dir: 输出目录
    
    Returns:
        list: 生成的文件路径列表
    """
    if indicator_cols is None:
        indicator_cols = ['总通勤人数', '平均通勤距离', '内部通勤比']
    
    stats = StatsCollector("create_diff_maps")
    stats.add('indicator_count', len(indicator_cols))
    
    config_map = {
        '总通勤人数': 'diff_people',
        '平均通勤距离': 'diff_distance',
        '内部通勤比': 'diff_ratio'
    }
    
    output_files = []
    
    for col in indicator_cols:
        diff_col = f'{col}_diff'
        config_key = config_map.get(col, 'diff_distance')
        
        if diff_col not in gdf_diff.columns:
            logger.warning(f"列 {diff_col} 不存在，跳过")
            continue
        
        title = f"{col}差值 ({name_a} - {name_b})"
        
        if output_dir:
            output_path = f"{output_dir}/map_diff_{col}_{name_a}_vs_{name_b}.png"
        else:
            output_path = get_result_path('figures', f'map_diff_{col}_{name_a}_vs_{name_b}.png')
        
        fig = create_diverging_map(
            gdf_data=gdf_diff,
            gdf_base=gdf_base,
            column=diff_col,
            config_key=config_key,
            output_path=output_path,
            title=title
        )
        
        if fig:
            output_files.append(output_path)
        plt.close(fig)
    
    stats.add('output_files', ', '.join(output_files))
    stats.save('create_diff_maps_stats.csv')
    
    return output_files


def create_summary_chart(stats_dict, output_path=None):
    """
    创建汇总统计图表
    
    Args:
        stats_dict: 统计信息字典
        output_path: 输出路径
    
    Returns:
        matplotlib.figure.Figure: 图形对象
    """
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # 这里可以根据实际统计信息创建图表
    # 示例：创建简单的柱状图
    
    plt.tight_layout()
    
    if output_path is not None:
        plt.savefig(output_path, dpi=VISUAL_CONFIG['dpi'],
                    bbox_inches='tight', facecolor='white')
        logger.info(f"汇总图表已保存: {output_path}")

    return fig


@timer_decorator
def create_flowline(
    df_od: pd.DataFrame,
    fence: gpd.GeoDataFrame,
    output_path,
    title: str = '',
    flow_col: str = '人数',
    o_col: str = 'o',
    d_col: str = 'd',
    top_n: int = 500,
    is_diff: bool = False,
    cmap_single: str = 'YlOrRd',
    linewidth_min: float = 0.5,
    linewidth_max: float = 8.0,
    alpha_min: float = 0.3,
    alpha_max: float = 0.9,
) -> None:
    """
    绘制 OD 流线图或差值流线图。
    线宽和透明度均根据流量大小动态调整：流量大→线宽大、不透明；流量小→线宽小、透明。

    Args:
        df_od: OD 数据，含 o_col, d_col, flow_col 列
        fence: TAZ 空间边界 GeoDataFrame
        output_path: 输出路径
        title: 图面标题（留空则不显示）
        flow_col: 流量列名
        o_col: 起点列名
        d_col: 终点列名
        top_n: 绘制流量绝对值最大的前 N 条 OD
        is_diff: True 时使用发散色阶（RdBu_r + TwoSlopeNorm），False 时使用单色阶
        cmap_single: 单格局模式的色阶名称
        linewidth_min: 最小线宽
        linewidth_max: 最大线宽
        alpha_min: 最小透明度（流量小时）
        alpha_max: 最大透明度（流量大时）
    """
    from matplotlib.collections import LineCollection
    from matplotlib.colors import Normalize
    from pathlib import Path

    # 构建 TAZ 中心点坐标字典
    fence_proj = fence.copy()
    if fence_proj.crs and fence_proj.crs.is_geographic:
        fence_proj = fence_proj.to_crs('EPSG:32649')
    centroids = fence_proj.geometry.centroid

    # 尝试用第一列作为 TAZ ID
    taz_col = fence.columns[0]
    taz_ids = fence[taz_col].values
    coord_dict = {tid: (c.x, c.y) for tid, c in zip(taz_ids, centroids)}

    df = df_od[[o_col, d_col, flow_col]].copy().dropna()
    df = df[df[o_col].isin(coord_dict) & df[d_col].isin(coord_dict)]

    # 筛选 top_n
    df = df.reindex(df[flow_col].abs().nlargest(top_n).index)

    if df.empty:
        logger.warning("create_flowline: 无有效 OD 数据，跳过绘图")
        return

    flows = df[flow_col].values
    abs_flows = np.abs(flows)
    flow_min, flow_max = abs_flows.min(), abs_flows.max()
    if flow_max == flow_min:
        flow_max = flow_min + 1

    # 线宽映射：流量大→线宽大
    lw = linewidth_min + (abs_flows - flow_min) / (flow_max - flow_min) * (linewidth_max - linewidth_min)

    # 透明度映射：流量大→不透明（alpha_max），流量小→透明（alpha_min）
    alphas = alpha_min + (abs_flows - flow_min) / (flow_max - flow_min) * (alpha_max - alpha_min)

    # 构建线段
    segments = []
    for _, row in df.iterrows():
        o_xy = coord_dict[row[o_col]]
        d_xy = coord_dict[row[d_col]]
        segments.append([o_xy, d_xy])

    # 颜色映射
    if is_diff:
        abs_max = float(np.abs(flows).max())
        if abs_max == 0:
            abs_max = 1
        norm = TwoSlopeNorm(vmin=-abs_max, vcenter=0, vmax=abs_max)
        cmap = plt.cm.get_cmap('RdBu_r')
        color_vals = flows
    else:
        norm = Normalize(vmin=flow_min, vmax=flow_max)
        cmap = plt.cm.get_cmap(cmap_single)
        color_vals = abs_flows

    colors = cmap(norm(color_vals))

    fig, ax = plt.subplots(figsize=VISUAL_CONFIG['figure_size'])

    # 底图
    fence_proj.plot(ax=ax, color='#F5F5F5', edgecolor='#CCCCCC', linewidth=0.3)
    boundary = gpd.GeoSeries([unary_union(fence_proj.geometry)])
    boundary.boundary.plot(ax=ax, color='#333333', linewidth=1.5)

    # 流线（逐条绘制以支持不同透明度）
    for i, (seg, color, width, alpha) in enumerate(zip(segments, colors, lw, alphas)):
        lc = LineCollection([seg], colors=[color], linewidths=[width], alpha=alpha)
        ax.add_collection(lc)

    # colorbar（颜色图例）
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.6, aspect=20, pad=0.02)
    cbar.set_label(flow_col, fontsize=VISUAL_CONFIG['label_fontsize'], fontweight='bold')
    cbar.ax.tick_params(labelsize=VISUAL_CONFIG['legend_fontsize'])

    # 线宽图例（手动添加）
    lw_legend_elements = []
    lw_bins = [flow_min, (flow_min + flow_max) / 2, flow_max]
    lw_labels = [f'{int(v)}' for v in lw_bins]
    lw_widths = [linewidth_min, (linewidth_min + linewidth_max) / 2, linewidth_max]

    for label, width in zip(lw_labels, lw_widths):
        lw_legend_elements.append(plt.Line2D([0], [0], color='black', linewidth=width, label=label))

    legend = ax.legend(handles=lw_legend_elements, loc='lower left',
                      bbox_to_anchor=(0.0, 0.0),
                      title=f'{flow_col} (线宽)',
                      fontsize=VISUAL_CONFIG['legend_fontsize'],
                      title_fontsize=VISUAL_CONFIG['label_fontsize'],
                      frameon=True, fancybox=True, shadow=True,
                      edgecolor='#CCCCCC', facecolor='white', framealpha=0.95)

    ax.set_axis_off()
    _add_scalebar_auto(ax, fence)
    add_north_arrow(ax)
    plt.tight_layout()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=VISUAL_CONFIG['dpi'],
                bbox_inches='tight', facecolor='white')
    plt.close(fig)
    logger.info(f"流线图已保存: {output_path}")


@timer_decorator
def create_distribution_plot(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    name_a: str,
    name_b: str,
    output_path,
    col: str = '人数',
    title: str = '',
    cap: float = 200.0,
) -> None:
    """
    绘制两个格局的分布对比箱线图。

    Args:
        df_a: 格局 A 的 OD 数据
        df_b: 格局 B 的 OD 数据
        name_a: 格局 A 名称（x 轴标签）
        name_b: 格局 B 名称（x 轴标签）
        output_path: 输出路径
        col: 对比列名（如 '人数' 或 'distance'）
        title: 图面标题（留空则不显示）
        cap: 截尾阈值，只保留 col <= cap 的行（None 表示不截尾）
    """
    from pathlib import Path

    def _extract(df):
        if col not in df.columns:
            return np.array([])
        s = df[col].dropna()
        if cap is not None:
            s = s[s <= cap]
        return s.values

    data_a = _extract(df_a)
    data_b = _extract(df_b)

    fig, ax = plt.subplots(figsize=(10, 7))

    bp = ax.boxplot(
        [data_a, data_b],
        labels=[name_a, name_b],
        patch_artist=True,
        vert=False,
        medianprops=dict(color='black', linewidth=2),
        whiskerprops=dict(linewidth=1.5),
        capprops=dict(linewidth=1.5),
        flierprops=dict(marker='o', markersize=3, alpha=0.4),
    )

    colors_bp = ['#2E7D9A', '#C65A4A']
    for patch, color in zip(bp['boxes'], colors_bp):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    ax.set_xlabel(col, fontsize=24, fontfamily='SimHei')
    ax.tick_params(axis='both', labelsize=24)
    for label in ax.get_yticklabels():
        label.set_fontfamily('SimHei')
        label.set_fontsize(24)

    if title:
        ax.set_title(title, fontsize=VISUAL_CONFIG['title_fontsize'],
                     fontweight='bold', color='#333333')

    ax.grid(True, axis='x', alpha=0.3)
    plt.tight_layout()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=VISUAL_CONFIG['dpi'],
                bbox_inches='tight', facecolor='white')
    plt.close(fig)
    logger.info(f"箱线图已保存: {output_path}")


@timer_decorator
def create_distance_pdf(
    df_list: list,
    names: list,
    output_path,
    col: str = 'distance',
    weight_col: str = None,
    cap_quantile: float = None,
    cap_abs: float = None,
    unit_scale: float = None,
    x_label: str = None,
    distance_col: str = 'distance',
    title: str = '',
    bins: int = 80,
) -> None:
    """
    绘制多个格局的概率密度分布对比图（核密度估计）。

    Args:
        df_list: OD DataFrame 列表
        names: 各格局名称列表，与 df_list 一一对应
        output_path: 输出路径
        col: 要可视化的列名（如 'distance' 或 'people'）
        weight_col: 加权列名（None=等权，传入列名则按该列加权 KDE）
        cap_quantile: 按分位数截尾（如 0.8 保留 80% 分布）
        cap_abs: 按绝对值截尾（如 20000 米）
        unit_scale: 单位换算系数（如 1/1000 米→千米）
        x_label: x 轴标签（None 时自动推断）
        distance_col: 旧参数名，向后兼容
        title: 图面标题
        bins: 直方图分箱数（用于背景参考）
    """
    from pathlib import Path
    from scipy.stats import gaussian_kde

    # 向后兼容：若 col='distance' 且 distance_col 有值则用 distance_col
    if col == 'distance' and distance_col != 'distance':
        col = distance_col

    colors = ['#2E7D9A', '#C65A4A', '#4A8F4A', '#8B6914']
    fig, ax = plt.subplots(figsize=(12, 7))

    for df, name, color in zip(df_list, names, colors):
        if col not in df.columns:
            logger.warning(f"create_distance_pdf: 列 {col} 不在 {name} 中，跳过")
            continue

        # 截尾逻辑
        mask_valid = df[col].notna()
        if cap_quantile is not None:
            threshold = df.loc[mask_valid, col].quantile(cap_quantile)
            mask_valid = mask_valid & (df[col] <= threshold)
        elif cap_abs is not None:
            mask_valid = mask_valid & (df[col] <= cap_abs)

        data = df.loc[mask_valid, col].values.astype(float)
        if len(data) == 0:
            logger.warning(f"create_distance_pdf: {name} 截尾后无有效数据")
            continue

        # 单位换算
        if unit_scale is not None:
            data = data * unit_scale

        # 加权 KDE
        if weight_col is not None and weight_col in df.columns:
            weights = df.loc[mask_valid, weight_col].values.astype(float)
            weights = weights / weights.sum()
            kde = gaussian_kde(data, weights=weights, bw_method='scott')
        else:
            kde = gaussian_kde(data, bw_method='scott')

        x_range = np.linspace(data.min(), data.max(), 500)
        ax.plot(x_range, kde(x_range), color=color, linewidth=2.5, label=name)
        ax.fill_between(x_range, kde(x_range), alpha=0.12, color=color)

    # x 轴标签自动推断
    if x_label is None:
        if col == 'distance' or 'distance' in col.lower():
            x_label = '通勤距离 (km)' if unit_scale == 1/1000 else '通勤距离 (m)'
        elif 'people' in col.lower() or '人数' in col:
            x_label = 'OD 对通勤人数 (人)'
        else:
            x_label = col

    ax.set_xlabel(x_label, fontsize=VISUAL_CONFIG['label_fontsize'], fontfamily='SimHei')
    ax.set_ylabel('概率密度', fontsize=VISUAL_CONFIG['label_fontsize'], fontfamily='SimHei')
    ax.tick_params(axis='both', labelsize=VISUAL_CONFIG['legend_fontsize'])
    ax.legend(prop={'family': 'SimHei', 'size': VISUAL_CONFIG['legend_fontsize']})
    ax.grid(True, alpha=0.3)

    if title:
        ax.set_title(title, fontsize=VISUAL_CONFIG['title_fontsize'],
                     fontweight='bold', color='#333333')

    plt.tight_layout()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=VISUAL_CONFIG['dpi'],
                bbox_inches='tight', facecolor='white')
    plt.close(fig)
    logger.info(f"PDF图已保存: {output_path}")


@timer_decorator
def create_street_choropleth(
    gdf_street: gpd.GeoDataFrame,
    gdf_taz_boundary: gpd.GeoDataFrame,
    column: str,
    config_key: str,
    output_path,
    title: str = '',
) -> None:
    """
    绘制街道级分级设色图，外边界用 TAZ 边界，内部用街道边界分色。

    Args:
        gdf_street:       街道级 GeoDataFrame（含 column 列，EPSG:32649）
        gdf_taz_boundary: TAZ 边界 GeoDataFrame（用于外边界裁剪显示）
        column:           要可视化的列名
        config_key:       COLOR_SCHEMES 中的配色方案 key
        output_path:      输出 PNG 路径
        title:            图面标题（留空则不显示）
    """
    from pathlib import Path

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    config = COLOR_SCHEMES[config_key]

    # 统一 CRS
    if gdf_taz_boundary.crs != gdf_street.crs:
        gdf_taz_boundary = gdf_taz_boundary.to_crs(gdf_street.crs)

    values = gdf_street[column].values
    valid_mask = ~np.isnan(values.astype(float))
    valid_values = values[valid_mask].astype(float)

    if len(valid_values) == 0:
        logger.warning(f"create_street_choropleth: {column} 无有效数据，跳过")
        return

    bins = np.array(config.get('bins', []))
    n_classes = len(bins) - 1

    fig, ax = plt.subplots(figsize=(14, 14))

    # TAZ 底图（浅灰）
    gdf_taz_boundary.plot(ax=ax, color='#F5F5F5', edgecolor='#DDDDDD', linewidth=0.2, alpha=0.5)

    # 街道分级设色
    for i in range(n_classes):
        if i == n_classes - 1:
            mask = (values.astype(float) >= bins[i]) & (values.astype(float) <= bins[i + 1] + 1e-10)
        else:
            mask = (values.astype(float) >= bins[i]) & (values.astype(float) < bins[i + 1])
        if mask.any():
            gdf_street[mask].plot(
                ax=ax, color=config['colors'][i],
                edgecolor='white', linewidth=0.5, alpha=0.9
            )

    # 街道边界线
    gdf_street.boundary.plot(ax=ax, color='#888888', linewidth=0.6, alpha=0.7)

    # TAZ 外边界
    boundary = gpd.GeoSeries([unary_union(gdf_taz_boundary.geometry)], crs=gdf_taz_boundary.crs)
    boundary.boundary.plot(ax=ax, color='#333333', linewidth=1.8, alpha=0.9)

    bounds = gdf_taz_boundary.total_bounds
    x_span = bounds[2] - bounds[0]
    y_span = bounds[3] - bounds[1]
    ax.set_xlim(bounds[0] - x_span * 0.01, bounds[2] + x_span * 0.06)
    ax.set_ylim(bounds[1] - y_span * 0.05, bounds[3] + y_span * 0.05)
    ax.set_aspect('equal', adjustable='box')

    # 图例
    legend_elements = []
    for i in range(n_classes):
        if i == 0:
            label = f'≤ {bins[i+1]:.{config["decimals"]}f}'
        elif i == n_classes - 1:
            label = f'> {bins[i]:.{config["decimals"]}f}'
        else:
            label = f'{bins[i]:.{config["decimals"]}f} - {bins[i+1]:.{config["decimals"]}f}'
        legend_elements.append(mpatches.Patch(
            facecolor=config['colors'][i], edgecolor='#666666', linewidth=0.5, label=label
        ))

    legend_title = f"{config['name']}" + (f" ({config['unit']})" if config.get('unit') else '')
    fig.legend(
        handles=legend_elements,
        loc='lower left',
        bbox_to_anchor=(0.004, 0.012),
        bbox_transform=fig.transFigure,
        borderaxespad=0.0,
        title=legend_title,
        fontsize=VISUAL_CONFIG['legend_fontsize'],
        title_fontsize=VISUAL_CONFIG['label_fontsize'],
        frameon=True, fancybox=True, shadow=True,
        edgecolor='#CCCCCC', facecolor='white', framealpha=0.95
    )

    right_edge_pos = 0.985
    _add_scalebar_auto(ax, gdf_street, label_fontsize=VISUAL_CONFIG['legend_fontsize'],
                       right_edge_pos=right_edge_pos)
    add_north_arrow(ax, right_edge_pos=right_edge_pos)

    if title:
        ax.set_title(title, fontsize=VISUAL_CONFIG['title_fontsize'],
                     fontweight='bold', color='#333333')

    ax.set_axis_off()
    plt.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.98)

    plt.savefig(output_path, dpi=VISUAL_CONFIG['dpi'],
                bbox_inches=None, pad_inches=0.15,
                facecolor='white', edgecolor='none')
    plt.close(fig)
    logger.info(f"街道分级设色图已保存: {output_path}")


def create_pie_chart(
    data_dict: dict,
    output_path,
    title: str = '',
    colors: list = None,
) -> None:
    """
    绘制饼图（时长区间占比、交通方式占比）。

    Args:
        data_dict:   {标签: 数值} 字典
        output_path: 输出PNG路径
        title:       图标题
        colors:      颜色列表，None时使用默认配色
    """
    from pathlib import Path

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    labels = list(data_dict.keys())
    values = [float(v) for v in data_dict.values()]

    if colors is None:
        colors = ['#2E7D9A', '#C65A4A', '#4A8F4A', '#8B6914', '#7B3F9E',
                  '#1A6B4A', '#D4A017', '#5C3317'][:len(labels)]

    fig, ax = plt.subplots(figsize=(10, 8))
    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        colors=colors,
        autopct='%1.1f%%',
        startangle=90,
        pctdistance=0.8,
        textprops={'fontfamily': 'SimHei', 'fontsize': VISUAL_CONFIG['legend_fontsize']},
    )
    for autotext in autotexts:
        autotext.set_fontsize(VISUAL_CONFIG['legend_fontsize'])
        autotext.set_fontweight('bold')

    if title:
        ax.set_title(title, fontsize=VISUAL_CONFIG['title_fontsize'],
                     fontweight='bold', fontfamily='SimHei', pad=20)

    plt.tight_layout()
    plt.savefig(output_path, dpi=VISUAL_CONFIG['dpi'],
                bbox_inches='tight', facecolor='white')
    plt.close(fig)
    logger.info(f"饼图已保存: {output_path}")


def create_blank_taz_map(
    fence: gpd.GeoDataFrame,
    output_path,
) -> None:
    """
    绘制空白TAZ底图（无数据设色，只显示边界线、指北针、比例尺）。

    Args:
        fence:       TAZ边界GeoDataFrame
        output_path: 输出PNG路径
    """
    from pathlib import Path

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fence_plot, _ = _prepare_map_for_plot(fence, fence)

    fig, ax = plt.subplots(figsize=(14, 14))

    fence_plot.plot(ax=ax, color='#F5F5F5', edgecolor='#888888', linewidth=0.5, alpha=0.8)

    boundary = gpd.GeoSeries([unary_union(fence_plot.geometry)], crs=fence_plot.crs)
    boundary.boundary.plot(ax=ax, color='#333333', linewidth=2.0)

    bounds = fence_plot.total_bounds
    x_span = bounds[2] - bounds[0]
    y_span = bounds[3] - bounds[1]
    ax.set_xlim(bounds[0] - x_span * 0.02, bounds[2] + x_span * 0.06)
    ax.set_ylim(bounds[1] - y_span * 0.05, bounds[3] + y_span * 0.05)
    ax.set_aspect('equal', adjustable='box')

    right_edge_pos = 0.985
    _add_scalebar_auto(ax, fence_plot, label_fontsize=VISUAL_CONFIG['legend_fontsize'],
                       right_edge_pos=right_edge_pos)
    add_north_arrow(ax, right_edge_pos=right_edge_pos)
    ax.set_axis_off()
    plt.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.98)

    plt.savefig(output_path, dpi=VISUAL_CONFIG['dpi'],
                bbox_inches=None, pad_inches=0.15,
                facecolor='white', edgecolor='none')
    plt.close(fig)
    logger.info(f"空白TAZ底图已保存: {output_path}")


def html_to_png(
    html_path,
    png_path,
    width: int = 1920,
    height: int = 1080,
    wait_seconds: int = 3,
) -> None:
    """
    将HTML文件截图转为PNG（使用playwright）。

    Args:
        html_path:    HTML文件路径
        png_path:     输出PNG路径
        width:        截图宽度（像素）
        height:       截图高度（像素）
        wait_seconds: 等待页面加载的秒数
    """
    from pathlib import Path

    html_path = Path(html_path)
    png_path = Path(png_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': width, 'height': height})
            page.goto(f'file:///{html_path.as_posix()}')
            page.wait_for_timeout(wait_seconds * 1000)
            page.screenshot(path=str(png_path), full_page=False)
            browser.close()
        logger.info(f"HTML转PNG已保存: {png_path}")
    except ImportError:
        logger.error("playwright 未安装，请运行: pip install playwright && playwright install chromium")
        raise


def create_od_flowmap_tbd(
    df_od: pd.DataFrame,
    fence: gpd.GeoDataFrame,
    output_path,
    mapbox_token: str,
    bounds: list,
    zoom: int = 14,
    style: int = 6,
    top_n: int = 500,
    o_col: str = 'o',
    d_col: str = 'd',
    value_col: str = '人数',
) -> None:
    """
    使用transbigdata绘制交互式OD流线图，输出HTML和PNG。

    Args:
        df_od:         OD DataFrame（含o_col, d_col, value_col列）
        fence:         TAZ边界GeoDataFrame（含taz, center_x, center_y列）
        output_path:   输出路径（.html），同时生成同名.png
        mapbox_token:  Mapbox访问令牌
        bounds:        地图范围 [lon_min, lat_min, lon_max, lat_max]
        zoom:          地图缩放级别
        style:         transbigdata地图样式编号
        top_n:         显示流量最大的前N条OD对
        o_col:         起点列名
        d_col:         终点列名
        value_col:     流量列名
    """
    from pathlib import Path

    try:
        import transbigdata as tbd
    except ImportError:
        logger.error("transbigdata 未安装，请运行: pip install transbigdata")
        raise

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fence_pts = fence[['taz', 'center_x', 'center_y']].copy()
    fence_pts['taz'] = fence_pts['taz'].astype(int)

    df = df_od[[o_col, d_col, value_col]].copy()
    df[o_col] = df[o_col].astype(int)
    df[d_col] = df[d_col].astype(int)
    df = df.nlargest(top_n, value_col)

    df = df.merge(fence_pts.rename(columns={'taz': o_col, 'center_x': 'o_lon', 'center_y': 'o_lat'}),
                  on=o_col, how='inner')
    df = df.merge(fence_pts.rename(columns={'taz': d_col, 'center_x': 'd_lon', 'center_y': 'd_lat'}),
                  on=d_col, how='inner')

    import plotly.graph_objects as go

    fig = go.Figure()

    val_min = df[value_col].min()
    val_max = df[value_col].max()
    if val_max == val_min:
        val_max = val_min + 1

    for _, row in df.iterrows():
        norm = (row[value_col] - val_min) / (val_max - val_min)
        width = 1.0 + norm * 5.0
        alpha = 0.3 + norm * 0.6
        fig.add_trace(go.Scattermapbox(
            lon=[row['o_lon'], row['d_lon']],
            lat=[row['o_lat'], row['d_lat']],
            mode='lines',
            line=dict(width=width, color=f'rgba(46,125,154,{alpha:.2f})'),
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
    logger.info(f"OD流线图HTML已保存: {output_path}")

    png_path = output_path.parent / (output_path.stem + '.png')
    try:
        html_to_png(output_path, png_path)
    except Exception as e:
        logger.warning(f"HTML转PNG失败: {e}")

