# -*- coding: utf-8 -*-
"""
WFH 情景推演完整流程脚本
对应 spec: 06_scenario_WFH_v2.md
"""
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_result_path
from src.data_prep import matrix_to_long_df, prob_to_int, distance_combine
from src.elasticity import compute_scenario_uot
from src.metrics_eval import (
    pattern_static_stats, pattern_flow_stats,
    compute_kl, compute_diff, compute_diff_statistics, compute_taz_indicators,
)
from src.visualization import (
    create_choropleth_map, create_diverging_map,
    create_flowline, create_distribution_plot, create_distance_pdf,
)
from src.utils import logger

SCENARIO_LABEL = 'rigidity_WFH'
PEOPLE_COL = 'people'  # 统一用 ASCII 列名，避免 Windows 控制台编码问题

# ── 步骤 1：读取刚性参数 ──────────────────────────────────────────────────────
logger.info("=== Step 1: load rigidity params ===")
rigidity_params = pd.read_csv(
    get_result_path('4.Scenario_Analysis/4.2Rigidity_Computation', 'star_rigidity_params.csv'),
    encoding='utf-8-sig'
)
theta_O_base = float(rigidity_params['theta_O'].iloc[0])
theta_D_base = float(rigidity_params['theta_D'].iloc[0])
beta_scenario = float(rigidity_params['beta'].iloc[0])
logger.info(f"theta_O={theta_O_base:.4f}, theta_D={theta_D_base:.4f}, beta={beta_scenario}")

# ── 读取基础数据 ──────────────────────────────────────────────────────────────
logger.info("=== Step 2: load base data ===")
DATA_DIR = Path('e:/00_Commute_Scenario_Research/data')

# 实际 OD 数据（Htaz=居住地, Jtaz=工作地, 人数）
df_actual = pd.read_csv(DATA_DIR / '[主城区]TAZ4-od聚合.csv', encoding='gbk')
df_actual.columns = ['o', 'd', PEOPLE_COL] + list(df_actual.columns[3:])
logger.info(f"actual OD: {len(df_actual)} rows, cols={df_actual.columns.tolist()}")

# 空间边界
fence = gpd.read_file(str(DATA_DIR / 'TAZ4_shapefile4326.shp'))
logger.info(f"fence: {len(fence)} rows, unique taz={fence['taz'].nunique()}")

# 距离矩阵
dist_df = pd.read_csv(DATA_DIR / '[主城区]TAZ4距离-完整版.csv', encoding='utf-8-sig')
distance_dict = {
    (int(row['Htaz']), int(row['Jtaz'])): float(row['distance_m'])
    for _, row in dist_df.iterrows()
}
logger.info(f"distance_dict: {len(distance_dict)} entries")

# 补充 distance 列
if 'distance' not in df_actual.columns:
    df_actual = distance_combine(df_actual, distance_dict)

# 构建 O/D 边际向量
all_taz = sorted(fence['taz'].astype(int).unique())
n_taz = len(all_taz)
taz_to_idx = {t: i for i, t in enumerate(all_taz)}
idx_to_taz = {i: t for t, i in taz_to_idx.items()}

O_array = np.zeros(n_taz)
D_array = np.zeros(n_taz)
for o_val, d_val, v in zip(df_actual['o'].values, df_actual['d'].values, df_actual[PEOPLE_COL].values):
    o_i, d_i = int(o_val), int(d_val)
    if o_i in taz_to_idx:
        O_array[taz_to_idx[o_i]] += float(v)
    if d_i in taz_to_idx:
        D_array[taz_to_idx[d_i]] += float(v)
logger.info(f"O_array sum={O_array.sum():.0f}, D_array sum={D_array.sum():.0f}")

# 构建距离矩阵
logger.info("building C_matrix...")
C_matrix = np.zeros((n_taz, n_taz))
for (o, d), dist in distance_dict.items():
    if o in taz_to_idx and d in taz_to_idx:
        C_matrix[taz_to_idx[o]][taz_to_idx[d]] = dist

# 零值用该行最小非零距离的一半替换
for i in range(n_taz):
    row_vals = C_matrix[i, :]
    nonzero_vals = row_vals[row_vals > 0]
    fill_val = nonzero_vals.min() * 0.5 if len(nonzero_vals) > 0 else 500.0
    C_matrix[i, row_vals == 0] = fill_val
logger.info(f"C_matrix shape={C_matrix.shape}, min={C_matrix.min():.1f}, max={C_matrix.max():.1f}")

# ── 步骤 3：UOT 情景推演 ──────────────────────────────────────────────────────
logger.info("=== Step 3: UOT scenario computation ===")
out_dir_43 = get_result_path(
    f'4.Scenario_Analysis/4.3Scenario_Computation/{SCENARIO_LABEL}', ''
)
out_dir_43.mkdir(parents=True, exist_ok=True)

