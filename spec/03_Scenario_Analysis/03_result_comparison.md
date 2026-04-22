# 步骤 4.4.1/4.4.2：结果对比（Result Comparison）

## 目标

计算情景格局本身的统计信息，并与实际格局进行差值统计和 KL 散度对比。

---

## 前置步骤：整数化（4.3.5）

在调用统计函数之前，必须先将 UOT 输出的浮点矩阵整数化。

```python
from src.data_prep import matrix_to_long_df, prob_to_int, distance_combine

target_total = int(O_array.sum())

# 浮点矩阵转长格式
df_scenario_float = matrix_to_long_df(
    T_scenario_float, value_name='人数', o_col='o', d_col='d'
)

# 整数化
df_scenario_int = prob_to_int(
    df_prob=df_scenario_float,
    target_total=target_total,
    output_dir=get_result_path(
        f'4.Scenario_Analysis/4.3Scenario_Computation/{scenario_label}', ''
    ),
)

# 附加距离列
df_scenario_int = distance_combine(df_scenario_int, distance_dict)

# 验证
assert df_scenario_int['人数'].sum() == target_total

df_scenario_int.to_csv(
    get_result_path(
        f'4.Scenario_Analysis/4.3Scenario_Computation/{scenario_label}',
        f'star_{scenario_label}_int.csv'
    ),
    index=False, encoding='utf-8-sig'
)
```

---

## 输入

| 变量 | 来源 | 说明 |
|---|---|---|
| `df_scenario` | `4.3Scenario_Computation/{scenario_label}/star_{scenario_label}_int.csv` | 情景整数 OD，列：o, d, 人数, distance |
| `df_actual` | `data/[主城区]TAZ4-od聚合.csv` 或统一结构文件 | 实际通勤 OD，列：o, d, 人数, distance |
| `fence` | `data/TAZ4_shapefile4326.shp` | TAZ 空间边界 |

**格式兼容说明**：`prob_to_int` 输出已包含 `[o, d, 人数]`，`distance_combine` 附加 `distance` 列后结构与实际格局一致，无需额外转换。若 `distance` 列缺失，调用 `distance_combine(df_scenario, distance_dict)` 补充。

---

## 步骤 4.4.1：情景格局统计

输出路径：`results/4.Scenario_Analysis/4.4Scenario_Compare/4.4.1Scenario_Pattern_Stats/`

调用与主流程 3.1 相同的函数：

```python
from src.metrics_eval import pattern_static_stats, pattern_flow_stats

dir_441 = get_result_path('4.Scenario_Analysis/4.4Scenario_Compare/4.4.1Scenario_Pattern_Stats', '')

# 静态统计（TAZ 级聚合）
pattern_static_stats(df_od=df_scenario, name=scenario_label, output_dir=dir_441)

# 动态统计（OD 流统计）
pattern_flow_stats(df_od=df_scenario, name=scenario_label, output_dir=dir_441)
```

输出文件：

| 文件 | 说明 |
|---|---|
| `{scenario_label}_static_all_stats.csv` | TAZ 级完整统计 |
| `star_{scenario_label}_static_concise_stats.csv` | 全局汇总（1 行） |
| `{scenario_label}_flow_all_stats.csv` | OD 流完整统计 |
| `star_{scenario_label}_flow_concise_stats.csv` | 流统计汇总（1 行） |

---

## 步骤 4.4.2：情景与实际格局对比

输出路径：`results/4.Scenario_Analysis/4.4Scenario_Compare/4.4.2Scenario_Actual_Compare/`

调用与主流程 3.4 相同的函数：

```python
from src.metrics_eval import compute_kl, compute_diff, compute_diff_statistics, compute_taz_indicators

dir_442 = get_result_path('4.Scenario_Analysis/4.4Scenario_Compare/4.4.2Scenario_Actual_Compare', '')

# KL 散度
compute_kl(
    df_a=df_actual, df_b=df_scenario,
    name_a='actual', name_b=scenario_label,
    output_dir=dir_442,
)

# TAZ 级指标（用于差值地图）
gdf_actual_taz = compute_taz_indicators(df_actual, fence)
gdf_scenario_taz = compute_taz_indicators(df_scenario, fence)

# TAZ 级差值
gdf_diff = compute_diff(
    gdf_a=gdf_actual_taz, gdf_b=gdf_scenario_taz,
    name_a='actual', name_b=scenario_label,
    fence=fence, output_dir=dir_442,
)

# 差值流统计
compute_diff_statistics(
    df_a=df_actual, df_b=df_scenario,
    name_a='actual', name_b=scenario_label,
    output_dir=dir_442,
)
```

输出文件：

| 文件 | 说明 |
|---|---|
| `star_kl_actual_{scenario_label}.csv` | KL 散度，含 kl_a_to_b, kl_b_to_a, jsd |
| `star_diff_actual_vs_{scenario_label}.csv` | TAZ 级差值 GeoDataFrame（CSV） |
| `diff_actual_{scenario_label}_flow_all_stats.csv` | 差值流完整统计 |
| `star_diff_actual_{scenario_label}_flow_concise_stats.csv` | 差值流汇总 |

---

## 结果解读说明

在输出统计结果后，应联系情景设定展开分析。情景一（刚性降低 20%）的城市规划背景是：居家办公普及、打卡约束放开后，系统自发调整——部分居民可能选择搬到更远但更宜居的地方，或接受更远的通勤以换取更优质的就业岗位。分析重点：

1. 情景格局的平均通勤距离是否增加？增幅是否在合理范围？
2. 哪些 TAZ 的通勤流入/流出变化最显著？是否呈现"近郊扩散"或"跨江通勤增加"的空间特征？
3. KL 散度反映的结构性偏离程度如何？

详见 `docs/Result_Analysis.md` 中"4.Scenario_Analysis"章节。

## 验证清单

- [ ] `star_{scenario_label}_int.csv` 总人数 == `int(O_array.sum())`（整数化后总量守恒）
- [ ] `prob_to_int_stats.csv` 存在于 `4.3Scenario_Computation/{scenario_label}/`
- [ ] `star_{scenario_label}_static_concise_stats.csv` 恰好 1 行
- [ ] `star_kl_actual_{scenario_label}.csv` 包含 `kl_a_to_b`, `kl_b_to_a`, `jsd` 列
- [ ] 情景总人数 == 实际总人数（O/D 边际不变，误差 < 1）
- [ ] `gdf_diff` 行数 == TAZ 数量（2427）
- [ ] 差值列无全 NaN
