"""
通勤研究项目 - 主流程管道
================================

执行顺序：
1. Data_Preprocess         - 读取原始数据，生成O/D/C/T矩阵
2.1 Theoretical_Pattern    - 理想格局（已有，直接读入）
2.2 Baseline_Pattern       - Wilson标定beta，输出基线格局
2.3 Random_Pattern         - beta=0，输出随机格局
2.4 Prob_to_Int Baseline   - 基线格局整数化
2.5 Prob_to_Int Random     - 随机格局整数化
3.1 Basic_Stats            - 四个格局统计信息
3.4 Pattern_Comparison     - 四对差值统计 + KL散度
"""

# %% [markdown]
# # 通勤研究项目 - 主流程管道

# %%
import sys
import json
from datetime import datetime
from pathlib import Path

project_root = Path(r"E:\00_Commute_Scenario_Research")
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
import geopandas as gpd

from src import (
    STATIC_CSV, DISTANCE_CSV, OD_CSV, SHP_PATH,
    RESULTS_DIR, get_result_path,
    StatsCollector, save_matrix, load_matrix,
    validate_od_consistency, logger,
)
from src.data_prep import (
    df_to_matrix, matrix_to_long_df, prob_to_int,
    prob_to_int_constrained, distance_combine, load_fence,
)
from src.metrics_eval import (
    compute_taz_indicators, compute_statistics,
    compute_diff, compute_diff_statistics,
    pattern_static_stats, pattern_flow_stats, compute_kl,
)
from src.models_pattern import compute_wilson, calibrate_beta
from src.config import WILSON_DEFAULT_BETA

RUN_TS = datetime.now().strftime('%Y%m%d_%H%M%S')
print("=" * 60)
print(f"通勤研究项目 - 主流程管道  [{RUN_TS}]")
print("=" * 60)

# %% [markdown]
# ## 1. Data_Preprocess
# 读取原始数据，转换为矩阵格式

# %%
print("\n" + "=" * 60)
print("## 1. Data_Preprocess")
print("=" * 60)

# 读取 O/D 列表
static_result = df_to_matrix(STATIC_CSV, data_type="static")
O_raw = static_result['O_list']   # shape (max_taz+1, 1)
D_raw = static_result['D_list']

# 展平为 1D
O_array = O_raw.flatten().astype(float)
D_array = D_raw.flatten().astype(float)

# 读取 C 矩阵（距离）
C_matrix = df_to_matrix(DISTANCE_CSV, data_type="matrix", matrix_type="C")

# 读取 T 矩阵（实际 OD）
T_observed = df_to_matrix(OD_CSV, data_type="matrix", matrix_type="T")

print(f"\n数据准备完成:")
print(f"  O_array shape: {O_array.shape}")
print(f"  D_array shape: {D_array.shape}")
print(f"  C_matrix shape: {C_matrix.shape}")
print(f"  T_observed shape: {T_observed.shape}")
print(f"  总人数(O): {O_array.sum():.0f}")

# 验证
assert len(O_array) == 2427, f"O_array 长度错误: {len(O_array)}"
assert len(D_array) == 2427, f"D_array 长度错误: {len(D_array)}"
assert C_matrix.shape == (2427, 2427), f"C_matrix 形状错误: {C_matrix.shape}"
assert T_observed.shape == (2427, 2427), f"T_observed 形状错误: {T_observed.shape}"
print("\n[OK] 矩阵维度验证通过: 2427 x 2427")

# 保存矩阵
out_dir_1 = get_result_path('1.Data_Preprocess', 'placeholder').parent
save_matrix(O_array, out_dir_1 / 'O_array.npy')
save_matrix(D_array, out_dir_1 / 'D_array.npy')
save_matrix(C_matrix, out_dir_1 / 'C_matrix.npy')
save_matrix(T_observed, out_dir_1 / 'T_observed.npy')

# 加载地理围栏
fence = load_fence(SHP_PATH)
print(f"\n地理围栏加载完成: {len(fence)} 个TAZ")

# 构建距离字典（供后续 distance_combine 使用）
rows, cols = np.nonzero(C_matrix)
distance_dict = {(int(r), int(c)): float(C_matrix[r, c]) for r, c in zip(rows, cols)}
print(f"距离字典条目数: {len(distance_dict)}")

