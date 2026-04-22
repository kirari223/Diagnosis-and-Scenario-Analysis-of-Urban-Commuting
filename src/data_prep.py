"""
数据准备模块
包含数据清洗、格式转换、空间关联等功能
"""
import json
import numpy as np
import pandas as pd
import geopandas as gpd
from pyproj import Transformer
from shapely.ops import unary_union

from .config import (
    STATIC_CSV, DISTANCE_CSV, OD_CSV, SHP_PATH,
    OD_FEATURE_CSV, POP_RESIDENTIAL_CSV, POP_WORK_CSV, GRID_TAZ_MAPPING_JSON,
    get_result_path, RESULTS_DIR
)
from .utils import StatsCollector, save_matrix, timer_decorator, logger


@timer_decorator
def matrix_to_df(static_path=None, distance_path=None, save_intermediate=True):
    """
    将原始数据转换为矩阵格式T/C和列表格式O/D
    
    Args:
        static_path: static.csv路径
        distance_path: distance.csv路径
        save_intermediate: 是否保存中间结果
    
    Returns:
        dict: 包含O_list, D_list, C_matrix, T_matrix的字典
    import json
    """
    stats = StatsCollector("matrix_to_df")
    
    # 使用默认路径
    static_path = static_path or STATIC_CSV
    distance_path = distance_path or DISTANCE_CSV
    
    # 读取static数据
    static = pd.read_csv(static_path, encoding='utf-8-sig')
    stats.add('static_rows', len(static))
    
    # 找到UNIT的最大值
    home_units = static[static['人口类型'] == 'home']['taz']
    work_units = static[static['人口类型'] == 'work']['taz']
    
    max_ID = max(home_units.max(), work_units.max()) if not (home_units.empty or work_units.empty) else 0
    m = int(home_units.max()) if not home_units.empty else 0  # SUNIT最大值
    n = int(work_units.max()) if not work_units.empty else 0   # EUNIT最大值
    taz_mapping = {int(taz): int(taz) for taz in range(max_ID + 1)}
    
    stats.add('max_home_taz', m)
    stats.add('max_work_taz', n)
    
    # 处理住房分布(O_list)
    O_list = [None] * (m + 1)
    home_data = static[static['人口类型'] == 'home'].copy()
    home_data['taz'] = home_data['taz'].astype(int)
    for _, row in home_data.iterrows():
        unit = row['taz']
        total_pop = row['人数']
        O_list[unit] = total_pop
    
    # 处理工作分布(D_list)
    D_list = [None] * (n + 1)
    work_data = static[static['人口类型'] == 'work'].copy()
    work_data['taz'] = work_data['taz'].astype(int)
    for _, row in work_data.iterrows():
        unit = row['taz']
        total_pop = row['人数']
        D_list[unit] = total_pop
    
    # 计算总和
    O_list_cal = [x for x in O_list if x is not None]
    D_list_cal = [x for x in D_list if x is not None]
    W = sum(O_list_cal)
    W_D = sum(D_list_cal)
    
    stats.add('housing_total', W)
    stats.add('work_total', W_D)
    stats.add('housing_count', len(O_list_cal))
    stats.add('work_count', len(D_list_cal))
    
    # 读取距离数据并构建C矩阵
    distance_df = pd.read_csv(distance_path, encoding='utf-8-sig')
    
    # 初始化C矩阵
    max_idx = max(taz_mapping.values()) + 1
    C_matrix = np.zeros((max_idx, max_idx))
    
    # 填充C矩阵
    for _, row in distance_df.iterrows():
        taz1 = int(row.iloc[0])
        taz2 = int(row.iloc[1])
        dist = row.iloc[2]
        
        if taz1 in taz_mapping and taz2 in taz_mapping:
            idx1 = taz_mapping[taz1]
            idx2 = taz_mapping[taz2]
            C_matrix[idx1, idx2] = dist
    
    stats.add('C_matrix_shape', C_matrix.shape)
    stats.add('C_matrix_nonzero', np.count_nonzero(C_matrix))
    
    # 读取OD数据构建T矩阵
    od_df = pd.read_csv(OD_CSV, encoding='utf-8-sig')
    T_matrix = np.zeros((max_idx, max_idx))
    
    for _, row in od_df.iterrows():
        o = int(row['o'])
        d = int(row['d'])
        count = row['人数']
        
        if o in taz_mapping and d in taz_mapping:
            idx_o = taz_mapping[o]
            idx_d = taz_mapping[d]
            T_matrix[idx_o, idx_d] = count
    
    stats.add('T_matrix_shape', T_matrix.shape)
    stats.add('T_matrix_total', T_matrix.sum())
    stats.add('T_matrix_nonzero', np.count_nonzero(T_matrix))
    
    # 保存中间结果
    if save_intermediate:
        pattern_dir = RESULTS_DIR / '2.Pattern_Computation' / '2.1Theoretical_Pattern'
        pattern_dir.mkdir(parents=True, exist_ok=True)
        save_matrix(np.array(O_list), pattern_dir / 'O_list.npy')
        save_matrix(np.array(D_list), pattern_dir / 'D_list.npy')
        save_matrix(C_matrix, pattern_dir / 'C_matrix.npy')
        save_matrix(T_matrix, pattern_dir / 'T_observed.npy')
    
    # 保存统计信息
    stats.save('data_prep_matrix_stats.csv')
    
    return {
        'O_list': O_list,
        'D_list': D_list,
        'C_matrix': C_matrix,
        'T_matrix': T_matrix,
        'taz_mapping': taz_mapping,
        'housing_total': W,
        'work_total': W_D
    }


