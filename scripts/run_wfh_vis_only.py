# -*- coding: utf-8 -*-
"""
WFH 情景可视化重新输出脚本（仅可视化，从已有结果加载数据）
对应 spec: 06_scenario_WFH_v2.md 步骤 6
输出目录: results/4.Scenario_Analysis/4.4Scenario_Compare/4.4.3Scenario_Compare_Visualize/rigidity_WFH/
"""
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_result_path
from src.visualization import (
    create_diverging_map, create_distance_pdf,
)
from src.utils import logger

SCENARIO_LABEL = 'rigidity_WFH'
PEOPLE_COL = 'people'
DATA_DIR = Path('e:/00_Commute_Scenario_Research/data')

# ── 读取数据 ──────────────────────────────────────────────────────────────────
logger.info("=== 读取数据 ===")

# 实际 OD
df_actual = pd.read_csv(DATA_DIR / '[主城区]TAZ4-od聚合.csv', encoding='gbk')
df_actual.columns = ['o', 'd', PEOPLE_COL] + list(df_actual.columns[3:])

# 补充 distance 列
dist_df = pd.read_csv(DATA_DIR / '[主城区]TAZ4距离-完整版.csv', encoding='utf-8-sig')
distance_dict = {
    (int(r['Htaz']), int(r['Jtaz'])): float(r['distance_m'])
    for _, r in dist_df.iterrows()
}
if 'distance' not in df_actual.columns:
    df_actual['distance'] = df_actual.apply(
        lambda r: distance_dict.get((int(r['o']), int(r['d'])), np.nan), axis=1
    )
logger.info(f"actual OD: {len(df_actual)} rows")

# 情景整数 OD
df_scenario_int = pd.read_csv(
    get_result_path(f'4.Scenario_Analysis/4.3Scenario_Computation/{SCENARIO_LABEL}',
                    f'star_{SCENARIO_LABEL}_int.csv'),
    encoding='utf-8-sig'
)
# 统一人数列名为 PEOPLE_COL
if 'people' not in df_scenario_int.columns:
    people_col_s = [c for c in df_scenario_int.columns if c not in ('o', 'd', 'distance')][0]
    df_scenario_int = df_scenario_int.rename(columns={people_col_s: PEOPLE_COL})
logger.info(f"scenario int OD: {len(df_scenario_int)} rows")

# TAZ 差值 GDF
fence = gpd.read_file(str(DATA_DIR / 'TAZ4_shapefile4326.shp'))
diff_csv = get_result_path(
    f'4.Scenario_Analysis/4.4Scenario_Compare/4.4.2Scenario_Actual_Compare/{SCENARIO_LABEL}',
    f'star_diff_actual_vs_{SCENARIO_LABEL}.csv'
)
df_diff = pd.read_csv(diff_csv, encoding='utf-8-sig')
gdf_diff = fence.drop_duplicates(subset='taz').merge(df_diff, on='taz', how='left')
logger.info(f"diff GDF: {len(gdf_diff)} rows, cols={[c for c in gdf_diff.columns if 'diff' in c]}")

# ── 输出目录 ──────────────────────────────────────────────────────────────────
out_dir_443 = get_result_path(
    f'4.Scenario_Analysis/4.4Scenario_Compare/4.4.3Scenario_Compare_Visualize/{SCENARIO_LABEL}', ''
)
out_dir_443.mkdir(parents=True, exist_ok=True)

# ── 差值地图（图幅已改为 15.3, 14）────────────────────────────────────────────
logger.info("=== 差值地图 ===")
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

# ── 人数 PDF（截尾 80%，按人数加权）──────────────────────────────────────────
logger.info("=== 人数 PDF ===")
create_distance_pdf(
    df_list=[df_actual, df_scenario_int],
    names=['actual', SCENARIO_LABEL],
    output_path=out_dir_443 / f'star_diff_actual_vs_{SCENARIO_LABEL}_people_pdf.png',
    col=PEOPLE_COL,
    weight_col=PEOPLE_COL,
    cap_quantile=0.8,
    x_label='OD 对通勤人数 (人)',
)

# ── 距离 PDF（两格局分布对比，按人数加权，截尾 20km）────────────────────────
logger.info("=== 距离 PDF ===")
create_distance_pdf(
    df_list=[df_actual, df_scenario_int],
    names=['actual', SCENARIO_LABEL],
    output_path=out_dir_443 / f'star_diff_actual_vs_{SCENARIO_LABEL}_distance_pdf.png',
    col='distance',
    weight_col=PEOPLE_COL,
    cap_abs=20000,
    unit_scale=1/1000,
    x_label='通勤距离 (km)',
)

logger.info("=== 可视化完成 ===")
logger.info(f"输出目录: {out_dir_443}")