# %% [markdown]
# ## 2.1 Theoretical_Pattern
# 理想格局已有，直接读入

# %%
print("\n" + "=" * 60)
print("## 2.1 Theoretical_Pattern  (直接读入)")
print("=" * 60)

IDEAL_CSV = project_root / 'results' / '2.Pattern_Computation' / '2.1Theoretical_Pattern' / '理想格局-统一结构-0414.csv'
df_ideal_raw = pd.read_csv(IDEAL_CSV, encoding='utf-8-sig')
print(f"理想格局列名: {df_ideal_raw.columns.tolist()}")
print(f"理想格局行数: {len(df_ideal_raw)}")

# 统一列名为 o, d, 人数, distance
col_map = {}
cols_lower = {c.lower(): c for c in df_ideal_raw.columns}
# 尝试自动识别列
for c in df_ideal_raw.columns:
    cl = c.lower()
    if cl in ('htaz', 'o', 'origin'):
        col_map[c] = 'o'
    elif cl in ('jtaz', 'd', 'dest', 'destination'):
        col_map[c] = 'd'
    elif cl in ('flow', '人数', 'count', 'trips'):
        col_map[c] = '人数'
    elif cl in ('distance', 'distance_m', 'dist'):
        col_map[c] = 'distance'

df_ideal = df_ideal_raw.rename(columns=col_map)[['o', 'd', '人数', 'distance']].copy()
df_ideal['o'] = df_ideal['o'].astype(int)
df_ideal['d'] = df_ideal['d'].astype(int)
print(f"理想格局统一后列名: {df_ideal.columns.tolist()}")
print(f"理想格局总人数: {df_ideal['人数'].sum():.0f}")

# %% [markdown]
# ## 2.2 Baseline_Pattern
# Wilson 标定 beta，目标距离 5577.58 m

# %%
print("\n" + "=" * 60)
print("## 2.2 Baseline_Pattern  (Wilson 标定 beta)")
print("=" * 60)

TARGET_DISTANCE = 5577.58

calib = calibrate_beta(
    O=O_array, D=D_array, C=C_matrix,
    target_distance=TARGET_DISTANCE,
    beta_range=(0.0001, 0.001),
    coarse_step=0.0001,
    fine_range=0.0001,
    fine_step=0.00001,
    max_iter=50,
)
best_beta = calib['best_beta']
print(f"\n标定结果:")
print(f"  best_beta    = {best_beta:.6f}")
print(f"  model_dist   = {calib['model_distance']:.4f} m")
print(f"  target_dist  = {TARGET_DISTANCE} m")
print(f"  error        = {calib['error']:.4f} m ({calib['error_pct']:.4f}%)")

assert calib['error_pct'] < 1.0, f"标定误差过大: {calib['error_pct']:.4f}%"
print("[OK] 标定误差 < 1%")

# 用最优 beta 计算基线格局
baseline_result = compute_wilson(
    O=O_array, D=D_array, C=C_matrix,
    beta=best_beta,
    max_iter=50,
    return_details=True
)
T_baseline = baseline_result['T_model']
print(f"\nWilson 基线格局:")
print(f"  avg_dist   = {baseline_result['avg_dist']:.4f} m")
print(f"  total_flow = {baseline_result['total_flow']:.0f}")
print(f"  iterations = {baseline_result['iterations']}")
print(f"  row_err    = {baseline_result['row_constraint_error']:.6f}")
print(f"  col_err    = {baseline_result['col_constraint_error']:.6f}")

# 保存
out_dir_22 = get_result_path('2.Pattern_Computation/2.2Baseline_Pattern', 'placeholder').parent
out_dir_22.mkdir(parents=True, exist_ok=True)
save_matrix(T_baseline, out_dir_22 / 'T_baseline_float.npy')
pd.DataFrame(calib['sweep_data']).to_csv(
    out_dir_22 / 'calibration_sweep.csv', index=False, encoding='utf-8-sig')
pd.DataFrame([{
    'best_beta': best_beta,
    'model_distance': calib['model_distance'],
    'target_distance': TARGET_DISTANCE,
    'error': calib['error'],
    'error_pct': calib['error_pct'],
}]).to_csv(out_dir_22 / 'calibration_summary.csv', index=False, encoding='utf-8-sig')
print(f"\n基线格局已保存至: {out_dir_22}")