@timer_decorator
def df_to_matrix(matrix_path, data_type="matrix", skip_header=True, matrix_type=None):
    """
    向量化极速版：无任何for循环，处理百万级数据秒级完成
    """
    stats = StatsCollector("df_to_matrix")

    # 1. 统一读取数据（一次读取）
    df = pd.read_csv(matrix_path, encoding='utf-8-sig', low_memory=False)
    stats.add("file_path", str(matrix_path))
    stats.add("raw_shape", df.shape)

    # ==========================================
    # 情况1：静态数据（向量化，无循环）
    # ==========================================
    if data_type == "static":
        print(f"输入静态分布数据，提取 O_list(home) / D_list(work)")

        # 向量化筛选
        home = df[df["人口类型"] == "home"]
        work = df[df["人口类型"] == "work"]

        # 获取全局最大 taz
        max_taz = df["taz"].max()

        # 向量化构建 O_list / D_list（无循环！）
        O_list = np.zeros((max_taz + 1,1), dtype=np.float32)
        D_list = np.zeros((max_taz + 1,1), dtype=np.float32)

        O_list[home["taz"].values, 0] = home["人数"].values
        D_list[work["taz"].values, 0] = work["人数"].values

        # 统计
        stats.add("data_type", "static")
        stats.add("total_home", float(O_list.sum()))
        stats.add("total_work", float(D_list.sum()))
        stats.add("taz_count", int(max_taz + 1))
        stats.save("static_data_stats.csv")

        return {
            "O_list": O_list,
            "D_list": D_list,
            "housing_total": int(O_list.sum()),
            "work_total": int(D_list.sum())
        }

    # ==========================================
    # 情况2：OD矩阵 / 距离矩阵（向量化，无循环！）
    # ==========================================
    else:
        print(f"输入矩阵类数据")

        # 自动列名
        Htaz_col = df.columns[0]
        Jtaz_col = df.columns[1]
        value_col = df.columns[2]

        # 转整数（向量化）
        h_list = df[Htaz_col].astype(int).values
        j_list = df[Jtaz_col].astype(int).values
        v_list = df[value_col].values

        # 计算矩阵尺寸
        max_h = h_list.max()
        max_j = j_list.max()
        max_idx = max(max_h, max_j) + 1

        # 向量化赋值（核心！无循环，秒填百万数据）
        result_matrix = np.zeros((max_idx, max_idx), dtype=np.float32)
        result_matrix[h_list, j_list] = v_list

        # 统计
        if matrix_type == "C":
            stats.add('C_matrix_shape', result_matrix.shape)
            stats.add('C_distance_total', round(float(result_matrix.sum()), 2))
            stats.add('C_nonzero_count', int(np.count_nonzero(result_matrix)))
            print("[OK] 距离矩阵 C 已生成（向量化）")

        elif matrix_type == "T":
            stats.add('T_matrix_shape', result_matrix.shape)
            stats.add('T_people_total', int(result_matrix.sum()))
            stats.add('T_nonzero_count', int(np.count_nonzero(result_matrix)))
            print("[OK] OD矩阵 T 已生成（向量化）")

        return result_matrix

@timer_decorator
def matrix_to_long_df(matrix, value_name='人数', o_col='o', d_col='d'):
    """
    将矩阵转换为长格式DataFrame
    
    Args:
        matrix: 2D numpy array或DataFrame
        value_name: 值列名
        o_col: 起点列名
        d_col: 终点列名
    
    Returns:
        pd.DataFrame: 长格式DataFrame
    """
    if isinstance(matrix, np.ndarray):
        matrix = pd.DataFrame(matrix)
    
    # 使用stack转换
    stacked = matrix.stack().reset_index()
    stacked.columns = [o_col, d_col, value_name]
    
    # 过滤零值
    stacked = stacked[stacked[value_name] > 0].copy()
    
    return stacked


