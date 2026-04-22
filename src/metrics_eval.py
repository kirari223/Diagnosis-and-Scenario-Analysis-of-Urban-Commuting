"""
指标评估模块
包含TAZ指标计算、统计信息、差值分析等功能
"""
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd

from .utils import StatsCollector, timer_decorator, logger


@timer_decorator
def compute_taz_indicators(df_od, fence, o_col='o', d_col='d', 
                           value_col='人数', distance_col='distance'):
    """
    从OD数据计算每个TAZ的指标
    
    计算指标：
    - 总通勤人数（以该TAZ为起点的总人数）
    - 平均通勤距离（加权平均）
    - 内部通勤比（o==d的人数占比）
    
    Args:
        df_od: OD数据DataFrame
        fence: GeoDataFrame空间数据
        o_col: 起点列名
        d_col: 终点列名
        value_col: 人数列名
        distance_col: 距离列名
    
    Returns:
        gpd.GeoDataFrame: 包含指标的空间数据
    """
    stats = StatsCollector("compute_taz_indicators")
    stats.add('input_rows', len(df_od))
    stats.add('fence_rows', len(fence))
    
    # 按起点o聚合 - 总人数
    total_people = df_od.groupby(o_col)[value_col].sum().reset_index()
    total_people.columns = ['taz', '总通勤人数']
    
    # 内部通勤人数
    internal = df_od[df_od[o_col] == df_od[d_col]].groupby(o_col)[value_col].sum().reset_index()
    internal.columns = ['taz', '内部通勤人数']
    
    # 加权平均距离
    df_od_valid = df_od[df_od[distance_col].notna() & (df_od[value_col] > 0)].copy()
    df_od_valid['weighted_dist'] = df_od_valid[value_col] * df_od_valid[distance_col]
    
    weighted = df_od_valid.groupby(o_col).agg(
        sum_weighted_dist=('weighted_dist', 'sum'),
        sum_people=(value_col, 'sum')
    ).reset_index()
    weighted['平均通勤距离'] = weighted['sum_weighted_dist'] / weighted['sum_people']
    weighted = weighted[[o_col, '平均通勤距离']].rename(columns={o_col: 'taz'})
    
    # 合并
    result = total_people.merge(internal, on='taz', how='left')
    result = result.merge(weighted, on='taz', how='left')
    result['内部通勤人数'] = result['内部通勤人数'].fillna(0)
    result['内部通勤比'] = result['内部通勤人数'] / result['总通勤人数'] * 100
    
    # 添加更多指标
    # 标准差
    std_dist = df_od_valid.groupby(o_col)[distance_col].std().reset_index()
    std_dist.columns = ['taz', '通勤距离标准差']
    result = result.merge(std_dist, on='taz', how='left')
    
    # 中位数距离
    median_dist = df_od_valid.groupby(o_col)[distance_col].median().reset_index()
    median_dist.columns = ['taz', '通勤距离中位数']
    result = result.merge(median_dist, on='taz', how='left')
    
    # 最大/最小距离
    max_dist = df_od_valid.groupby(o_col)[distance_col].max().reset_index()
    max_dist.columns = ['taz', '最大通勤距离']
    result = result.merge(max_dist, on='taz', how='left')
    
    min_dist = df_od_valid.groupby(o_col)[distance_col].min().reset_index()
    min_dist.columns = ['taz', '最小通勤距离']
    result = result.merge(min_dist, on='taz', how='left')
    
    # 与fence关联
    result['taz'] = result['taz'].astype(int)
    fence_copy = fence[['taz', 'geometry']].copy()
    fence_copy['taz'] = fence_copy['taz'].astype(int)
    
    gdf = fence_copy.merge(result, on='taz', how='inner')
    gdf = gpd.GeoDataFrame(gdf, geometry='geometry', crs=fence.crs)
    
    stats.add('output_rows', len(gdf))
    stats.add('avg_total_people', gdf['总通勤人数'].mean())
    stats.add('avg_avg_distance', gdf['平均通勤距离'].mean())
    stats.add('avg_internal_ratio', gdf['内部通勤比'].mean())
    
    stats.save('compute_taz_indicators_stats.csv')
    
    return gdf


@timer_decorator
def compute_statistics(gdf, name, save=True, output_dir=None):
    """
    计算并保存统计信息（替代print）

    Args:
        gdf: GeoDataFrame
        name: 数据名称（如"基线格局"）
        save: 是否保存到文件
        output_dir: 输出目录（Path），None 则使用 RESULTS_DIR

    Returns:
        dict: 统计信息字典
    """
    stats_collector = StatsCollector(f"statistics_{name}")
    
    result = {
        'name': name,
        'taz_count': len(gdf),
        'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    stats_collector.add('name', name)
    stats_collector.add('taz_count', len(gdf))
    
    indicator_cols = ['总通勤人数', '平均通勤距离', '内部通勤比', 
                      '通勤距离标准差', '通勤距离中位数', '最大通勤距离', '最小通勤距离']
    
    for col in indicator_cols:
        if col in gdf.columns:
            vals = gdf[col].dropna()
            
            col_stats = {
                f'{col}_valid': len(vals),
                f'{col}_mean': vals.mean(),
                f'{col}_median': vals.median(),
                f'{col}_std': vals.std(),
                f'{col}_min': vals.min(),
                f'{col}_max': vals.max(),
                f'{col}_q25': vals.quantile(0.25),
                f'{col}_q75': vals.quantile(0.75)
            }
            
            result[col] = col_stats
            stats_collector.add_dict(col_stats)
    
    if save:
        # 保存为CSV
        flat_stats = {'name': name, 'taz_count': len(gdf)}
        for col in indicator_cols:
            if col in gdf.columns:
                vals = gdf[col].dropna()
                flat_stats[f'{col}_mean'] = vals.mean()
                flat_stats[f'{col}_median'] = vals.median()
                flat_stats[f'{col}_std'] = vals.std()
                flat_stats[f'{col}_min'] = vals.min()
                flat_stats[f'{col}_max'] = vals.max()

        df_stats = pd.DataFrame([flat_stats])
        from .config import RESULTS_DIR
        save_dir = Path(output_dir) if output_dir is not None else RESULTS_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        output_path = save_dir / f'statistics_{name}.csv'
        df_stats.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"统计信息已保存: {output_path}")
    
    return result


