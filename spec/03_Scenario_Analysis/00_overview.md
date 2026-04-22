# 情景分析阶段总览（Phase 4: Scenario Analysis）

## 任务目标

从实际通勤格局中提取 O/D 两侧刚性参数，在刚性发生变化的情景假设下，通过凸优化推演出新的 OD 格局，并与实际格局进行统计对比和可视化。

---

## 输入文件

| 文件 | 描述 | 关键列 |
|---|---|---|
| `data/[主城区]TAZ4-static.csv` | 静态 O/D 边际 | taz, 居住人口, 工作人口 |
| `data/[主城区]TAZ4距离-完整版.csv` | TAZ 间距离矩阵 | o, d, distance |
| `data/[主城区]TAZ4-od聚合.csv` | 实际通勤 OD | o, d, 人数 |
| `results/1.Data_Preprocess/` | 预处理后的矩阵 | O_array, D_array, C_matrix, T_observed |
| `results/2.Pattern_Computation/2.2Baseline_Pattern/` | Wilson 标定结果 | best_beta |

---

## 输出目录树

```
results/4.Scenario_Analysis/
  4.1Extract_Ratio/                        # 刚性提取中间结果
  4.2Rigidity_Computation/                 # 刚性计算结果
    star_rigidity_params.csv               # alpha_O, alpha_D, theta_O, theta_D
    estimate_rigidity_poisson_stats.csv
  4.3Scenario_Computation/                 # 情景推演结果
    {scenario_label}/                      # 每个情景一个子文件夹
      T_scenario_float.npy
      star_{scenario_label}_int.csv
      scenario_computation_stats.csv
  4.4Scenario_Compare/
    4.4.1Scenario_Pattern_Stats/           # 情景格局统计
    4.4.2Scenario_Actual_Compare/          # 情景与实际对比
    4.4.3Scenario_Compare_Visualize/       # 可视化输出
```

---

## 阶段索引

| 子 spec | 覆盖步骤 | 关键函数 |
|---|---|---|
| [01_rigidity_extraction.md](01_rigidity_extraction.md) | 4.1 + 4.2：泊松回归提取刚性 | `estimate_rigidity_poisson` |
| [02_scenario_computation.md](02_scenario_computation.md) | 4.3：UOT 情景推演 | `compute_scenario_uot` |
| [03_result_comparison.md](03_result_comparison.md) | 4.4.1 + 4.4.2：统计对比 | `pattern_static_stats`, `compute_kl`, `compute_diff` |
| [04_visualization.md](04_visualization.md) | 4.4.3：地图/流线/箱线图 | `create_choropleth_map`, `create_flowline`, `create_distribution_plot` |
| [05_scenario_one_rigidity_minus20.md](05_scenario_one_rigidity_minus20.md) | 情景一：居家办公趋势提升 | `rigidity_multiplier=0.8` |

---

## 全局约束

- 输出文件编码：utf-8-sig
- 论文直引文件加 `star_` 前缀
- 可视化规范：300 DPI，指北针、比例尺、色标必须包含
- **情景参数化**：所有函数接受 `scenario_label: str` 参数（如 `'rigidity_plus20'`），不硬编码具体情景值，支持多情景并存
- `scenario_label` 命名规则：`{parameter}_{direction}{magnitude}`，示例：`rigidity_plus20`、`rigidity_plus50`
- 所有 src/ 函数为通用工具模块，不在注释中使用步骤限定性描述

---

## 修改文件清单

| 文件 | 修改类型 | 说明 |
|---|---|---|
| `src/elasticity.py` | 新增函数 | `estimate_rigidity_poisson`, `solve_uot_scenario`, `compute_scenario_uot` |
| `src/visualization.py` | 新增函数 | `create_flowline`, `create_distribution_plot` |
| `src/visualization.py` | 修正签名 | `create_diverging_map` 的 `config_key` 改为可选 |
| `notebooks/01_main_pipeline.ipynb` | 新增 section | 4.2 ~ 4.4 对应 cells |