@timer_decorator
def prob_to_int(
    df_prob: pd.DataFrame,
    target_total: int,
    threshold: float = 0.5,
    value_col: str = '人数',
    o_col: str = 'o',
    d_col: str = 'd',
    output_dir=None,
) -> pd.DataFrame:
    """
    将浮点数格局转换为整数格局（截尾 + 四舍五入 + 全局缩放微调）。

    参照 od_process_step1.py（截尾）和 od_process_step2a.py（四舍五入）。

    Args:
        df_prob:      浮点数格局 DataFrame，至少含 o_col、d_col、value_col 三列
        target_total: 目标总人数（通常取原始浮点数据人数列求和取整）
        threshold:    截尾阈值，人数 < threshold 的 OD 对直接丢弃，默认 0.5
        value_col:    人数列名，默认 '人数'
        o_col:        起点列名，默认 'o'
        d_col:        终点列名，默认 'd'
        output_dir:   统计文件输出目录（Path），None 则不保存

    Returns:
        pd.DataFrame: 整数化结果，列为 [o_col, d_col, value_col]，人数为正整数
    """
    stats = StatsCollector("prob_to_int")
    stats.add('input_rows', len(df_prob))
    stats.add('input_total', float(df_prob[value_col].sum()))
    stats.add('target_total', target_total)
    stats.add('threshold', threshold)

    # Step 1: 截尾
    df = df_prob[[o_col, d_col, value_col]].copy()
    df = df[df[value_col] >= threshold].copy()
    stats.add('after_threshold_rows', len(df))
    stats.add('threshold_keep_rate', len(df) / len(df_prob))

    # Step 2: 四舍五入，过滤零值
    df[value_col] = df[value_col].round().astype(int)
    df = df[df[value_col] > 0].copy()
    stats.add('after_round_rows', len(df))
    stats.add('after_round_total', int(df[value_col].sum()))

    # Step 3: 全局缩放使总和接近目标
    current_total = df[value_col].sum()
    scale_factor = target_total / current_total
    df[value_col] = (df[value_col] * scale_factor).round().astype(int)
    df = df[df[value_col] > 0].copy()
    stats.add('scale_factor', round(scale_factor, 6))
    stats.add('after_scale_total', int(df[value_col].sum()))

    # Step 4: 微调，使总和严格等于 target_total
    diff = target_total - int(df[value_col].sum())
    if diff != 0:
        sorted_idx = df.sort_values(value_col, ascending=False).index
        adjust_idx = sorted_idx[:abs(diff)]
        df.loc[adjust_idx, value_col] += (1 if diff > 0 else -1)
        # 确保无零值或负值
        df = df[df[value_col] > 0].copy()

    final_total = int(df[value_col].sum())
    stats.add('final_rows', len(df))
    stats.add('final_total', final_total)
    stats.add('total_diff_from_target', final_total - target_total)

    # 保存统计
    if output_dir is not None:
        from pathlib import Path as _Path
        _Path(output_dir).mkdir(parents=True, exist_ok=True)
        stats_path = _Path(output_dir) / 'prob_to_int_stats.csv'
        import pandas as _pd
        _pd.DataFrame([stats.current]).to_csv(stats_path, index=False, encoding='utf-8-sig')
        logger.info(f"整数化统计已保存: {stats_path}")

    logger.info(
        f"prob_to_int 完成: 输入 {len(df_prob):,} 行 -> 截尾后 {stats.current.get('after_threshold_rows',0):,} 行 "
        f"-> 最终 {len(df):,} 行, 总人数 {final_total:,} (目标 {target_total:,})"
    )

    return df[[o_col, d_col, value_col]].reset_index(drop=True)