@timer_decorator
def compute_diff(
    gdf_a: gpd.GeoDataFrame,
    gdf_b: gpd.GeoDataFrame,
    name_a: str,
    name_b: str,
    fence: gpd.GeoDataFrame,
    indicator_cols: list = None,
    output_dir: Path = None,
) -> gpd.GeoDataFrame:
    """
    计算两个格局的 TAZ 级差值 (A - B)。

    差值列命名为 {col}_diff；同时保留 {col}_{name_a}、{col}_{name_b} 两列，
    供后续箱线图等可视化使用。

    Args:
        gdf_a:         格局A的GeoDataFrame（含 taz 列和指标列）
        gdf_b:         格局B的GeoDataFrame
        name_a:        格局A名称（用于列名后缀）
        name_b:        格局B名称
        fence:         空间数据（用于关联 geometry）
        indicator_cols: 要计算差值的指标列，默认 ['总通勤人数','平均通勤距离','内部通勤比']
        output_dir:    统计文件输出目录（Path），None 则不保存

    Returns:
        gpd.GeoDataFrame: 差值 GeoDataFrame
    """
    if indicator_cols is None:
        indicator_cols = ['总通勤人数', '平均通勤距离', '内部通勤比']

    stats = StatsCollector("compute_diff")
    stats.add('name_a', name_a)
    stats.add('name_b', name_b)
    stats.add('gdf_a_rows', len(gdf_a))
    stats.add('gdf_b_rows', len(gdf_b))

    # 提取需要的列
    cols = ['taz'] + indicator_cols
    df_a = gdf_a[[c for c in cols if c in gdf_a.columns]].copy()
    df_b = gdf_b[[c for c in cols if c in gdf_b.columns]].copy()

    # 合并，保留两侧原始值
    merged = df_a.merge(df_b, on='taz', suffixes=(f'_{name_a}', f'_{name_b}'), how='inner')
    stats.add('matched_taz', len(merged))

    # 计算差值
    for col in indicator_cols:
        col_a = f'{col}_{name_a}'
        col_b = f'{col}_{name_b}'
        if col_a in merged.columns and col_b in merged.columns:
            merged[f'{col}_diff'] = merged[col_a] - merged[col_b]

    # 关联 geometry
    fence_copy = fence[['taz', 'geometry']].copy()
    fence_copy['taz'] = fence_copy['taz'].astype(int)
    merged['taz'] = merged['taz'].astype(int)

    gdf_diff = fence_copy.merge(merged, on='taz', how='inner')
    gdf_diff = gpd.GeoDataFrame(gdf_diff, geometry='geometry', crs=fence.crs)
    stats.add('output_rows', len(gdf_diff))

    if output_dir is not None:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        stats_path = Path(output_dir) / f'diff_{name_a}_vs_{name_b}_stats.csv'
        pd.DataFrame([stats.current]).to_csv(stats_path, index=False, encoding='utf-8-sig')
        logger.info(f"compute_diff 统计已保存: {stats_path}")

    return gdf_diff


@timer_decorator
def compute_diff_statistics(gdf_diff, name_a, name_b, save=True, output_dir=None):
    """
    计算并保存差值统计信息
    
    Args:
        gdf_diff: 差值GeoDataFrame
        name_a: 格局A名称
        name_b: 格局B名称
        save: 是否保存到文件
    
    Returns:
        dict: 差值统计信息字典
    """
    stats_collector = StatsCollector(f"diff_statistics_{name_a}_vs_{name_b}")
    
    result = {
        'comparison': f'{name_a} - {name_b}',
        'taz_count': len(gdf_diff),
        'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    stats_collector.add('comparison', f'{name_a} - {name_b}')
    stats_collector.add('taz_count', len(gdf_diff))
    
    indicator_cols = ['总通勤人数', '平均通勤距离', '内部通勤比']
    
    for col_base in indicator_cols:
        col_diff = f'{col_base}_diff'
        col_pct = f'{col_base}_pct_change'
        
        if col_diff in gdf_diff.columns:
            vals = gdf_diff[col_diff].dropna()

            col_stats = {
                f'{col_base}_diff_valid': len(vals),
                f'{col_base}_diff_mean': vals.mean(),
                f'{col_base}_diff_median': vals.median(),
                f'{col_base}_diff_std': vals.std(),
                f'{col_base}_diff_min': vals.min(),
                f'{col_base}_diff_max': vals.max(),
                f'{col_base}_diff_positive': (vals > 0).sum(),
                f'{col_base}_diff_positive_pct': (vals > 0).mean() * 100,
                f'{col_base}_diff_negative': (vals < 0).sum(),
                f'{col_base}_diff_negative_pct': (vals < 0).mean() * 100,
                f'{col_base}_diff_zero': (vals == 0).sum(),
            }
            # pct_change 列仅在 compute_diff 输出中存在时才计算
            if col_pct in gdf_diff.columns:
                vals_pct = gdf_diff[col_pct].dropna()
                col_stats[f'{col_base}_pct_change_mean'] = vals_pct.mean()
                col_stats[f'{col_base}_pct_change_median'] = vals_pct.median()
            
            result[col_base] = col_stats
            stats_collector.add_dict(col_stats)
    
    if save:
        # 保存为CSV
        flat_stats = {'comparison': f'{name_a} - {name_b}', 'taz_count': len(gdf_diff)}
        for col_base in indicator_cols:
            if f'{col_base}_diff' in gdf_diff.columns:
                vals = gdf_diff[f'{col_base}_diff'].dropna()
                flat_stats[f'{col_base}_diff_mean'] = vals.mean()
                flat_stats[f'{col_base}_diff_median'] = vals.median()
                flat_stats[f'{col_base}_diff_std'] = vals.std()
                flat_stats[f'{col_base}_diff_positive_pct'] = (vals > 0).mean() * 100

        df_stats = pd.DataFrame([flat_stats])
        from .config import RESULTS_DIR
        save_dir = Path(output_dir) if output_dir is not None else RESULTS_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        output_path = save_dir / f'diff_statistics_{name_a}_vs_{name_b}.csv'
        df_stats.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"差值统计信息已保存: {output_path}")
        
        # 同时保存详细统计
        stats_collector.save(f'diff_statistics_{name_a}_vs_{name_b}_detailed.csv')
    
    return result