# %% [markdown]
# ## 2.3 Random_Pattern
# beta=0，输出随机格局

# %%
print("\n" + "=" * 60)
print("## 2.3 Random_Pattern  (beta=0)")
print("=" * 60)

random_result = compute_wilson(
    O=O_array, D=D_array, C=C_matrix,
    beta=0.0,
    max_iter=50,
    return_details=True
)
T_random = random_result['T_model']
print(f"\nWilson 随机格局 (beta=0):")
print(f"  avg_dist   = {random_result['avg_dist']:.4f} m")
print(f"  total_flow = {random_result['total_flow']:.0f}")
print(f"  iterations = {random_result['iterations']}")

out_dir_23 = get_result_path('2.Pattern_Computation/2.3Random_Pattern', 'placeholder').parent
out_dir_23.mkdir(parents=True, exist_ok=True)
save_matrix(T_random, out_dir_23 / 'T_random_float.npy')
pd.DataFrame([{
    'beta': 0.0,
    'avg_dist': random_result['avg_dist'],
    'total_flow': random_result['total_flow'],
    'iterations': random_result['iterations'],
}]).to_csv(out_dir_23 / 'random_summary.csv', index=False, encoding='utf-8-sig')
print(f"随机格局已保存至: {out_dir_23}")

# %% [markdown]
# ## 2.4 Prob_to_Int — Baseline Pattern Integerization

# %%
print("\n" + "=" * 60)
print("## 2.4 Prob_to_Int — Baseline Pattern Integerization")
print("=" * 60)

target_total = int(O_array.sum())
print(f"目标总人数: {target_total}")

df_baseline_float = matrix_to_long_df(T_baseline, value_name='人数', o_col='o', d_col='d')
out_dir_24 = get_result_path('2.Pattern_Computation/2.4Baseline_Int', 'placeholder').parent
out_dir_24.mkdir(parents=True, exist_ok=True)

df_baseline_int = prob_to_int(
    df_prob=df_baseline_float,
    target_total=target_total,
    output_dir=out_dir_24,
)
df_baseline_int = distance_combine(df_baseline_int, distance_dict)

assert df_baseline_int['人数'].sum() == target_total, \
    f"整数化总量不匹配: {df_baseline_int['人数'].sum()} != {target_total}"
print(f"[OK] 基线整数化总量: {df_baseline_int['人数'].sum()}")
print(f"     OD对数: {len(df_baseline_int)}")

df_baseline_int.to_csv(
    out_dir_24 / 'star_baseline_int.csv', index=False, encoding='utf-8-sig')
print(f"基线整数化结果已保存至: {out_dir_24 / 'star_baseline_int.csv'}")

# %% [markdown]
# ## 2.5 Prob_to_Int — Random Pattern Integerization

# %%
print("\n" + "=" * 60)
print("## 2.5 Prob_to_Int — Random Pattern Integerization")
print("=" * 60)

df_random_float = matrix_to_long_df(T_random, value_name='人数', o_col='o', d_col='d')
out_dir_25 = get_result_path('2.Pattern_Computation/2.5Random_Int', 'placeholder').parent
out_dir_25.mkdir(parents=True, exist_ok=True)

df_random_int = prob_to_int(
    df_prob=df_random_float,
    target_total=target_total,
    output_dir=out_dir_25,
)
df_random_int = distance_combine(df_random_int, distance_dict)

assert df_random_int['人数'].sum() == target_total, \
    f"整数化总量不匹配: {df_random_int['人数'].sum()} != {target_total}"
print(f"[OK] 随机整数化总量: {df_random_int['人数'].sum()}")
print(f"     OD对数: {len(df_random_int)}")

df_random_int.to_csv(
    out_dir_25 / 'star_random_int.csv', index=False, encoding='utf-8-sig')
print(f"随机整数化结果已保存至: {out_dir_25 / 'star_random_int.csv'}")

# %% [markdown]
# ## 3.1 Basic_Stats — Pattern Statistics
# 对四个格局分别计算 TAZ 级别指标、静态统计、动态统计

# %%
print("\n" + "=" * 60)
print("## 3.1 Basic_Stats — Pattern Statistics")
print("=" * 60)

# 读入实际格局
ACTUAL_CSV = project_root / 'results' / '1.Data_Preprocess' / '实际格局-统一结构.csv'
df_actual_raw = pd.read_csv(ACTUAL_CSV, encoding='utf-8-sig')
print(f"实际格局列名: {df_actual_raw.columns.tolist()}")

