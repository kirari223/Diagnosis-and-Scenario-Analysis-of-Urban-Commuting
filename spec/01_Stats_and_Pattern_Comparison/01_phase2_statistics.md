# 阶段2：统计指标计算

## 目标

对四个格局（实际、理想、基线整数化、随机整数化）分别计算静态OD端统计和动态T统计，并对四对差值（实际-理想、实际-基线、实际-随机、随机-理想）计算差值统计和KL散度。所有统计结果保存为CSV，供论文引用和阶段3可视化使用。

**不输出 taz_indicators**（`compute_taz_indicators` 仅在内存中调用供差值计算使用）。

---

## 输入

| 变量名 | 来源文件 |
|---|---|
| `df_actual` | `results/1.Data_Preprocess/实际格局-统一结构.csv` |
| `df_ideal` | `results/2.Pattern_Computation/2.1Theoretical_Pattern/理想格局-统一结构-0414.csv` |
| `df_baseline` | `results/2.Pattern_Computation/2.4Baseline_Int/star_baseline_int.csv` |
| `df_random` | `results/2.Pattern_Computation/2.5Random_Int/star_random_int.csv` |

---

## 函数清单

| 函数 | 位置 | 说明 |
|---|---|---|
| `pattern_static_stats` | `src/metrics_eval.py` | 单格局静态OD端统计 |
| `pattern_flow_stats` | `src/metrics_eval.py` | 单格局动态T通勤流统计 |
| `compute_kl` | `src/metrics_eval.py` | 两格局KL散度 |
| `compute_diff` | `src/metrics_eval.py` | TAZ级差值（供可视化使用） |

---

## 3.1 Basic_Stats — 四个格局各自统计

对 `actual`、`ideal`、`baseline`、`random` 四个格局分别调用：

```python
pattern_static_stats(df_od=df, name=name, output_dir=out_dir_31, ...)
pattern_flow_stats(df_od=df, name=name, output_dir=out_dir_31, ...)
```

输出到 `results/3.1Basic_Stats/`，文件命名规则：
- `{name}_static_all_stats.csv`（详细版）
- `star_{name}_static_concise_stats.csv`（简明版，论文直引）
- `{name}_flow_all_stats.csv`（详细版）
- `star_{name}_flow_concise_stats.csv`（简明版，论文直引）

---

## 3.4 Pattern_Comparison — 四对差值统计

四对差值：

| 对比 | name_a | name_b |
|------|--------|--------|
| 实际 - 理想 | actual | ideal |
| 实际 - 基线 | actual | baseline |
| 实际 - 随机 | actual | random |
| 随机 - 理想 | random | ideal |

对每对调用：

```python
# KL 散度
kl = compute_kl(df_a=patterns[name_a], df_b=patterns[name_b],
                name_a=name_a, name_b=name_b,
                value_col='人数', o_col='o', d_col='d',
                output_dir=out_dir_34)

# OD 流差值统计
df_merged = patterns[name_a].merge(
    patterns[name_b][['o','d','人数']].rename(columns={'人数':'人数_b'}),
    on=['o','d'], how='outer').fillna(0)
df_merged['差值'] = df_merged['人数'] - df_merged['人数_b']
pattern_flow_stats(df_od=df_merged, name=f'diff_{name_a}_{name_b}',
                   output_dir=out_dir_34,
                   value_col='差值', distance_col='distance', is_diff=True)

# TAZ 级差值（供可视化使用，不保存 taz_indicators）
gdf_diff = compute_diff(gdfs[name_a], gdfs[name_b],
                        name_a=name_a, name_b=name_b,
                        fence=fence, output_dir=out_dir_34)
gdf_diff.drop(columns='geometry').to_csv(
    out_dir_34 / f'star_diff_{name_a}_vs_{name_b}.csv',
    index=False, encoding='utf-8-sig')
```

---

## `pattern_static_stats` 函数规范

**签名**：
```python
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
```

**O侧聚合**（按起点分组）：总流出量、平均流出量、OD对数、流出量标准差、变异系数、平均距离、距离标准差。

**D侧聚合**（按终点分组）：同O侧，列名改为"流入量"。

**详细版**（`{name}_static_all_stats.csv`）：O/D侧 describe() + 变异系数 + 流出量最大前10 TAZ + 平均距离最短/最长前10 TAZ。

**简明版**（`star_{name}_static_concise_stats.csv`）：一行汇总，含起终点TAZ数、O/D侧总量均值/中位数/标准差/CV、O/D侧平均距离均值/中位数。

---

## `pattern_flow_stats` 函数规范

**签名**：
```python
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
```

**详细版**（`{name}_flow_all_stats.csv`）：总OD对数、总通勤人数、全局加权平均距离、距离中位数/标准差、人数CV、人数Q25/Q50/Q75、距离Q25/Q50/Q75。差值模式额外输出按距离分段（0-5km, 5-10km, 10-20km, 20-50km, >50km）的差值统计。

**简明版**（`star_{name}_flow_concise_stats.csv`）：总流量、OD对数、平均流量、加权平均距离。

---

## `compute_kl` 函数规范

```python
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
```

返回 `kl_a_to_b`、`kl_b_to_a`、`jsd`，保存到 `star_kl_{name_a}_{name_b}.csv`。