@timer_decorator
def compare_multiple_patterns(gdf_list, names, fence, output_prefix='comparison'):
    """
    比较多个格局
    
    Args:
        gdf_list: GeoDataFrame列表
        names: 格局名称列表
        fence: 空间数据
        output_prefix: 输出文件名前缀
    
    Returns:
        dict: 比较结果
    """
    stats = StatsCollector("compare_multiple_patterns")
    stats.add('pattern_count', len(gdf_list))
    stats.add('names', ', '.join(names))
    
    # 汇总统计表
    summary_rows = []
    
    for gdf, name in zip(gdf_list, names):
        row = {'pattern_name': name, 'taz_count': len(gdf)}
        
        for col in ['总通勤人数', '平均通勤距离', '内部通勤比']:
            if col in gdf.columns:
                vals = gdf[col].dropna()
                row[f'{col}_mean'] = vals.mean()
                row[f'{col}_median'] = vals.median()
                row[f'{col}_std'] = vals.std()
        
        summary_rows.append(row)
    
    summary_df = pd.DataFrame(summary_rows)
    
    # 保存汇总表
    from .config import RESULTS_DIR
    output_path = RESULTS_DIR / f'{output_prefix}_summary.csv'
    summary_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    logger.info(f"多格局比较汇总已保存: {output_path}")
    
    stats.add('output_file', str(output_path))
    stats.save('compare_multiple_patterns_stats.csv')
    
    return {
        'summary': summary_df,
        'names': names
    }


def compute_global_metrics(df_od, o_col='o', d_col='d', value_col='人数', distance_col='distance'):
    """
    计算全局指标
    
    Args:
        df_od: OD数据DataFrame
    
    Returns:
        dict: 全局指标
    """
    stats = StatsCollector("global_metrics")
    
    total_flow = df_od[value_col].sum()
    
    # 加权平均距离
    df_valid = df_od[df_od[distance_col].notna()].copy()
    weighted_dist = (df_valid[value_col] * df_valid[distance_col]).sum() / df_valid[value_col].sum()
    
    # 内部通勤
    internal = df_od[df_od[o_col] == df_od[d_col]][value_col].sum()
    internal_ratio = internal / total_flow * 100
    
    # 距离分布
    dist_stats = df_valid[distance_col].describe()
    
    result = {
        'total_flow': total_flow,
        'weighted_avg_distance': weighted_dist,
        'internal_commute_count': internal,
        'internal_commute_ratio': internal_ratio,
        'distance_mean': dist_stats['mean'],
        'distance_std': dist_stats['std'],
        'distance_min': dist_stats['min'],
        'distance_25%': dist_stats['25%'],
        'distance_50%': dist_stats['50%'],
        'distance_75%': dist_stats['75%'],
        'distance_max': dist_stats['max']
    }
    
    stats.add_dict(result)
    stats.save('global_metrics_stats.csv')

    return result


# ---------------------------------------------------------------------------
# 新增函数：pattern_static_stats / pattern_flow_stats / compute_kl
# ---------------------------------------------------------------------------