scenario_result = compute_scenario_uot(
    C_matrix=C_matrix,
    O_array=O_array,
    D_array=D_array,
    theta_O=theta_O_base,
    theta_D=theta_D_base,
    beta=beta_scenario,
    rigidityO_multiplier=1.2,
    rigidityD_multiplier=0.8,
    scenario_label=SCENARIO_LABEL,
    output_dir=out_dir_43,
)
T_scenario_float = scenario_result['T_scenario']
logger.info(f"UOT done: avg_dist={scenario_result['avg_dist']:.2f} m, total={scenario_result['total_flow']:.0f}")

# ── 步骤 4：整数化 ────────────────────────────────────────────────────────────
logger.info("=== Step 4: prob_to_int ===")
target_total = int(O_array.sum())

df_float = matrix_to_long_df(T_scenario_float, value_name=PEOPLE_COL, o_col='o', d_col='d')
df_float['o'] = df_float['o'].map(idx_to_taz)
df_float['d'] = df_float['d'].map(idx_to_taz)
df_float = df_float.dropna(subset=['o', 'd'])
df_float['o'] = df_float['o'].astype(int)
df_float['d'] = df_float['d'].astype(int)

df_scenario_int = prob_to_int(
    df_prob=df_float,
    target_total=target_total,
    value_col=PEOPLE_COL,
    output_dir=out_dir_43,
)
df_scenario_int = distance_combine(df_scenario_int, distance_dict)

actual_total = int(df_scenario_int[PEOPLE_COL].sum())
assert actual_total == target_total, f"total mismatch: {actual_total} != {target_total}"
logger.info(f"int done: {len(df_scenario_int)} rows, total={actual_total}")

df_scenario_int.to_csv(
    out_dir_43 / f'star_{SCENARIO_LABEL}_int.csv',
    index=False, encoding='utf-8-sig', float_format='%.4f'
)

# ── 步骤 5：情景格局统计（4.4.1）────────────────────────────────────────────
logger.info("=== Step 5: pattern stats 4.4.1 ===")
out_dir_441 = get_result_path(
    f'4.Scenario_Analysis/4.4Scenario_Compare/4.4.1Scenario_Pattern_Stats/{SCENARIO_LABEL}', ''
)
out_dir_441.mkdir(parents=True, exist_ok=True)

pattern_static_stats(df_od=df_scenario_int, name=SCENARIO_LABEL, output_dir=out_dir_441,
                     value_col=PEOPLE_COL)
pattern_flow_stats(df_od=df_scenario_int, name=SCENARIO_LABEL, output_dir=out_dir_441,
                   value_col=PEOPLE_COL)
logger.info("pattern stats done")

# ── 步骤 6：情景与实际格局对比（4.4.2）──────────────────────────────────────
logger.info("=== Step 6: comparison 4.4.2 ===")
out_dir_442 = get_result_path(
    f'4.Scenario_Analysis/4.4Scenario_Compare/4.4.2Scenario_Actual_Compare/{SCENARIO_LABEL}', ''
)
out_dir_442.mkdir(parents=True, exist_ok=True)

kl_result = compute_kl(
    df_a=df_actual, df_b=df_scenario_int,
    name_a='actual', name_b=SCENARIO_LABEL,
    value_col=PEOPLE_COL,
    output_dir=out_dir_442,
)
logger.info(f"KL: kl_a_to_b={kl_result['kl_a_to_b']:.6f}, jsd={kl_result['jsd']:.6f}")

gdf_actual_taz = compute_taz_indicators(df_actual, fence, value_col=PEOPLE_COL)
gdf_scenario_taz = compute_taz_indicators(df_scenario_int, fence, value_col=PEOPLE_COL)
logger.info(f"TAZ indicators: actual={len(gdf_actual_taz)}, scenario={len(gdf_scenario_taz)}")

gdf_diff = compute_diff(
    gdf_a=gdf_actual_taz, gdf_b=gdf_scenario_taz,
    name_a='actual', name_b=SCENARIO_LABEL,
    fence=fence, output_dir=out_dir_442,
)
logger.info(f"diff GDF: {len(gdf_diff)} rows")

compute_diff_statistics(
    gdf_diff=gdf_diff, name_a='actual', name_b=SCENARIO_LABEL,
    save=True, output_dir=out_dir_442,
)

gdf_diff.drop(columns='geometry', errors='ignore').to_csv(
    out_dir_442 / f'star_diff_actual_vs_{SCENARIO_LABEL}.csv',
    index=False, encoding='utf-8-sig', float_format='%.4f'
)