@timer_decorator
def prob_to_int_constrained(
    df_prob: pd.DataFrame,
    O_array: np.ndarray,
    D_array: np.ndarray,
    target_total: int,
    threshold: float = 0.5,
    value_col: str = '人数',
    o_col: str = 'o',
    d_col: str = 'd',
    max_iter: int = 20,
    tol_rate: float = 0.001,
    output_dir=None,
) -> pd.DataFrame:
    """
    带行列约束的整数化：截尾 + 四舍五入 + IPF 行列调整。

    在满足总量约束的基础上，通过迭代比例调整（IPF）尽量使每个 TAZ 的
    行和等于 O_i、列和等于 D_j，并输出行列误差统计。

    Args:
        df_prob:      浮点数格局 DataFrame，至少含 o_col、d_col、value_col 三列
        O_array:      起点约束向量，shape (n_taz,)，O_array[i] = TAZ i 的出行量
        D_array:      终点约束向量，shape (n_taz,)，D_array[j] = TAZ j 的吸引量
        target_total: 目标总人数
        threshold:    截尾阈值，默认 0.5
        value_col:    人数列名
        o_col:        起点列名
        d_col:        终点列名
        max_iter:     IPF 最大迭代轮数，默认 20
        tol_rate:     收敛阈值（行列误差绝对值之和 / target_total），默认 0.001
        output_dir:   统计文件输出目录，None 则不保存

    Returns:
        pd.DataFrame: 整数化结果，列为 [o_col, d_col, value_col]
    """
    from pathlib import Path as _Path

    stats = StatsCollector("prob_to_int_constrained")
    stats.add('input_rows', len(df_prob))
    stats.add('input_total', float(df_prob[value_col].sum()))
    stats.add('target_total', target_total)

    # Step 1: 缩放到真实人数尺度（Wilson 输出为概率解，先乘以总人数）
    df = df_prob[[o_col, d_col, value_col]].copy()
    raw_total = df[value_col].sum()
    if raw_total > 0:
        df[value_col] = df[value_col] * (target_total / raw_total)

    # Step 2: 截尾（在真实人数尺度上，0.5人以下丢弃）
    df = df[df[value_col] >= threshold].copy()

    # Step 3: 四舍五入，过滤零值
    df[value_col] = df[value_col].round().astype(int)
    df = df[df[value_col] > 0].copy()

    # 构建 O/D 目标字典（只保留非零约束）
    O_target = {i: int(round(v)) for i, v in enumerate(O_array) if v > 0}
    D_target = {j: int(round(v)) for j, v in enumerate(D_array) if v > 0}

    tol_abs = target_total * tol_rate

    # Step 4: IPF 行列调整
    for iteration in range(max_iter):
        # ── 行调整 ──────────────────────────────────────────────────────
        row_sums = df.groupby(o_col)[value_col].sum()
        row_err_total = 0
        for i, o_target in O_target.items():
            current = int(row_sums.get(i, 0))
            delta = o_target - current
            if delta == 0:
                continue
            row_err_total += abs(delta)
            mask = df[o_col] == i
            rows_i = df[mask].copy()
            if len(rows_i) == 0:
                continue
            # 按流量大小排序，优先调整大流量
            rows_i_sorted = rows_i.sort_values(value_col, ascending=(delta < 0))
            n_adjust = min(abs(delta), len(rows_i_sorted))
            adjust_idx = rows_i_sorted.index[:n_adjust]
            df.loc[adjust_idx, value_col] += (1 if delta > 0 else -1)

        # 清除零值或负值
        df = df[df[value_col] > 0].copy()

        # ── 列调整 ──────────────────────────────────────────────────────
        col_sums = df.groupby(d_col)[value_col].sum()
        col_err_total = 0
        for j, d_target in D_target.items():
            current = int(col_sums.get(j, 0))
            delta = d_target - current
            if delta == 0:
                continue
            col_err_total += abs(delta)
            mask = df[d_col] == j
            rows_j = df[mask].copy()
            if len(rows_j) == 0:
                continue
            rows_j_sorted = rows_j.sort_values(value_col, ascending=(delta < 0))
            n_adjust = min(abs(delta), len(rows_j_sorted))
            adjust_idx = rows_j_sorted.index[:n_adjust]
            df.loc[adjust_idx, value_col] += (1 if delta > 0 else -1)

        df = df[df[value_col] > 0].copy()

        total_err = row_err_total + col_err_total
        logger.info(f"  IPF iter {iteration+1}: row_err={row_err_total}, col_err={col_err_total}, total_err={total_err}")
        stats.add(f'iter_{iteration+1}_row_err', row_err_total)
        stats.add(f'iter_{iteration+1}_col_err', col_err_total)

        if total_err <= tol_abs:
            logger.info(f"  IPF 收敛于第 {iteration+1} 轮")
            break

    # Step 5: 全局微调使总量严格等于 target_total
    final_sum = int(df[value_col].sum())
    diff = target_total - final_sum
    if diff != 0:
        sorted_idx = df.sort_values(value_col, ascending=False).index
        adjust_idx = sorted_idx[:abs(diff)]
        df.loc[adjust_idx, value_col] += (1 if diff > 0 else -1)
        df = df[df[value_col] > 0].copy()

    # ── 误差统计 ────────────────────────────────────────────────────────
    row_sums_final = df.groupby(o_col)[value_col].sum()
    col_sums_final = df.groupby(d_col)[value_col].sum()

    row_errors = []
    for i, o_target in O_target.items():
        actual = int(row_sums_final.get(i, 0))
        row_errors.append({'taz': i, 'O_target': o_target, 'O_actual': actual,
                            'row_error': actual - o_target,
                            'row_error_rate': (actual - o_target) / o_target if o_target > 0 else 0})
    df_row_err = pd.DataFrame(row_errors)

    col_errors = []
    for j, d_target in D_target.items():
        actual = int(col_sums_final.get(j, 0))
        col_errors.append({'taz': j, 'D_target': d_target, 'D_actual': actual,
                            'col_error': actual - d_target,
                            'col_error_rate': (actual - d_target) / d_target if d_target > 0 else 0})
    df_col_err = pd.DataFrame(col_errors)

    row_mae  = df_row_err['row_error'].abs().mean()
    row_rmse = (df_row_err['row_error'] ** 2).mean() ** 0.5
    row_max  = df_row_err['row_error'].abs().max()
    col_mae  = df_col_err['col_error'].abs().mean()
    col_rmse = (df_col_err['col_error'] ** 2).mean() ** 0.5
    col_max  = df_col_err['col_error'].abs().max()

    summary = {
        'final_total':    int(df[value_col].sum()),
        'target_total':   target_total,
        'total_diff':     int(df[value_col].sum()) - target_total,
        'row_MAE':        round(row_mae, 4),
        'row_RMSE':       round(row_rmse, 4),
        'row_max_abs_err':int(row_max),
        'row_err_rate':   round(df_row_err['row_error_rate'].abs().mean(), 6),
        'col_MAE':        round(col_mae, 4),
        'col_RMSE':       round(col_rmse, 4),
        'col_max_abs_err':int(col_max),
        'col_err_rate':   round(df_col_err['col_error_rate'].abs().mean(), 6),
    }
    stats.add_dict(summary)

    logger.info(
        f"prob_to_int_constrained 完成: {len(df):,} 行, 总量={df[value_col].sum():,}, "
        f"行MAE={row_mae:.2f}, 列MAE={col_mae:.2f}"
    )

    # 保存统计文件
    if output_dir is not None:
        out = _Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        df_row_err.to_csv(out / 'int_row_error.csv', index=False, encoding='utf-8-sig')
        df_col_err.to_csv(out / 'int_col_error.csv', index=False, encoding='utf-8-sig')
        pd.DataFrame([summary]).to_csv(
            out / 'star_int_constraint_summary.csv', index=False, encoding='utf-8-sig')
        logger.info(f"行列误差统计已保存至: {out}")

    return df[[o_col, d_col, value_col]].reset_index(drop=True)