# 统一列名
col_map_actual = {}
for c in df_actual_raw.columns:
    cl = c.lower()
    if cl in ('htaz', 'o', 'origin'):
        col_map_actual[c] = 'o'
    elif cl in ('jtaz', 'd', 'dest', 'destination'):
        col_map_actual[c] = 'd'
    elif cl in ('flow', '人数', 'count', 'trips'):
        col_map_actual[c] = '人数'
    elif cl in ('distance', 'distance_m', 'dist'):
        col_map_actual[c] = 'distance'

df_actual = df_actual_raw.rename(columns=col_map_actual)[['o', 'd', '人数', 'distance']].copy()
df_actual['o'] = df_actual['o'].astype(int)
df_actual['d'] = df_actual['d'].astype(int)
print(f"实际格局总人数: {df_actual['人数'].sum():.0f}")

# 四个格局
patterns = {
    'actual':   df_actual,
    'ideal':    df_ideal,
    'baseline': df_baseline_int,
    'random':   df_random_int,
}

out_dir_31 = get_result_path('3.1Basic_Stats', 'placeholder').parent
out_dir_31.mkdir(parents=True, exist_ok=True)
# 输出到 _new 子目录，避免 IDE 文件锁定导致覆盖失败
out_dir_31_new = out_dir_31 / '_new'
out_dir_31_new.mkdir(parents=True, exist_ok=True)

gdfs = {}
for name, df in patterns.items():
    print(f"\n  [{name}] 计算 TAZ 指标...")
    gdf = compute_taz_indicators(
        df_od=df, fence=fence,
        o_col='o', d_col='d',
        value_col='人数', distance_col='distance'
    )

    # taz_indicators 仅保留在内存中供 3.4 差值计算使用，不保存 CSV

    # 静态统计和动态统计只重跑 baseline/random
    if name in ('baseline', 'random'):
        pattern_static_stats(
            df_od=df, name=name, output_dir=out_dir_31_new,
            o_col='o', d_col='d', value_col='人数', distance_col='distance'
        )
        pattern_flow_stats(
            df_od=df, name=name, output_dir=out_dir_31_new,
            o_col='o', d_col='d', value_col='人数', distance_col='distance'
        )

    gdfs[name] = gdf
    print(f"    TAZ数: {len(gdf)}, 平均通勤距离: {gdf['平均通勤距离'].mean():.2f} m")

# 尝试将 _new 中的文件移动到正式目录，跳过被锁定的文件
import shutil, os
moved, skipped = [], []
for f in out_dir_31_new.iterdir():
    dst = out_dir_31 / f.name
    try:
        shutil.copy2(f, dst)
        moved.append(f.name)
    except PermissionError:
        skipped.append(f.name)
        print(f"  [SKIP] {f.name} 被锁定，保留在 _new/ 中")
if not skipped:
    shutil.rmtree(out_dir_31_new)
print(f"\n3.1 统计结果已保存至: {out_dir_31}")
if skipped:
    print(f"  注意: {len(skipped)} 个文件因锁定保留在 {out_dir_31_new}")

# %% [markdown]
# ## 3.4 Pattern_Comparison — Diff Statistics
# 四对差值统计 + KL 散度

# %%
print("\n" + "=" * 60)
print("## 3.4 Pattern_Comparison — Diff Statistics")
print("=" * 60)

out_dir_34 = get_result_path('3.4Pattern_Comparison', 'placeholder').parent
out_dir_34.mkdir(parents=True, exist_ok=True)

pairs = [
    ('actual',   'ideal',    '实际-理想'),
    ('actual',   'baseline', '实际-基线'),
    ('actual',   'random',   '实际-随机'),
    ('random',   'ideal',    '随机-理想'),
]