def _safe_write_csv(df: pd.DataFrame, output_path: Path, **kwargs) -> None:
    """先写临时文件再原子替换，避免文件被 IDE 独占锁定时写入失败。"""
    import os, tempfile
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=output_path.parent, suffix='.tmp')
    try:
        os.close(fd)
        df.to_csv(tmp, **kwargs)
        os.replace(tmp, output_path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _save_sections_to_csv(sections: list, output_path: Path) -> None:
    """
    将多个 (标题, DataFrame) 拼接写入单个 CSV，section 之间用空行+标题行分隔。

    Args:
        sections:    list of (section_title: str, df: pd.DataFrame)
        output_path: 输出路径
    """
    import os, tempfile
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=output_path.parent, suffix='.tmp')
    try:
        os.close(fd)
        with open(tmp, 'w', encoding='utf-8-sig', newline='') as f:
            for title, df in sections:
                f.write(f'# {title}\n')
                df.to_csv(f, index=True)
                f.write('\n')
        os.replace(tmp, output_path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def pattern_static_stats(
    df_od: pd.DataFrame,
    name: str,
    output_dir: Path,
    o_col: str = 'o',
    d_col: str = 'd',
    value_col: str = '人数',
    distance_col: str = 'distance',
    is_diff: bool = False,
) -> dict:
    """
    计算格局的静态 OD 端统计（O 侧 / D 侧人数分布特征）。

    兼容单格局统计（is_diff=False）和两格局差值统计（is_diff=True，
    此时 value_col 传入差值列名如 '差值'）。

    输出：
        {name}_static_all_stats.csv      — 详细版（O/D 侧 describe + 前10特例）
        star_{name}_static_concise_stats.csv — 简明版（论文直引）

    Args:
        df_od:        OD 数据 DataFrame
        name:         格局名称前缀（如 'actual'、'diff_actual_theoretical'）
        output_dir:   输出目录
        o_col:        起点列名
        d_col:        终点列名
        value_col:    人数/差值列名
        distance_col: 距离列名
        is_diff:      是否为差值模式

    Returns:
        dict: {'o_stats': DataFrame, 'd_stats': DataFrame}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = df_od.copy()
    has_dist = distance_col in df.columns and df[distance_col].notna().any()

    # ── O 侧聚合 ──────────────────────────────────────────────────────────
    agg_dict = {
        '总流出量': (value_col, 'sum'),
        '平均流出量': (value_col, 'mean'),
        'OD对数': (value_col, 'count'),
        '流出量标准差': (value_col, 'std'),
        '最小流出量': (value_col, 'min'),
        '最大流出量': (value_col, 'max'),
    }
    if has_dist:
        agg_dict.update({
            '平均距离': (distance_col, 'mean'),
            '距离标准差': (distance_col, 'std'),
            '最短距离': (distance_col, 'min'),
            '最长距离': (distance_col, 'max'),
        })
    o_stats = df.groupby(o_col).agg(**agg_dict).reset_index()
    o_stats.rename(columns={o_col: 'taz'}, inplace=True)
    o_stats['变异系数'] = (o_stats['流出量标准差'] / o_stats['平均流出量']).round(4)

    # ── D 侧聚合 ──────────────────────────────────────────────────────────
    agg_dict_d = {
        '总流入量': (value_col, 'sum'),
        '平均流入量': (value_col, 'mean'),
        'OD对数': (value_col, 'count'),
        '流入量标准差': (value_col, 'std'),
        '最小流入量': (value_col, 'min'),
        '最大流入量': (value_col, 'max'),
    }
    if has_dist:
        agg_dict_d.update({
            '平均距离': (distance_col, 'mean'),
            '距离标准差': (distance_col, 'std'),
            '最短距离': (distance_col, 'min'),
            '最长距离': (distance_col, 'max'),
        })
    d_stats = df.groupby(d_col).agg(**agg_dict_d).reset_index()
    d_stats.rename(columns={d_col: 'taz'}, inplace=True)
    d_stats['变异系数'] = (d_stats['流入量标准差'] / d_stats['平均流入量']).round(4)

    # ── 详细版 CSV ────────────────────────────────────────────────────────
    sections = [
        ('O侧（起点）分布统计 describe', o_stats.describe()),
        ('D侧（终点）分布统计 describe', d_stats.describe()),
        ('O侧 流出量最大前10 TAZ',
         o_stats.nlargest(10, '总流出量')[
             ['taz', '总流出量', 'OD对数', '平均流出量'] +
             (['平均距离'] if has_dist else [])
         ]),
        ('O侧 OD对数最多前10 TAZ',
         o_stats.nlargest(10, 'OD对数')[
             ['taz', 'OD对数', '总流出量', '平均流出量'] +
             (['平均距离'] if has_dist else [])
         ]),
    ]
    if has_dist:
        sections += [
            ('O侧 平均距离最短前10 TAZ',
             o_stats.nsmallest(10, '平均距离')[['taz', '平均距离', '总流出量', 'OD对数']]),
            ('O侧 平均距离最长前10 TAZ',
             o_stats.nlargest(10, '平均距离')[['taz', '平均距离', '总流出量', 'OD对数']]),
        ]
    _save_sections_to_csv(sections, output_dir / f'{name}_static_all_stats.csv')

    # ── 简明版 CSV ────────────────────────────────────────────────────────
    concise = {
        '起点TAZ数': o_stats['taz'].nunique(),
        '终点TAZ数': d_stats['taz'].nunique(),
        'O侧_总流出量均值': round(o_stats['总流出量'].mean(), 4),
        'O侧_总流出量中位数': round(o_stats['总流出量'].median(), 4),
        'O侧_总流出量标准差': round(o_stats['总流出量'].std(), 4),
        'O侧_变异系数均值': round(o_stats['变异系数'].mean(), 4),
        'D侧_总流入量均值': round(d_stats['总流入量'].mean(), 4),
        'D侧_总流入量中位数': round(d_stats['总流入量'].median(), 4),
        'D侧_总流入量标准差': round(d_stats['总流入量'].std(), 4),
        'D侧_变异系数均值': round(d_stats['变异系数'].mean(), 4),
    }
    if has_dist:
        concise.update({
            'O侧_平均距离均值(m)': round(o_stats['平均距离'].mean(), 4),
            'O侧_平均距离中位数(m)': round(o_stats['平均距离'].median(), 4),
            'D侧_平均距离均值(m)': round(d_stats['平均距离'].mean(), 4),
            'D侧_平均距离中位数(m)': round(d_stats['平均距离'].median(), 4),
        })
    concise_path = output_dir / f'star_{name}_static_concise_stats.csv'
    _safe_write_csv(pd.DataFrame([concise]), concise_path, index=False, encoding='utf-8-sig')

    logger.info(f"pattern_static_stats 完成: {name}, 输出至 {output_dir}")
    return {'o_stats': o_stats, 'd_stats': d_stats}


def pattern_flow_stats(
    df_od: pd.DataFrame,
    name: str,
    output_dir: Path,
    o_col: str = 'o',
    d_col: str = 'd',
    value_col: str = '人数',
    distance_col: str = 'distance',
    is_diff: bool = False,
) -> dict:
    """
    计算格局的动态 T 通勤流统计（OD 对级别的人数和距离分布）。

    兼容单格局统计（is_diff=False）和两格局差值统计（is_diff=True）。
    差值模式额外输出按距离分段的差值统计。

    输出：
        {name}_flow_all_stats.csv          — 详细版
        star_{name}_flow_concise_stats.csv — 简明版（论文直引）

    Args:
        df_od:        OD 数据 DataFrame
        name:         格局名称前缀
        output_dir:   输出目录
        o_col:        起点列名
        d_col:        终点列名
        value_col:    人数/差值列名
        distance_col: 距离列名
        is_diff:      是否为差值模式

    Returns:
        dict: {'global_stats': dict, 'dist_seg': DataFrame or None}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = df_od.copy()
    has_dist = distance_col in df.columns and df[distance_col].notna().any()
    vals = df[value_col]

    # ── 全局指标 ──────────────────────────────────────────────────────────
    total_od = len(df)
    total_flow = float(vals.sum())
    nonzero_od = int((vals != 0).sum())
    cv = float(vals.std() / vals.mean()) if vals.mean() != 0 else np.nan

    global_stats: dict = {
        '总OD对数': total_od,
        '总通勤人数': round(total_flow, 4),
        '非零OD对数': nonzero_od,
        '变异系数CV(人数)': round(cv, 4),
        '人数Q25': round(float(vals.quantile(0.25)), 4),
        '人数Q50': round(float(vals.quantile(0.50)), 4),
        '人数Q75': round(float(vals.quantile(0.75)), 4),
    }

    if has_dist:
        dist = df[distance_col].dropna()
        weighted_avg = float(
            (df[value_col] * df[distance_col]).sum() / df[value_col].sum()
        ) if df[value_col].sum() != 0 else np.nan
        global_stats.update({
            '全局加权平均通勤距离(m)': round(weighted_avg, 4),
            '全局通勤距离中位数(m)': round(float(dist.median()), 4),
            '全局通勤距离标准差(m)': round(float(dist.std()), 4),
            '距离Q25(m)': round(float(dist.quantile(0.25)), 4),
            '距离Q50(m)': round(float(dist.quantile(0.50)), 4),
            '距离Q75(m)': round(float(dist.quantile(0.75)), 4),
        })

    # ── 差值模式：按距离分段统计 ──────────────────────────────────────────
    dist_seg = None
    if is_diff and has_dist:
        bins = [0, 5000, 10000, 20000, 50000, np.inf]
        labels = ['0-5km', '5-10km', '10-20km', '20-50km', '>50km']
        df['距离段'] = pd.cut(df[distance_col], bins=bins, labels=labels)
        dist_seg = df.groupby('距离段', observed=True)[value_col].agg(
            ['sum', 'mean', 'count']
        )

    # ── 详细版 CSV ────────────────────────────────────────────────────────
    sections = [
        ('全局通勤流统计', pd.DataFrame([global_stats]).T.rename(columns={0: '值'})),
    ]
    if dist_seg is not None:
        sections.append(('按距离分段差值统计', dist_seg))
    _save_sections_to_csv(sections, output_dir / f'{name}_flow_all_stats.csv')

    # ── 简明版 CSV ────────────────────────────────────────────────────────
    concise = {
        '总流量': round(total_flow, 4),
        'OD对数': total_od,
        '平均流量': round(float(vals.mean()), 4),
        '变异系数CV': round(cv, 4),
    }
    if has_dist:
        concise['平均距离(m)'] = round(global_stats.get('全局加权平均通勤距离(m)', np.nan), 4)

    concise_rows = [concise]
    if dist_seg is not None:
        # 将分段统计追加到简明版（多行）
        seg_df = dist_seg.reset_index()
        seg_df.columns = ['距离段', '差值sum', '差值mean', 'OD对数']
        concise_rows_df = pd.concat(
            [pd.DataFrame([concise]), seg_df], ignore_index=True
        )
        _safe_write_csv(
            concise_rows_df,
            output_dir / f'star_{name}_flow_concise_stats.csv',
            index=False, encoding='utf-8-sig'
        )
    else:
        _safe_write_csv(
            pd.DataFrame(concise_rows),
            output_dir / f'star_{name}_flow_concise_stats.csv',
            index=False, encoding='utf-8-sig'
        )

    logger.info(f"pattern_flow_stats 完成: {name}, 输出至 {output_dir}")
    return {'global_stats': global_stats, 'dist_seg': dist_seg}


def compute_kl(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    name_a: str,
    name_b: str,
    value_col: str = '人数',
    o_col: str = 'o',
    d_col: str = 'd',
    output_dir: Path = None,
) -> dict:
    """
    计算两个格局之间的 KL 散度和 Jensen-Shannon 散度。

    计算基于概率分布（归一化后），取两格局 OD 对并集，缺失值填充 epsilon=1e-10。

    KL(P||Q) = sum(P * log(P/Q))
    JSD(P||Q) = 0.5*KL(P||M) + 0.5*KL(Q||M)，M = 0.5*(P+Q)

    输出：
        star_kl_{name_a}_{name_b}.csv — KL 散度结果（论文直引）

    Args:
        df_a:       格局A的 OD DataFrame
        df_b:       格局B的 OD DataFrame
        name_a:     格局A名称
        name_b:     格局B名称
        value_col:  人数列名
        o_col:      起点列名
        d_col:      终点列名
        output_dir: 输出目录（Path），None 则不保存

    Returns:
        dict: {'kl_a_to_b', 'kl_b_to_a', 'jsd', 'name_a', 'name_b'}
    """
    epsilon = 1e-10

    # 归一化为概率分布
    def _to_prob(df: pd.DataFrame) -> pd.Series:
        s = df.groupby([o_col, d_col])[value_col].sum()
        total = s.sum()
        return s / total if total > 0 else s

    p_series = _to_prob(df_a)
    q_series = _to_prob(df_b)

    # 取并集索引
    all_idx = p_series.index.union(q_series.index)
    p = p_series.reindex(all_idx, fill_value=epsilon).values.astype(float)
    q = q_series.reindex(all_idx, fill_value=epsilon).values.astype(float)

    # 确保无零值（防止 log(0)）
    p = np.where(p <= 0, epsilon, p)
    q = np.where(q <= 0, epsilon, q)

    # 重新归一化（填充 epsilon 后总和略有偏差）
    p = p / p.sum()
    q = q / q.sum()

    kl_a_to_b = float(np.sum(p * np.log(p / q)))
    kl_b_to_a = float(np.sum(q * np.log(q / p)))

    m = 0.5 * (p + q)
    jsd = float(0.5 * np.sum(p * np.log(p / m)) + 0.5 * np.sum(q * np.log(q / m)))

    result = {
        'name_a': name_a,
        'name_b': name_b,
        'od_pairs_a': len(df_a),
        'od_pairs_b': len(df_b),
        'od_pairs_union': len(all_idx),
        'kl_a_to_b': round(kl_a_to_b, 6),
        'kl_b_to_a': round(kl_b_to_a, 6),
        'jsd': round(jsd, 6),
    }

    if output_dir is not None:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        out_path = Path(output_dir) / f'star_kl_{name_a}_{name_b}.csv'
        pd.DataFrame([result]).to_csv(out_path, index=False, encoding='utf-8-sig')
        logger.info(f"KL 散度已保存: {out_path}")

    logger.info(
        f"compute_kl: {name_a} vs {name_b} | "
        f"KL(A||B)={kl_a_to_b:.4f}, KL(B||A)={kl_b_to_a:.4f}, JSD={jsd:.4f}"
    )
    return result


def compute_balance_ratio(
    static_csv_path,
    fence: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    计算每个 TAZ 的职住平衡度（工作地人数 / 居住地人数）。

    Args:
        static_csv_path: [主城区]TAZ4-static.csv 路径
        fence:           TAZ 边界 GeoDataFrame

    Returns:
        gpd.GeoDataFrame: 含 taz, 居住人数, 工作人数, 平衡度 列
    """
    df = pd.read_csv(static_csv_path, encoding='utf-8-sig')
    df['taz'] = df['taz'].astype(int)

    home = df[df['人口类型'] == 'home'][['taz', '人数']].rename(columns={'人数': '居住人数'})
    work = df[df['人口类型'] == 'work'][['taz', '人数']].rename(columns={'人数': '工作人数'})

    merged = home.merge(work, on='taz', how='outer').fillna(0)
    # 避免除以零：居住人数为 0 时平衡度设为 NaN
    merged['平衡度'] = np.where(
        merged['居住人数'] > 0,
        merged['工作人数'] / merged['居住人数'],
        np.nan
    )

    fence_copy = fence[['taz', 'geometry']].copy()
    fence_copy['taz'] = fence_copy['taz'].astype(int)
    gdf = fence_copy.merge(merged, on='taz', how='left')
    gdf = gpd.GeoDataFrame(gdf, geometry='geometry', crs=fence.crs)

    logger.info(
        f"compute_balance_ratio: {len(gdf)} TAZ, "
        f"平衡度均值={gdf['平衡度'].mean():.3f}, 中位数={gdf['平衡度'].median():.3f}"
    )
    return gdf


def compute_street_self_sufficiency(
    df_od: pd.DataFrame,
    fence: gpd.GeoDataFrame,
    street_shp_path,
    o_col: str = 'o',
    d_col: str = 'd',
    value_col: str = '人数',
) -> gpd.GeoDataFrame:
    """
    计算街道级自给度（内部通勤比），并进行面积归一化。

    方法：
    1. 将 TAZ 中心点（fence 的 center_x/center_y）空间关联到街道边界
    2. 按街道聚合：内部流（起终点在同一街道）/ 总流（以该街道为O或D端）
    3. 计算街道面积（km²）并归一化自给度为自给度密度（1/km²）

    Args:
        df_od:           OD 数据 DataFrame
        fence:           TAZ 边界 GeoDataFrame（含 taz, center_x, center_y 列）
        street_shp_path: 街道边界 shapefile 路径（EPSG:32649）
        o_col:           起点列名
        d_col:           终点列名
        value_col:       人数列名

    Returns:
        gpd.GeoDataFrame: 街道级，含 自给度, 面积_km2, 自给度密度 列（EPSG:32649）
    """
    street_shp_path = Path(street_shp_path)
    streets = gpd.read_file(street_shp_path)

    # 将 TAZ 中心点转为投影坐标系与街道一致
    fence_pts = fence[['taz', 'center_x', 'center_y']].copy()
    fence_pts['taz'] = fence_pts['taz'].astype(int)
    gdf_pts = gpd.GeoDataFrame(
        fence_pts,
        geometry=gpd.points_from_xy(fence_pts['center_x'], fence_pts['center_y']),
        crs='EPSG:4326'
    ).to_crs(streets.crs)

    # 空间关联：TAZ 中心点 → 街道
    joined = gpd.sjoin(gdf_pts, streets[['geometry']].reset_index().rename(columns={'index': 'street_idx'}),
                       how='left', predicate='within')
    taz_to_street = joined[['taz', 'street_idx']].dropna(subset=['street_idx'])
    taz_to_street['street_idx'] = taz_to_street['street_idx'].astype(int)
    # 一个 TAZ 中心点可能落在多个街道边界上（边界重叠），取第一个
    taz_to_street = taz_to_street.drop_duplicates(subset='taz', keep='first')

    # 将街道编号关联到 OD 数据
    df = df_od[[o_col, d_col, value_col]].copy()
    df[o_col] = df[o_col].astype(int)
    df[d_col] = df[d_col].astype(int)

    t2s = taz_to_street.set_index('taz')['street_idx']
    df['o_street'] = df[o_col].map(t2s)
    df['d_street'] = df[d_col].map(t2s)
    df = df.dropna(subset=['o_street', 'd_street'])
    df['o_street'] = df['o_street'].astype(int)
    df['d_street'] = df['d_street'].astype(int)

    # 内部流：起终点在同一街道
    internal = df[df['o_street'] == df['d_street']].groupby('o_street')[value_col].sum()

    # 总流：以该街道为 O 端或 D 端（去重计算）
    o_total = df.groupby('o_street')[value_col].sum()
    d_total = df.groupby('d_street')[value_col].sum()
    # 内部流在 O 和 D 两侧都被计入，需减去一次重复
    all_streets = o_total.index.union(d_total.index)
    total = (o_total.reindex(all_streets, fill_value=0)
             + d_total.reindex(all_streets, fill_value=0)
             - internal.reindex(all_streets, fill_value=0))

    result = pd.DataFrame({
        'street_idx': all_streets,
        '内部通勤人数': internal.reindex(all_streets, fill_value=0).values,
        '总通勤人数': total.values,
    })
    result['自给度'] = np.where(
        result['总通勤人数'] > 0,
        result['内部通勤人数'] / result['总通勤人数'],
        np.nan
    )

    streets_reset = streets.reset_index().rename(columns={'index': 'street_idx'})
    gdf_out = streets_reset.merge(result, on='street_idx', how='left')
    gdf_out = gpd.GeoDataFrame(gdf_out, geometry='geometry', crs=streets.crs)

    # 计算街道面积（km²）并归一化自给度
    gdf_out['面积_km2'] = gdf_out.geometry.area / 1e6
    gdf_out['自给度密度'] = np.where(
        gdf_out['面积_km2'] > 0,
        gdf_out['自给度'] / gdf_out['面积_km2'],
        np.nan
    )

    logger.info(
        f"compute_street_self_sufficiency: {len(gdf_out)} 街道, "
        f"自给度均值={gdf_out['自给度'].mean():.3f}, "
        f"自给度密度均值={gdf_out['自给度密度'].mean():.3f} 1/km²"
    )
    return gdf_out


def compute_excess_commute(
    c_obs_km: float,
    c_min_km: float = 1.118,
    c_ran_km: float = 13.144,
    output_dir: Path = None,
) -> dict:
    """
    计算超额通勤相关指标。

    指标定义：
        EC  = (C_obs - C_min) / C_obs * 100
        NEC = (C_obs - C_min) / (C_ran - C_min) * 100
        CE  = (C_ran - C_obs) / C_ran * 100
        NCE = (C_ran - C_obs) / (C_ran - C_min) * 100

    Args:
        c_obs_km:   实际格局全局加权平均通勤距离（km）
        c_min_km:   理论最小通勤距离（km），默认 1.118
        c_ran_km:   随机通勤距离（km），默认 13.144
        output_dir: 输出目录，None 则不保存

    Returns:
        dict: 含 C_obs, C_min, C_ran, EC, NEC, CE, NCE
    """
    denom_ec = c_obs_km if c_obs_km != 0 else 1e-10
    denom_nec = (c_ran_km - c_min_km) if (c_ran_km - c_min_km) != 0 else 1e-10

    ec  = (c_obs_km - c_min_km) / denom_ec * 100
    nec = (c_obs_km - c_min_km) / denom_nec * 100
    ce  = (c_ran_km - c_obs_km) / c_ran_km * 100
    nce = (c_ran_km - c_obs_km) / denom_nec * 100

    result = {
        'C_obs(km)': round(c_obs_km, 4),
        'C_min(km)': round(c_min_km, 4),
        'C_ran(km)': round(c_ran_km, 4),
        'EC(%)':  round(ec,  2),
        'NEC(%)': round(nec, 2),
        'CE(%)':  round(ce,  2),
        'NCE(%)': round(nce, 2),
    }

    if output_dir is not None:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        out_path = Path(output_dir) / 'star_超额通勤指标.csv'
        pd.DataFrame([result]).to_csv(out_path, index=False, encoding='utf-8-sig')
        logger.info(f"超额通勤指标已保存: {out_path}")

    logger.info(
        f"compute_excess_commute: C_obs={c_obs_km:.3f}km | "
        f"EC={ec:.1f}%, NEC={nec:.1f}%, CE={ce:.1f}%, NCE={nce:.1f}%"
    )
    return result


def compute_time_indicators(
    df_od: pd.DataFrame,
    fence: gpd.GeoDataFrame,
    time_col: str = '平均通勤时间(s)',
    o_col: str = 'o',
    d_col: str = 'd',
    value_col: str = '人数',
) -> tuple:
    """
    计算TAZ级平均通勤时间和全局时长分段统计。

    Args:
        df_od:     完整OD DataFrame，含时间列
        fence:     TAZ边界GeoDataFrame
        time_col:  时间列名（秒）
        o_col:     起点TAZ列名
        d_col:     终点TAZ列名
        value_col: 人数列名

    Returns:
        tuple: (gdf_time, time_stats)
            gdf_time: TAZ级GeoDataFrame，含 '平均通勤时间_min' 列
            time_stats: dict，含全局时长分段统计
    """
    df = df_od[[o_col, d_col, value_col, time_col]].copy()
    df = df[df[time_col].notna() & (df[value_col] > 0)]

    # TAZ级加权平均时间
    df['weighted_time'] = df[value_col] * df[time_col]
    taz_time = df.groupby(o_col).agg(
        sum_weighted_time=('weighted_time', 'sum'),
        sum_people=(value_col, 'sum')
    ).reset_index()
    taz_time['平均通勤时间_min'] = taz_time['sum_weighted_time'] / taz_time['sum_people'] / 60.0
    taz_time = taz_time[[o_col, '平均通勤时间_min']].rename(columns={o_col: 'taz'})

    fence_copy = fence[['taz', 'geometry']].copy()
    fence_copy['taz'] = fence_copy['taz'].astype(int)
    taz_time['taz'] = taz_time['taz'].astype(int)
    gdf_time = fence_copy.merge(taz_time, on='taz', how='left')
    gdf_time = gpd.GeoDataFrame(gdf_time, geometry='geometry', crs=fence.crs)

    # 全局时长分段统计
    bins = [0, 900, 1800, 2700, 3600, float('inf')]
    labels = ['<15分钟', '15-30分钟', '30-45分钟', '45-60分钟', '>60分钟']
    df['时长段'] = pd.cut(df[time_col], bins=bins, labels=labels)

    time_seg = df.groupby('时长段', observed=True)[value_col].sum()
    time_stats = {label: int(time_seg.get(label, 0)) for label in labels}

    global_avg_min = float((df[value_col] * df[time_col]).sum() / df[value_col].sum() / 60.0)
    time_stats['全局平均时间_min'] = round(global_avg_min, 2)

    logger.info(
        f"compute_time_indicators: TAZ数={len(gdf_time)}, "
        f"全局平均时间={global_avg_min:.2f}分钟"
    )
    return gdf_time, time_stats


def compute_transport_mode_stats(
    df_od: pd.DataFrame,
    value_col: str = '人数',
) -> dict:
    """
    计算5种交通方式的全局加权占比。

    Args:
        df_od:     完整OD DataFrame，含交通方式比例列
        value_col: 人数列名

    Returns:
        dict: {'驾车': float, '地铁': float, '公交': float, '骑行': float, '步行': float}
    """
    mode_cols = {
        '驾车比例': '驾车',
        '地铁比例': '地铁',
        '公交比例': '公交',
        '骑行比例': '骑行',
        '步行比例': '步行',
    }

    df = df_od.copy()
    total = df[value_col].sum()

    result = {}
    for col, name in mode_cols.items():
        if col in df.columns:
            weighted = (df[col] * df[value_col]).sum() / total
            result[name] = round(float(weighted), 4)
        else:
            result[name] = 0.0

    logger.info(
        f"compute_transport_mode_stats: "
        f"驾车={result.get('驾车', 0):.2%}, 地铁={result.get('地铁', 0):.2%}, "
        f"公交={result.get('公交', 0):.2%}, 骑行={result.get('骑行', 0):.2%}, "
        f"步行={result.get('步行', 0):.2%}"
    )
    return result


def compute_street_balance_ratio(
    static_csv_path,
    fence: gpd.GeoDataFrame,
    street_shp_path,
) -> gpd.GeoDataFrame:
    """
    计算街道级职住平衡度。

    Args:
        static_csv_path: TAZ静态数据CSV路径（含taz, 人口类型, 人数列）
        fence:           TAZ边界GeoDataFrame
        street_shp_path: 街道边界SHP路径

    Returns:
        GeoDataFrame: 街道级，含 '居住人数', '工作人数', '平衡度' 列
    """
    street_shp_path = Path(street_shp_path)
    streets = gpd.read_file(street_shp_path)

    df_static = pd.read_csv(static_csv_path, encoding='utf-8-sig')
    df_static['taz'] = df_static['taz'].astype(int)

    fence_pts = fence[['taz', 'center_x', 'center_y']].copy()
    fence_pts['taz'] = fence_pts['taz'].astype(int)
    gdf_pts = gpd.GeoDataFrame(
        fence_pts,
        geometry=gpd.points_from_xy(fence_pts['center_x'], fence_pts['center_y']),
        crs='EPSG:4326'
    ).to_crs(streets.crs)

    joined = gpd.sjoin(gdf_pts, streets[['geometry']].reset_index().rename(columns={'index': 'street_idx'}),
                       how='left', predicate='within')
    taz_to_street = joined[['taz', 'street_idx']].dropna(subset=['street_idx'])
    taz_to_street['street_idx'] = taz_to_street['street_idx'].astype(int)
    taz_to_street = taz_to_street.drop_duplicates(subset='taz', keep='first')

    df_with_street = df_static.merge(taz_to_street, on='taz', how='inner')

    home = df_with_street[df_with_street['人口类型'] == 'home'].groupby('street_idx')['人数'].sum()
    work = df_with_street[df_with_street['人口类型'] == 'work'].groupby('street_idx')['人数'].sum()

    result = pd.DataFrame({
        'street_idx': home.index.union(work.index),
        '居住人数': home.reindex(home.index.union(work.index), fill_value=0).values,
        '工作人数': work.reindex(home.index.union(work.index), fill_value=0).values,
    })
    result['平衡度'] = np.where(
        result['居住人数'] > 0,
        result['工作人数'] / result['居住人数'],
        np.nan
    )

    streets_reset = streets.reset_index().rename(columns={'index': 'street_idx'})
    gdf_out = streets_reset.merge(result, on='street_idx', how='left')
    gdf_out = gpd.GeoDataFrame(gdf_out, geometry='geometry', crs=streets.crs)

    logger.info(
        f"compute_street_balance_ratio: {len(gdf_out)} 街道, "
        f"平衡度均值={gdf_out['平衡度'].mean():.3f}"
    )
    return gdf_out