@timer_decorator
def spatial_combine(df_data, fence, on='taz', how='left'):
    """
    将分布数据与空间单元关联
    
    Args:
        df_data: 分布数据DataFrame
        fence: GeoDataFrame空间数据
        on: 关联列名
        how: 关联方式
    
    Returns:
        gpd.GeoDataFrame: 关联后的GeoDataFrame
    """
    stats = StatsCollector("spatial_combine")
    stats.add('input_data_rows', len(df_data))
    stats.add('fence_rows', len(fence))
    
    # 确保taz列类型一致
    df_data = df_data.copy()
    df_data[on] = df_data[on].astype(int)
    fence = fence.copy()
    fence[on] = fence[on].astype(int)
    
    # 合并
    result = fence.merge(df_data, on=on, how=how)
    
    stats.add('output_rows', len(result))
    stats.add('matched_rows', result[on].notna().sum())
    
    stats.save('spatial_combine_stats.csv')
    
    return result


@timer_decorator
def distance_combine(df_pattern, distance_dict, o_col='o', d_col='d'):
    """
    为格局关联距离列
    
    Args:
        df_pattern: 格局DataFrame
        distance_dict: 距离字典 {(o, d): distance}
        o_col: 起点列名
        d_col: 终点列名
    
    Returns:
        pd.DataFrame: 带distance列的DataFrame
    """
    stats = StatsCollector("distance_combine")
    stats.add('input_rows', len(df_pattern))
    
    df_result = df_pattern.copy()
    
    # 添加距离列
    df_result['distance'] = df_result.apply(
        lambda row: distance_dict.get((int(row[o_col]), int(row[d_col])), np.nan),
        axis=1
    )
    
    missing = df_result['distance'].isna().sum()
    stats.add('missing_distance', missing)
    stats.add('missing_pct', missing / len(df_result) * 100)
    
    stats.save('distance_combine_stats.csv')
    
    return df_result


@timer_decorator
def fill_missing_distance(df_ideal, fence, o_col='o', d_col='d'):
    """
    补全缺失的距离值
    
    对于o==d的情况，使用面积等圆半径
    对于o!=d的情况，使用坐标计算欧氏距离
    """
    stats = StatsCollector("fill_missing_distance")
    
    # 从原始shp重新读取以获取准确面积
    try:
        fence_raw = gpd.read_file(SHP_PATH, encoding='GBK')
    except:
        try:
            fence_raw = gpd.read_file(SHP_PATH, encoding='GB2312')
        except:
            fence_raw = gpd.read_file(SHP_PATH)
    
    # 按taz汇总面积
    fence_raw['_area'] = fence_raw.geometry.area
    taz_area_df = fence_raw.groupby('taz')['_area'].sum()
    taz_area = taz_area_df.to_dict()
    
    # 构建taz -> center坐标字典
    taz_cx = dict(zip(fence['taz'], fence['center_x']))
    taz_cy = dict(zip(fence['taz'], fence['center_y']))
    
    # 坐标转换器
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32649", always_xy=True)
    
    df_result = df_ideal.copy()
    null_mask = df_result['distance'].isna()
    filled_count = 0
    
    for idx in df_result[null_mask].index:
        o_val = int(df_result.loc[idx, o_col])
        d_val = int(df_result.loc[idx, d_col])
        
        if o_val == d_val:
            # o==d: 用面积等圆半径
            if o_val in taz_area:
                area = taz_area[o_val]
            else:
                area = np.median(list(taz_area.values()))
            
            df_result.loc[idx, 'distance'] = np.sqrt(area / np.pi)
            filled_count += 1
        else:
            # o!=d: 用坐标计算欧氏距离
            ox = taz_cx.get(o_val)
            oy = taz_cy.get(o_val)
            dx = taz_cx.get(d_val)
            dy = taz_cy.get(d_val)
            
            if pd.notna(ox) and pd.notna(oy) and pd.notna(dx) and pd.notna(dy):
                ox_utm, oy_utm = transformer.transform(ox, oy)
                dx_utm, dy_utm = transformer.transform(dx, dy)
                dist = np.sqrt((ox_utm - dx_utm)**2 + (oy_utm - dy_utm)**2)
                df_result.loc[idx, 'distance'] = dist
                filled_count += 1
    
    stats.add('filled_count', filled_count)
    stats.add('remaining_missing', df_result['distance'].isna().sum())
    stats.save('fill_missing_distance_stats.csv')
    
    return df_result

