# 情景设定：WFH 居家办公趋势下的通勤情景演变（v2）

> 本文件是 `06_scenario_WFH.md` 的修订版，主要变更：
> 1. `compute_scenario_uot` 函数签名更新为双系数（`rigidityO_multiplier` / `rigidityD_multiplier`）
> 2. 补充整数化步骤（4.3.5）
> 3. 明确箱线图横向排列要求及 `create_distribution_plot` 修改说明
> 4. 明确 `create_diverging_map` 色带正负检查步骤
> 5. 输出路径统一到 `{scenario_label}` 子文件夹
> 6. 补充 PDF 距离分布图输出

---

## 政策背景

### 长沙市政策导向：稳定居住，降低工作摩擦

1. 《长沙市国土空间总体规划（2021-2035）》"15分钟生活圈"建设：目标是让居民就地享受高品质生活，不是鼓励搬家，而是让人们不必搬家。
2. 湖南省新就业形态政策：打破就业地与社保绑定，降低的是工作端摩擦，对居住端毫无松动作用。
3. 长沙"青年友好城市"建设：提供人才公寓、购房补贴，这些政策是为了稳定居住，不是促进流动。
4. 城市更新行动（《长沙市全面推进城市更新行动方案(2026-2030年)》）：通过老旧小区改造、15分钟生活圈建设，大幅提升现有居住地宜居性，居民"留守"意愿和沉没成本感知增强。
5. 数字经济政策（马栏山、岳麓山大科城）：主要利好工作端的灵活匹配（平台化、虚拟协作），而非直接降低搬家门槛。

**总结**：O 端（居住地）刚性提升，D 端（工作地）刚性降低。

---

## 情景参数设定

**情景名称**：WFH 居家办公趋势——居住地刚性提升 20%，工作地刚性降低 20%

| 参数 | 值 | 说明 |
|---|---|---|
| `rigidityO_multiplier` | `1.2` | 居住地 O 端刚性提升 20% |
| `rigidityD_multiplier` | `0.8` | 工作地 D 端刚性降低 20% |
| `scenario_label` | `'rigidity_WFH'` | 文件命名标识 |

**模拟机制**：
- O 端 θ 提升 → τ_O 增大 → 居住地分布更难偏离现状（更难搬家）
- D 端 θ 降低 → τ_D 减小 → 就业地分布更容易偏离现状（更容易换工作/接受远距离通勤）
- 总通勤人数 M 保持不变

---

## 预期结果方向

| 指标 | 预期变化 | 机制 |
|---|---|---|
| 平均通勤距离 | 增加 | D 端刚性降低，职住匹配更自由，部分人接受更远通勤换取更优岗位 |
| KL(O*\|\|O0) | 较小 | O 端刚性提升，居住分布偏离现状幅度受限 |
| KL(D*\|\|D0) | 较大 | D 端刚性降低，就业分布偏离现状幅度更大 |
| 与实际格局 JSD | 增加 | 情景格局与实际格局结构差异扩大 |

---

## 前置条件

- `src/elasticity.py` 中 `compute_scenario_uot` 已更新为双系数签名（见"代码修改"章节）
- `src/visualization.py` 中 `create_distribution_plot` 已修改为横向箱线图（`vert=False`）
- `results/4.Scenario_Analysis/4.2Rigidity_Computation/star_rigidity_params.csv` 已存在

---

## 代码修改

### 修改一：`src/elasticity.py` — `compute_scenario_uot` 双系数

将函数签名中的单一 `rigidity_multiplier` 拆分为两个独立系数：

```python
# 旧签名
def compute_scenario_uot(
    C_matrix, O_array, D_array, theta_O, theta_D, beta,
    rigidity_multiplier: float = 1.0,
    scenario_label: str = 'scenario',
    output_dir=None,
) -> dict:

# 新签名
def compute_scenario_uot(
    C_matrix: np.ndarray,
    O_array: np.ndarray,
    D_array: np.ndarray,
    theta_O: float,
    theta_D: float,
    beta: float,
    rigidityO_multiplier: float = 1.0,
    rigidityD_multiplier: float = 1.0,
    scenario_label: str = 'scenario',
    output_dir=None,
) -> dict:
```

