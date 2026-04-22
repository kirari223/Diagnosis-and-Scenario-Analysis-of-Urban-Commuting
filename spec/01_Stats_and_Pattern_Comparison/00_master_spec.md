# 总规范：格局对比实证统计与可视化

## 任务目标

对实际格局、理想格局（Theoretical）、基线格局（Baseline）、随机格局（Random）四个格局分别进行实证统计，并对四对差值（实际-理想、实际-基线、实际-随机、随机-理想）计算差值统计和KL散度，输出可直接用于论文的图表和统计结果。

## 输入文件

| 文件 | 说明 | 列结构 |
|---|---|---|
| `results/1.Data_Preprocess/实际格局-统一结构.csv` | 实际格局 | o, d, 人数, distance |
| `results/2.Pattern_Computation/2.1Theoretical_Pattern/理想格局-统一结构-0414.csv` | 理想格局 | o, d, 人数, distance |
| `results/2.Pattern_Computation/2.4Baseline_Int/star_baseline_int.csv` | 基线格局整数化结果 | o, d, 人数, distance |
| `results/2.Pattern_Computation/2.5Random_Int/star_random_int.csv` | 随机格局整数化结果 | o, d, 人数, distance |
| `data/TAZ4_shapefile4326.shp` | TAZ地理围栏 | taz, geometry |

## 整数化方法

基线格局和随机格局均使用 `prob_to_int`（v1 全局缩放）：截尾（threshold=0.5）→ 四舍五入 → 全局缩放微调。不使用 IPF 行列约束。

## 输出目录结构

```
results/
├── 2.Pattern_Computation/
│   ├── 2.4Baseline_Int/
│   │   └── star_baseline_int.csv              # 基线格局整数化结果（论文直引）
│   └── 2.5Random_Int/
│       └── star_random_int.csv                # 随机格局整数化结果（论文直引）
└── 3.1Basic_Stats/                            # 四个格局各自统计，扁平存放
│   ├── actual_static_all_stats.csv
│   ├── star_actual_static_concise_stats.csv
│   ├── actual_flow_all_stats.csv
│   ├── star_actual_flow_concise_stats.csv
│   ├── ideal_static_all_stats.csv
│   ├── star_ideal_static_concise_stats.csv
│   ├── ideal_flow_all_stats.csv
│   ├── star_ideal_flow_concise_stats.csv
│   ├── baseline_static_all_stats.csv
│   ├── star_baseline_static_concise_stats.csv
│   ├── baseline_flow_all_stats.csv
│   ├── star_baseline_flow_concise_stats.csv
│   ├── random_static_all_stats.csv
│   ├── star_random_static_concise_stats.csv
│   ├── random_flow_all_stats.csv
│   └── star_random_flow_concise_stats.csv
└── 3.4Pattern_Comparison/                     # 四对差值，扁平存放
    ├── star_diff_actual_vs_ideal.csv
    ├── star_diff_actual_vs_baseline.csv
    ├── star_diff_actual_vs_random.csv
    ├── star_diff_random_vs_ideal.csv
    ├── star_kl_actual_ideal.csv
    ├── star_kl_actual_baseline.csv
    ├── star_kl_actual_random.csv
    ├── star_kl_random_ideal.csv
    ├── diff_actual_ideal_flow_all_stats.csv
    ├── star_diff_actual_ideal_flow_concise_stats.csv
    ├── diff_actual_baseline_flow_all_stats.csv
    ├── star_diff_actual_baseline_flow_concise_stats.csv
    ├── diff_actual_random_flow_all_stats.csv
    ├── star_diff_actual_random_flow_concise_stats.csv
    ├── diff_random_ideal_flow_all_stats.csv
    └── star_diff_random_ideal_flow_concise_stats.csv
```

**注意**：3.1Basic_Stats 中不输出 `taz_indicators`，只输出 static_stats 和 flow_stats。

## 阶段划分

| 阶段 | 内容 | 对应分spec |
|---|---|---|
| 阶段1 | 整数化（prob_to_int v1 全局缩放） | `01_phase1_prob_to_int.md` |
| 阶段2 | 统计指标计算 | `01_phase2_statistics.md` |
| 阶段3 | 可视化 | `01_phase3_visualization.md` |

## 涉及修改的文件

| 文件 | 操作 |
|---|---|
| `src/data_prep.py` | `prob_to_int` 使用 v1 全局缩放，不使用 IPF |
| `src/metrics_eval.py` | `pattern_static_stats`、`pattern_flow_stats`、`compute_kl`、`compute_diff` |
| `src/visualization.py` | `create_choropleth_map`（OD端分布图）、`create_diverging_map`（差值图）、`create_flowline`（流线图）、`create_distance_pdf`（距离PDF）、`create_distribution_plot`（箱线图） |
| `notebooks/01_main_pipeline.py` | 2.4/2.5 调用 `prob_to_int`；3.1 四格局统计；3.4 四对差值 |
| `docs/Result_Analysis.md` | 累加结果解读 |
| `docs/Technical_Record.md` | 补充方法说明 |

## 全局约束

- 所有图：无经纬度网格（`ax.set_axis_off()`），有指北针、比例尺、图例/色标，字体 SimHei，标签 24pt，图例 24pt，注释 20pt，300 DPI，图面中不显示标题
- 所有 CSV：utf-8-sig 编码，数值保留 4 位小数
- 论文直引文件加 `star_` 前缀
- 颜色方案沿用 `config.COLOR_SCHEMES`
- 底图色 `#F5F5F5`，边线 `#CCCCCC`，外边界 `#333333`
- 虚拟环境：`C:\Users\Administrator\.conda\envs\job_housing`