def build_grid_taz_mapping(od_csv_path=None):
    """
    根据起点/终点网格ID与对应TAZ编号，构建网格ID -> TAZ编号的映射字典。

    Args:
        od_csv_path: OD明细CSV路径，默认使用OD_FEATURE_CSV

    Returns:
        dict: {grid_id: taz}
    """
    od_csv_path = od_csv_path or OD_FEATURE_CSV
    df = pd.read_csv(od_csv_path, encoding="utf-8-sig", low_memory=False)

    required_cols = ["Htaz", "Jtaz", "起点网格ID", "终点网格ID"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise KeyError(
            f"OD文件缺少必要列: {missing_cols}. 请传入包含起点/终点网格ID的OD明细文件，例如 OD_FEATURE_CSV"
        )

    h_map = df[["起点网格ID", "Htaz"]].copy()
    h_map.columns = ["grid_id", "taz"]
    j_map = df[["终点网格ID", "Jtaz"]].copy()
    j_map.columns = ["grid_id", "taz"]

    merged = pd.concat([h_map, j_map], axis=0, ignore_index=True)
    merged = merged.dropna(subset=["grid_id", "taz"]).copy()
    merged["grid_id"] = merged["grid_id"].astype(str).str.strip()
    merged["taz"] = merged["taz"].astype(int)

    conflict = merged.groupby("grid_id")["taz"].nunique()
    conflict = conflict[conflict > 1]
    if len(conflict) > 0:
        raise ValueError(f"发现同一网格ID对应多个TAZ: {conflict.head().to_dict()}")

    merged = merged.drop_duplicates(subset=["grid_id"], keep="first")
    return dict(zip(merged["grid_id"], merged["taz"]))


def _load_grid_taz_mapping(od_csv_path=None):
    """优先加载已生成的映射JSON，缺失时直接按OD明细现算。"""
    if GRID_TAZ_MAPPING_JSON.exists():
        with open(GRID_TAZ_MAPPING_JSON, "r", encoding="utf-8") as f:
            raw_mapping = json.load(f)
        return {str(k): int(v) for k, v in raw_mapping.items()}

    return build_grid_taz_mapping(od_csv_path=od_csv_path)

@timer_decorator
def ratio_extract(od_path=None):
    """提取分行业刚性并返回全部中间变量。"""
    stats = StatsCollector("ratio_extract")

    od_path = od_path or OD_FEATURE_CSV
    od_df = pd.read_csv(od_path, encoding='utf-8-sig', low_memory=False)
    pop_res = pd.read_csv(POP_RESIDENTIAL_CSV, encoding='utf-8-sig', low_memory=False)
    pop_work = pd.read_csv(POP_WORK_CSV, encoding='utf-8-sig', low_memory=False)

    stats.add('od_rows', len(od_df))
    stats.add('pop_res_rows', len(pop_res))
    stats.add('pop_work_rows', len(pop_work))

    for col in ['起点网格ID', '终点网格ID', '人数']:
        if col not in od_df.columns:
            raise KeyError(f"OD表缺少列: {col}")
    if '网格ID' not in pop_res.columns:
        raise KeyError('居住人口表缺少列: 网格ID')
    if '网格ID' not in pop_work.columns:
        raise KeyError('工作人口表缺少列: 网格ID')

    industry_cols = [c for c in pop_res.columns if str(c).startswith('行业:')]
    if not industry_cols:
        raise KeyError("居住人口表中未找到行业列，要求列名以 '行业:' 开头")
    missing_industry_cols = [c for c in industry_cols if c not in pop_work.columns]
    if missing_industry_cols:
        raise KeyError(f"工作人口表缺少行业列: {missing_industry_cols}")
    stats.add('industry_count', len(industry_cols))

    grid_taz_map = _load_grid_taz_mapping(od_csv_path=od_path)
    grid_key_set = set(grid_taz_map.keys())
    stats.add('mapping_count', len(grid_key_set))

    pop_res = pop_res.copy()
    pop_work = pop_work.copy()
    pop_res['网格ID'] = pop_res['网格ID'].astype(str)
    pop_work['网格ID'] = pop_work['网格ID'].astype(str)
    pop_res = pop_res[pop_res['网格ID'].isin(grid_key_set)].copy()
    pop_work = pop_work[pop_work['网格ID'].isin(grid_key_set)].copy()

    pop_res['taz'] = pop_res['网格ID'].map(grid_taz_map)
    pop_work['taz'] = pop_work['网格ID'].map(grid_taz_map)
    pop_res = pop_res.dropna(subset=['taz']).copy()
    pop_work = pop_work.dropna(subset=['taz']).copy()
    pop_res['taz'] = pop_res['taz'].astype(int)
    pop_work['taz'] = pop_work['taz'].astype(int)

    required_keep_cols = ['日期', '网格ID', 'taz', '人口类型'] + industry_cols
    missing_res = [c for c in required_keep_cols if c not in pop_res.columns]
    missing_work = [c for c in required_keep_cols if c not in pop_work.columns]
    if missing_res:
        raise KeyError(f"居住人口表缺少列: {missing_res}")
    if missing_work:
        raise KeyError(f"工作人口表缺少列: {missing_work}")

    pop_res = pop_res[required_keep_cols].copy()
    pop_work = pop_work[required_keep_cols].copy()

    for col in industry_cols:
        pop_res[col] = pd.to_numeric(pop_res[col], errors='coerce').fillna(0)
        pop_work[col] = pd.to_numeric(pop_work[col], errors='coerce').fillna(0)

    res_ratio_sum = pop_res[industry_cols].sum(axis=1)
    work_ratio_sum = pop_work[industry_cols].sum(axis=1)
    res_nz = res_ratio_sum > 0
    work_nz = work_ratio_sum > 0
    pop_res.loc[res_nz, industry_cols] = pop_res.loc[res_nz, industry_cols].div(res_ratio_sum[res_nz], axis=0)
    pop_work.loc[work_nz, industry_cols] = pop_work.loc[work_nz, industry_cols].div(work_ratio_sum[work_nz], axis=0)

    od_df['起点网格ID'] = od_df['起点网格ID'].astype(str)
    od_df['终点网格ID'] = od_df['终点网格ID'].astype(str)
    od_df['人数'] = pd.to_numeric(od_df['人数'], errors='coerce').fillna(0)
    O_grid_list = od_df.groupby('起点网格ID', as_index=False)['人数'].sum()
    O_grid_list.columns = ['网格ID', '人数']
    D_grid_list = od_df.groupby('终点网格ID', as_index=False)['人数'].sum()
    D_grid_list.columns = ['网格ID', '人数']
    stats.add('O_grid_rows', len(O_grid_list))
    stats.add('D_grid_rows', len(D_grid_list))

    Or_zcq_grid = pop_res.merge(O_grid_list, on='网格ID', how='inner')
    Dr_zcq_grid = pop_work.merge(D_grid_list, on='网格ID', how='inner')
    stats.add('Or_zcq_grid_rows', len(Or_zcq_grid))
    stats.add('Dr_zcq_grid_rows', len(Dr_zcq_grid))

    for col in industry_cols:
        Or_zcq_grid[f'O人数{col}'] = Or_zcq_grid['人数'] * Or_zcq_grid[col]
        Dr_zcq_grid[f'D人数{col}'] = Dr_zcq_grid['人数'] * Dr_zcq_grid[col]

    Or_taz_adj = Or_zcq_grid.groupby('taz', as_index=False)['人数'].sum()
    Dr_taz_adj = Dr_zcq_grid.groupby('taz', as_index=False)['人数'].sum()
    for col in industry_cols:
        o_col = f'O人数{col}'
        d_col = f'D人数{col}'
        o_sum = Or_zcq_grid.groupby('taz')[o_col].sum()
        d_sum = Dr_zcq_grid.groupby('taz')[d_col].sum()
        Or_taz_adj[o_col] = Or_taz_adj['taz'].map(o_sum).fillna(0)
        Dr_taz_adj[d_col] = Dr_taz_adj['taz'].map(d_sum).fillna(0)
        Or_taz_adj[col] = np.where(Or_taz_adj['人数'] > 0, Or_taz_adj[o_col] / Or_taz_adj['人数'], 0)
        Dr_taz_adj[col] = np.where(Dr_taz_adj['人数'] > 0, Dr_taz_adj[d_col] / Dr_taz_adj['人数'], 0)

    O_taz = Or_taz_adj.copy()
    D_taz = Dr_taz_adj.copy()
    O_taz['taz'] = O_taz['taz'].astype(str)
    D_taz['taz'] = D_taz['taz'].astype(str)

    O_totals = np.array([O_taz[f'O人数{col}'].sum() for col in industry_cols], dtype=float)
    D_totals = np.array([D_taz[f'D人数{col}'].sum() for col in industry_cols], dtype=float)

    industry_avg = (O_totals + D_totals) / 2
    scale_O = np.divide(industry_avg, O_totals, out=np.ones_like(industry_avg), where=O_totals != 0)
    scale_D = np.divide(industry_avg, D_totals, out=np.ones_like(industry_avg), where=D_totals != 0)
    for i, col in enumerate(industry_cols):
        o_col = f'O人数{col}'
        d_col = f'D人数{col}'
        O_taz[o_col] = O_taz[o_col] * scale_O[i]
        D_taz[d_col] = D_taz[d_col] * scale_D[i]

    for col in industry_cols:
        O_taz[col] = np.where(O_taz['人数'] > 0, O_taz[f'O人数{col}'] / O_taz['人数'], 0)
        D_taz[col] = np.where(D_taz['人数'] > 0, D_taz[f'D人数{col}'] / D_taz['人数'], 0)

    O_totals_adj = np.array([O_taz[f'O人数{col}'].sum() for col in industry_cols], dtype=float)
    D_totals_adj = np.array([D_taz[f'D人数{col}'].sum() for col in industry_cols], dtype=float)

    official_stats = {
        "（一）农、林、牧、渔业": 799,
        "（二）采矿业": 434,
        "（三）制造业": 320280,
        "（四）电力、热力、燃气及水生产和供应业": 9888,
        "（五）建筑业": 172085,
        "（六）批发和零售业": 93523,
        "（七）交通运输、仓储和邮政业": 62840,
        "（八）住宿和餐饮业": 36278,
        "（九）信息传输、软件和信息技术服务业": 47273,
        "（十）金融业": 68532,
        "（十一）房地产业": 54054,
        "（十二）租赁和商务服务业": 51375,
        "（十三）科学研究和技术服务业": 70740,
        "（十四）水利、环境和公共设施管理业": 18105,
        "（十五）居民服务、修理和其他服务业": 8585,
        "（十六）教育": 156698,
        "（十七）卫生和社会工作": 94800,
        "（十八）文化、体育和娱乐业": 24769,
        "（十九）公共管理、社会保障和社会组织": 110284,
    }
    mapping_rules = {
        "农林牧渔": {"（一）农、林、牧、渔业": 1.0},
        "能源采矿化工": {"（三）制造业": 1.0},
        "食品加工": {"（三）制造业": 1.0},
        "纺织服装": {"（三）制造业": 1.0},
        "建材家居": {"（三）制造业": 1.0},
        "医药卫生": {"（三）制造业": 1.0},
        "机械制造": {"（三）制造业": 1.0},
        "汽车": {"（三）制造业": 1.0},
        "IT通信电子": {"（三）制造业": 1.0},
        "建筑房地产": {"（五）建筑业": 1.0},
        "交通运输和仓储": {"（七）交通运输、仓储和邮政业": 1.0},
        "餐饮": {"（八）住宿和餐饮业": 1.0},
        "家电": {"（三）制造业": 1.0},
        "日化百货": {"（六）批发和零售业": 1.0},
        "金融保险": {"（十）金融业": 1.0},
        "生活服务": {"（十五）居民服务、修理和其他服务业": 1.0},
        "住宿旅游": {"（八）住宿和餐饮业": 1.0},
        "广告营销": {"（十三）科学研究和技术服务业": 1.0},
        "法律商务人力外贸": {"（十二）租赁和商务服务业": 1.0},
        "科学研究": {"（十三）科学研究和技术服务业": 1.0},
        "教育": {"（十六）教育": 1.0},
        "文化体育娱乐": {"（十八）文化、体育和娱乐业": 1.0},
        "社会公共管理": {"（十四）水利、环境和公共设施管理业": 1.0},
    }

    official_keys = list(official_stats.keys())
    official_values = np.array([official_stats[k] for k in official_keys], dtype=float)
    official_prop = official_values / official_values.sum()
    mapped_O_dict = {k: 0.0 for k in official_keys}
    mapped_D_dict = {k: 0.0 for k in official_keys}
    industry_names = [c.replace('行业:', '') for c in industry_cols]
    for i, industry_name in enumerate(industry_names):
        if industry_name not in mapping_rules:
            continue
        for off_hy, weight in mapping_rules[industry_name].items():
            mapped_O_dict[off_hy] += float(O_totals_adj[i]) * weight
            mapped_D_dict[off_hy] += float(D_totals_adj[i]) * weight

    mapped_O = np.array([mapped_O_dict[k] for k in official_keys], dtype=float)
    mapped_D = np.array([mapped_D_dict[k] for k in official_keys], dtype=float)
    prop_mapped_O = mapped_O / mapped_O.sum() if mapped_O.sum() > 0 else mapped_O
    prop_mapped_D = mapped_D / mapped_D.sum() if mapped_D.sum() > 0 else mapped_D

    from scipy.stats import pearsonr
    corr_off_O, _ = pearsonr(official_prop, prop_mapped_O)
    corr_off_D, _ = pearsonr(official_prop, prop_mapped_D)
    prop_O = O_totals_adj / O_totals_adj.sum() if O_totals_adj.sum() > 0 else O_totals_adj
    prop_D = D_totals_adj / D_totals_adj.sum() if D_totals_adj.sum() > 0 else D_totals_adj
    corr_od_total, _ = pearsonr(prop_O, prop_D)

    summary_df = pd.DataFrame({
        '指标': [
            'O端-官方Pearson',
            'D端-官方Pearson',
            '主城区总O-D比例Pearson',
            '同步后行业最大绝对差值'
        ],
        '值': [
            corr_off_O,
            corr_off_D,
            corr_od_total,
            float(np.abs(O_totals_adj - D_totals_adj).max())
        ]
    })

    stats.add('corr_off_O', corr_off_O)
    stats.add('corr_off_D', corr_off_D)
    stats.add('corr_od_total', corr_od_total)
    stats.add('O_taz_rows', len(O_taz))
    stats.add('D_taz_rows', len(D_taz))
    stats.save('ratio_extract_stats.csv')

    return {
        'grid_taz_map': grid_taz_map,
        'od_df': od_df,
        'Or_orgin': pop_res,
        'Dr_orgin': pop_work,
        'pop_res': pop_res,
        'pop_work': pop_work,
        'industry_cols': industry_cols,
        'O_grid_list': O_grid_list,
        'D_grid_list': D_grid_list,
        'Or_zcq_grid': Or_zcq_grid,
        'Dr_zcq_grid': Dr_zcq_grid,
        'Or_taz_adj': Or_taz_adj,
        'Dr_taz_adj': Dr_taz_adj,
        'O_taz': O_taz,
        'D_taz': D_taz,
        'O_totals': O_totals,
        'D_totals': D_totals,
        'O_totals_adj': O_totals_adj,
        'D_totals_adj': D_totals_adj,
        'official_keys': official_keys,
        'official_prop': official_prop,
        'mapped_O': mapped_O,
        'mapped_D': mapped_D,
        'prop_mapped_O': prop_mapped_O,
        'prop_mapped_D': prop_mapped_D,
        'corr_off_O': corr_off_O,
        'corr_off_D': corr_off_D,
        'corr_od_total': corr_od_total,
        'summary_df': summary_df,
    }


def load_fence(shp_path=None):
    """加载地理围栏，并按taz dissolve去重"""
    shp_path = shp_path or SHP_PATH
    
    try:
        fence = gpd.read_file(shp_path, encoding='GBK')
    except:
        try:
            fence = gpd.read_file(shp_path, encoding='GB2312')
        except:
            fence = gpd.read_file(shp_path)
    
    logger.info(f'地理围栏原始行数: {len(fence)}, unique taz: {fence["taz"].nunique()}, CRS={fence.crs}')
    
    # 按taz dissolve去重
    fence_dissolved = fence.dissolve(by='taz', as_index=False)
    
    # 保留需要的列
    keep_cols = ['taz', 'geometry']
    for c in ['center_x', 'center_y', 'UTM_x', 'UTM_y']:
        if c in fence_dissolved.columns:
            keep_cols.append(c)
    
    fence_dissolved = fence_dissolved[keep_cols]
    logger.info(f'dissolve后行数: {len(fence_dissolved)}')
    
    return fence_dissolved