内部逻辑同步修改：
```python
# 旧
theta_O_s = theta_O * rigidity_multiplier
theta_D_s = theta_D * rigidity_multiplier

# 新
theta_O_s = theta_O * rigidityO_multiplier
theta_D_s = theta_D * rigidityD_multiplier
```

`stats` 记录和 `summary_df` 保存中的 `rigidity_multiplier` 列也同步替换为两列。

### 修改二：`src/visualization.py` — `create_distribution_plot` 横向箱线图

spec 要求箱线图横轴为人数/距离，纵轴为格局名（横向排列）。需将 `ax.boxplot` 调用改为 `vert=False`，并交换轴标签：

```python
# 旧
bp = ax.boxplot([data_a, data_b], labels=[name_a, name_b], patch_artist=True, ...)
ax.set_ylabel(col, fontsize=24, fontfamily='SimHei')
for label in ax.get_xticklabels(): ...
ax.grid(True, axis='y', alpha=0.3)

# 新
bp = ax.boxplot([data_a, data_b], labels=[name_a, name_b], patch_artist=True,
                vert=False, ...)
ax.set_xlabel(col, fontsize=24, fontfamily='SimHei')
for label in ax.get_yticklabels(): ...
ax.grid(True, axis='x', alpha=0.3)
```

---

## 任务步骤

### 步骤 1：读取刚性参数

```python
import pandas as pd
import numpy as np
from src.config import get_result_path

rigidity_params = pd.read_csv(
    get_result_path('4.Scenario_Analysis/4.2Rigidity_Computation', 'star_rigidity_params.csv'),
    encoding='utf-8-sig'
)

# theta 值由米单位运算得出，C_matrix 单位为米时直接使用
theta_O_base = float(rigidity_params['theta_O'].iloc[0])
theta_D_base = float(rigidity_params['theta_D'].iloc[0])
beta_scenario = float(rigidity_params['beta'].iloc[0])
```

若整体运算改用千米单位，需将 theta 除以 1000：
```python
theta_O_base = theta_O_base / 1000
theta_D_base = theta_D_base / 1000
```

### 步骤 2：UOT 情景推演

```python
from src.elasticity import compute_scenario_uot

SCENARIO_LABEL = 'rigidity_WFH'
out_dir_43 = get_result_path(
    f'4.Scenario_Analysis/4.3Scenario_Computation/{SCENARIO_LABEL}', ''
)

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
```

### 步骤 3：整数化

```python
from src.data_prep import matrix_to_long_df, prob_to_int, distance_combine

target_total = int(O_array.sum())
df_scenario_float = matrix_to_long_df(T_scenario_float, value_name='人数', o_col='o', d_col='d')

df_scenario_int = prob_to_int(
    df_prob=df_scenario_float,
    target_total=target_total,
    output_dir=out_dir_43,
)
df_scenario_int = distance_combine(df_scenario_int, distance_dict)

assert df_scenario_int['人数'].sum() == target_total, \
    f"整数化总量不匹配: {df_scenario_int['人数'].sum()} != {target_total}"

df_scenario_int.to_csv(
    out_dir_43 / f'star_{SCENARIO_LABEL}_int.csv',
    index=False, encoding='utf-8-sig'
)
```

### 步骤 4：情景格局统计（4.4.1）

```python
from src.metrics_eval import pattern_static_stats, pattern_flow_stats

out_dir_441 = get_result_path(
    f'4.Scenario_Analysis/4.4Scenario_Compare/4.4.1Scenario_Pattern_Stats/{SCENARIO_LABEL}', ''
)

pattern_static_stats(df_od=df_scenario_int, name=SCENARIO_LABEL, output_dir=out_dir_441)
pattern_flow_stats(df_od=df_scenario_int, name=SCENARIO_LABEL, output_dir=out_dir_441)
```

### 步骤 5：情景与实际格局对比（4.4.2）