# 色带正负检查
logger.info("=== colorbar sign check ===")
for col_base in ['total_people', 'avg_distance', 'internal_ratio',
                 '总通勤人数', '平均通勤距离', '内部通勤比']:
    diff_col = f'{col_base}_diff'
    if diff_col in gdf_diff.columns:
        vals = gdf_diff[diff_col].dropna()
        logger.info(
            f"  {diff_col}: min={vals.min():.2f}, max={vals.max():.2f}, "
            f"neg={(vals < 0).sum()}, pos={(vals > 0).sum()}"
        )

# ── 步骤 7：可视化（4.4.3）──────────────────────────────────────────────────
logger.info("=== Step 7: visualization 4.4.3 ===")
out_dir_443 = get_result_path(
    f'4.Scenario_Analysis/4.4Scenario_Compare/4.4.3Scenario_Compare_Visualize/{SCENARIO_LABEL}', ''
)
out_dir_443.mkdir(parents=True, exist_ok=True)

# 找到 gdf 中的人数列名（compute_taz_indicators 可能用中文或英文）
taz_people_col = '总通勤人数' if '总通勤人数' in gdf_scenario_taz.columns else 'total_people'
logger.info(f"TAZ people col: {taz_people_col}")

# 情景格局 O 端分布图
create_choropleth_map(
    gdf_data=gdf_scenario_taz, gdf_base=fence,
    column=taz_people_col, config_key='total_people',
    output_path=out_dir_443 / f'star_{SCENARIO_LABEL}_static_O.png',
)

# 情景格局 D 端分布图
gdf_scenario_taz_d = compute_taz_indicators(
    df_scenario_int, fence, o_col='d', d_col='o', value_col=PEOPLE_COL
)
create_choropleth_map(
    gdf_data=gdf_scenario_taz_d, gdf_base=fence,
    column=taz_people_col, config_key='total_people',
    output_path=out_dir_443 / f'star_{SCENARIO_LABEL}_static_D.png',
)

# 情景格局流线图
create_flowline(
    df_od=df_scenario_int, fence=fence,
    output_path=out_dir_443 / f'star_{SCENARIO_LABEL}_flowline.png',
    flow_col=PEOPLE_COL,
    is_diff=False,
)

# 差值地图（找到实际存在的 diff 列）
diff_people_col = '总通勤人数_diff' if '总通勤人数_diff' in gdf_diff.columns else 'total_people_diff'
create_diverging_map(
    gdf_data=gdf_diff, gdf_base=fence,
    column=diff_people_col,
    output_path=out_dir_443 / f'star_diff_actual_vs_{SCENARIO_LABEL}_O.png',
)
create_diverging_map(
    gdf_data=gdf_diff, gdf_base=fence,
    column=diff_people_col,
    output_path=out_dir_443 / f'star_diff_actual_vs_{SCENARIO_LABEL}_D.png',
)

# 差值流线图（实际 - 情景）
df_diff_merged = df_actual[['o', 'd', PEOPLE_COL]].merge(
    df_scenario_int[['o', 'd', PEOPLE_COL]].rename(columns={PEOPLE_COL: 'people_s'}),
    on=['o', 'd'], how='outer'
).fillna(0)
df_diff_merged[PEOPLE_COL] = df_diff_merged[PEOPLE_COL] - df_diff_merged['people_s']
df_diff_merged = df_diff_merged.drop(columns='people_s')
if 'distance' not in df_diff_merged.columns:
    df_diff_merged = distance_combine(df_diff_merged, distance_dict)

create_flowline(
    df_od=df_diff_merged, fence=fence,
    output_path=out_dir_443 / f'star_diff_actual_vs_{SCENARIO_LABEL}_flowline.png',
    flow_col=PEOPLE_COL,
    is_diff=True,
)

# 箱线图（横向，vert=False）
create_distribution_plot(
    df_a=df_actual, df_b=df_scenario_int,
    name_a='actual', name_b=SCENARIO_LABEL,
    output_path=out_dir_443 / f'star_diff_actual_vs_{SCENARIO_LABEL}_boxplot_people.png',
    col=PEOPLE_COL, cap=200.0,
)
create_distribution_plot(
    df_a=df_actual, df_b=df_scenario_int,
    name_a='actual', name_b=SCENARIO_LABEL,
    output_path=out_dir_443 / f'star_diff_actual_vs_{SCENARIO_LABEL}_boxplot_distance.png',
    col='distance', cap=None,
)

# 距离 PDF 图
create_distance_pdf(
    df_list=[df_actual, df_scenario_int],
    names=['actual', SCENARIO_LABEL],
    output_path=out_dir_443 / f'star_diff_actual_vs_{SCENARIO_LABEL}_distance_pdf.png',
)

logger.info("=== ALL STEPS DONE ===")
logger.info(f"4.3  -> {out_dir_43}")
logger.info(f"4.4.1 -> {out_dir_441}")
logger.info(f"4.4.2 -> {out_dir_442}")
logger.info(f"4.4.3 -> {out_dir_443}")