for name_a, name_b, label in pairs:
    print(f"\n  [{label}] 差值统计...")

    # TAZ 级差值
    gdf_diff = compute_diff(
        gdfs[name_a], gdfs[name_b],
        name_a=name_a, name_b=name_b,
        fence=fence,
        output_dir=out_dir_34,
    )
    compute_diff_statistics(gdf_diff, name_a=name_a, name_b=name_b, save=False)

    # 保存差值 GeoDataFrame
    gdf_diff_out = gdf_diff.drop(columns='geometry', errors='ignore')
    gdf_diff_out.to_csv(
        out_dir_34 / f'star_diff_{name_a}_vs_{name_b}.csv',
        index=False, encoding='utf-8-sig'
    )

    # KL 散度
    kl = compute_kl(
        df_a=patterns[name_a], df_b=patterns[name_b],
        name_a=name_a, name_b=name_b,
        value_col='人数', o_col='o', d_col='d',
        output_dir=out_dir_34,
    )
    print(f"    KL(A||B)={kl['kl_a_to_b']:.4f}, JSD={kl['jsd']:.4f}")

    # OD 级差值统计（flow stats，is_diff=True）
    df_merged = patterns[name_a].merge(
        patterns[name_b][['o', 'd', '人数']].rename(columns={'人数': '人数_b'}),
        on=['o', 'd'], how='outer'
    ).fillna(0)
    df_merged['差值'] = df_merged['人数'] - df_merged['人数_b']
    if 'distance' not in df_merged.columns:
        df_merged = distance_combine(df_merged, distance_dict)

    pattern_flow_stats(
        df_od=df_merged,
        name=f'diff_{name_a}_{name_b}',
        output_dir=out_dir_34,
        o_col='o', d_col='d',
        value_col='差值', distance_col='distance',
        is_diff=True,
    )

print(f"\n3.4 对比结果已保存至: {out_dir_34}")

# %% [markdown]
# ## 日志输出

# %%
print("\n" + "=" * 60)
print("写入运行日志")
print("=" * 60)

log_dir = project_root / 'log'
log_dir.mkdir(parents=True, exist_ok=True)
log_path = log_dir / f'run_{RUN_TS}.md'

log_content = f"""# Run Log — {RUN_TS.replace('_', ' ')}

## 输入
- STATIC_CSV: {STATIC_CSV}
- DISTANCE_CSV: {DISTANCE_CSV}
- OD_CSV: {OD_CSV}
- IDEAL_CSV: {IDEAL_CSV}
- ACTUAL_CSV: {ACTUAL_CSV}

## 执行步骤
1. Data_Preprocess — O/D/C/T 矩阵转换，2427x2427
2. Theoretical_Pattern — 理想格局直接读入，{len(df_ideal)} 条OD，总人数 {df_ideal['人数'].sum():.0f}
3. Baseline_Pattern — calibrate_beta, best_beta={best_beta:.6f}, avg_dist={baseline_result['avg_dist']:.2f} m
4. Random_Pattern — beta=0, avg_dist={random_result['avg_dist']:.2f} m
5. Prob_to_Int Baseline — total={df_baseline_int['人数'].sum()}, OD对={len(df_baseline_int)}
6. Prob_to_Int Random — total={df_random_int['人数'].sum()}, OD对={len(df_random_int)}
7. Basic_Stats — 四个格局 TAZ 指标 + 静态/动态统计
8. Pattern_Comparison — 四对差值统计 + KL 散度

## 输出文件
- results/2.Pattern_Computation/2.2Baseline_Pattern/T_baseline_float.npy
- results/2.Pattern_Computation/2.2Baseline_Pattern/calibration_sweep.csv
- results/2.Pattern_Computation/2.2Baseline_Pattern/calibration_summary.csv
- results/2.Pattern_Computation/2.3Random_Pattern/T_random_float.npy
- results/2.Pattern_Computation/2.3Random_Pattern/random_summary.csv
- results/2.Pattern_Computation/2.4Baseline_Int/star_baseline_int.csv
- results/2.Pattern_Computation/2.5Random_Int/star_random_int.csv
- results/3.1Basic_Stats/star_taz_indicators_{{actual|ideal|baseline|random}}.csv
- results/3.1Basic_Stats/star_{{name}}_static_concise_stats.csv
- results/3.1Basic_Stats/star_{{name}}_flow_concise_stats.csv
- results/3.4Pattern_Comparison/star_diff_{{pair}}.csv（四个）
- results/3.4Pattern_Comparison/star_kl_{{pair}}.csv（四个）
"""

log_path.write_text(log_content, encoding='utf-8')
print(f"日志已写入: {log_path}")

print("\n" + "=" * 60)
print(f"主流程执行完成!  [{RUN_TS}]")
print("=" * 60)