```python
from src.metrics_eval import compute_kl, compute_diff, compute_diff_statistics, compute_taz_indicators

out_dir_442 = get_result_path(
    f'4.Scenario_Analysis/4.4Scenario_Compare/4.4.2Scenario_Actual_Compare/{SCENARIO_LABEL}', ''
)

# KL 散度
kl_result = compute_kl(
    df_a=df_actual, df_b=df_scenario_int,
    name_a='actual', name_b=SCENARIO_LABEL,
    output_dir=out_dir_442,
)

# TAZ 级指标
gdf_actual_taz = compute_taz_indicators(df_actual, fence)
gdf_scenario_taz = compute_taz_indicators(df_scenario_int, fence)

# TAZ 级差值
gdf_diff = compute_diff(
    gdf_a=gdf_actual_taz, gdf_b=gdf_scenario_taz,
    name_a='actual', name_b=SCENARIO_LABEL,
    fence=fence, output_dir=out_dir_442,
)

# 差值统计
compute_diff_statistics(
    gdf_diff=gdf_diff, name_a='actual', name_b=SCENARIO_LABEL,
    save=True, output_dir=out_dir_442,
)

# 保存差值 CSV
gdf_diff.drop(columns='geometry', errors='ignore').to_csv(
    out_dir_442 / f'star_diff_actual_vs_{SCENARIO_LABEL}.csv',
    index=False, encoding='utf-8-sig'
)

# 色带正负检查（为 create_diverging_map 提供依据）
for col_base in ['总通勤人数', '平均通勤距离', '内部通勤比']:
    diff_col = f'{col_base}_diff'
    if diff_col in gdf_diff.columns:
        vals = gdf_diff[diff_col].dropna()
        print(f"  {diff_col}: min={vals.min():.2f}, max={vals.max():.2f}, "
              f"负值TAZ={(vals < 0).sum()}, 正值TAZ={(vals > 0).sum()}")
```

**色带正负说明**：`create_diverging_map` 内部逻辑：
- 若 `vmin < 0` 且 `vmax > 0`：使用 `TwoSlopeNorm`，色带含正负两侧（正常情况）
- 若 `vmin >= 0`：退化为单侧正值色带（极少数情况，实际格局所有 TAZ 均大于情景格局）
- 若 `vmax <= 0`：退化为单侧负值色带

上方打印输出可确认实际情况。

### 步骤 6：可视化（4.4.3）

```python
from src.visualization import (
    create_choropleth_map, create_diverging_map,
    create_flowline, create_distribution_plot, create_distance_pdf,
)

out_dir_443 = get_result_path(
    f'4.Scenario_Analysis/4.4Scenario_Compare/4.4.3Scenario_Compare_Visualize/{SCENARIO_LABEL}', ''
)
out_dir_443.mkdir(parents=True, exist_ok=True)

# 情景格局 O/D 端分布图
create_choropleth_map(
    gdf_data=gdf_scenario_taz, gdf_base=fence,
    column='总通勤人数', config_key='total_people',
    output_path=out_dir_443 / f'star_{SCENARIO_LABEL}_static_O.png',
)
create_choropleth_map(
    gdf_data=gdf_scenario_taz, gdf_base=fence,
    column='总通勤人数', config_key='total_people',
    output_path=out_dir_443 / f'star_{SCENARIO_LABEL}_static_D.png',
)

# 情景格局流线图
create_flowline(
    df_od=df_scenario_int, fence=fence,
    output_path=out_dir_443 / f'star_{SCENARIO_LABEL}_flowline.png',
    is_diff=False,
)

# 差值地图
create_diverging_map(
    gdf_data=gdf_diff, gdf_base=fence,
    column='总通勤人数_diff',
    output_path=out_dir_443 / f'star_diff_actual_vs_{SCENARIO_LABEL}_O.png',
)
create_diverging_map(
    gdf_data=gdf_diff, gdf_base=fence,
    column='总通勤人数_diff',
    output_path=out_dir_443 / f'star_diff_actual_vs_{SCENARIO_LABEL}_D.png',
)

# 差值流线图（实际 - 情景）
df_diff_merged = df_actual.merge(
    df_scenario_int[['o', 'd', '人数']].rename(columns={'人数': '人数_scenario'}),
    on=['o', 'd'], how='outer'
).fillna(0)
df_diff_merged['人数'] = df_diff_merged['人数'] - df_diff_merged['人数_scenario']
if 'distance' not in df_diff_merged.columns:
    df_diff_merged = distance_combine(df_diff_merged, distance_dict)

create_flowline(
    df_od=df_diff_merged, fence=fence,
    output_path=out_dir_443 / f'star_diff_actual_vs_{SCENARIO_LABEL}_flowline.png',
    is_diff=True,
)

# 箱线图（横向，vert=False 已在 create_distribution_plot 修改后生效）
create_distribution_plot(
    df_a=df_actual, df_b=df_scenario_int,
    name_a='actual', name_b=SCENARIO_LABEL,
    output_path=out_dir_443 / f'star_diff_actual_vs_{SCENARIO_LABEL}_boxplot_people.png',
    col='人数', cap=200.0,
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
```

---

## 输出文件清单

### 4.3Scenario_Computation/rigidity_WFH/

| 文件 | 说明 |
|---|---|
| `T_scenario_float.npy` | 情景 OD 矩阵（浮点） |
| `star_rigidity_WFH_int.csv` | 整数化情景 OD，列：o, d, 人数, distance |
| `scenario_computation_stats.csv` | 推演统计：迭代次数、总流量、平均距离、KL 偏离 |

### 4.4.1Scenario_Pattern_Stats/rigidity_WFH/

| 文件 | 说明 |
|---|---|
| `rigidity_WFH_static_all_stats.csv` | TAZ 级完整统计 |
| `star_rigidity_WFH_static_concise_stats.csv` | 全局汇总（1 行） |
| `rigidity_WFH_flow_all_stats.csv` | OD 流完整统计 |
| `star_rigidity_WFH_flow_concise_stats.csv` | 流统计汇总 |

### 4.4.2Scenario_Actual_Compare/rigidity_WFH/

| 文件 | 说明 |
|---|---|
| `star_kl_actual_rigidity_WFH.csv` | KL 散度（kl_a_to_b, kl_b_to_a, jsd） |
| `star_diff_actual_vs_rigidity_WFH.csv` | TAZ 级差值 CSV |
| `diff_actual_rigidity_WFH_flow_all_stats.csv` | 差值流完整统计 |
| `star_diff_actual_rigidity_WFH_flow_concise_stats.csv` | 差值流汇总 |

### 4.4.3Scenario_Compare_Visualize/rigidity_WFH/

| 文件 | 函数 | 说明 |
|---|---|---|
| `star_rigidity_WFH_static_O.png` | `create_choropleth_map` | 情景 O 端出行量分布 |
| `star_rigidity_WFH_static_D.png` | `create_choropleth_map` | 情景 D 端吸引量分布 |
| `star_rigidity_WFH_flowline.png` | `create_flowline` | 情景格局 OD 流线图 |
| `star_diff_actual_vs_rigidity_WFH_O.png` | `create_diverging_map` | O 端出行量差值地图 |
| `star_diff_actual_vs_rigidity_WFH_D.png` | `create_diverging_map` | D 端吸引量差值地图 |
| `star_diff_actual_vs_rigidity_WFH_flowline.png` | `create_flowline` | OD 流线差值图 |
| `star_diff_actual_vs_rigidity_WFH_boxplot_people.png` | `create_distribution_plot` | 人数分布对比箱线图（横向） |
| `star_diff_actual_vs_rigidity_WFH_boxplot_distance.png` | `create_distribution_plot` | 距离分布对比箱线图（横向） |
| `star_diff_actual_vs_rigidity_WFH_distance_pdf.png` | `create_distance_pdf` | 通勤距离 PDF 对比图 |

---

## 记录要求

- 日志：`log/run_YYYYMMDD_HHMMSS.md`
- 技术记录：`docs/Technical_Record_4.3_scenario_computation.md`（UOT 推演方法、双系数参数化说明）
- 结果分析：`docs/Result_Analysis.md`（4.Scenario_Analysis 章节，含平均距离变化、KL 散度解读、空间分布特征）

---

## 验证清单

- [ ] `T_scenario_float.npy` 总量 ≈ `O_array.sum()`（误差 < 1）
- [ ] `star_rigidity_WFH_int.csv` 总人数 == `int(O_array.sum())`
- [ ] `scenario_computation_stats.csv` 包含 `rigidityO_multiplier` 和 `rigidityD_multiplier` 两列
- [ ] `star_rigidity_WFH_static_concise_stats.csv` 恰好 1 行
- [ ] `star_kl_actual_rigidity_WFH.csv` 包含 `kl_a_to_b`, `kl_b_to_a`, `jsd` 列
- [ ] `gdf_diff` 行数 == TAZ 数量（2427）
- [ ] 差值列无全 NaN
- [ ] 差值地图色带正负已通过步骤 5 打印输出确认
- [ ] 箱线图为横向排列（横轴为数值，纵轴为格局名）
- [ ] 所有地图包含指北针、比例尺、色标
