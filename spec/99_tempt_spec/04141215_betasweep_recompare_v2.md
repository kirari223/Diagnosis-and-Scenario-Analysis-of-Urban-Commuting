# 格局重扫参与统计信息重输出 v2

**原始 spec**: 04141215_betasweep_recompare.md  
**版本日期**: 2026-04-14  
**任务目标**: 用 Wilson 最大熵模型重新输出基线格局和随机格局，对四个格局计算统计信息和差值统计，所有结果保存为 CSV 供论文引用。

---

## 前置确认

| 项目 | 值 |
|------|-----|
| 实际格局平均通勤距离（标定目标） | 5577.58 m |
| TAZ 编号范围 | 0 ~ 2426（共 2427 个） |
| 矩阵行列数 | 2427 × 2427 |
| Wilson 最大迭代次数 | 50 |
| 随机格局 beta | 0.0 |
| 整数化约束 | 仅保证总量一致（target_total），不做行列约束 |

---

## 输入文件

| 变量 | 路径 |
|------|------|
| 静态人口（O/D） | `data/[主城区]TAZ4-static.csv` |
| 距离矩阵（C） | `data/[主城区]TAZ4距离-完整版.csv` |
| 实际 OD（T） | `data/[主城区]TAZ4-od聚合.csv` |
| 空间边界 | `data/TAZ4_shapefile4326.shp` |
| 实际格局 OD | `results/1.Data_Preprocess/实际格局-统一结构.csv` |
| 理想格局 OD | `results/2.Pattern_Computation/2.1Theoretical_Pattern/理想格局-统一结构-0414.csv` |

---

## 动作一：Wilson 重扫参

### Step 1 — `## 1. Data_Preprocess`

**调用函数**: `df_to_matrix()`（`src/data_prep.py`）

```python
from src.data_prep import df_to_matrix

# O/D 列表
static_result = df_to_matrix(STATIC_CSV, data_type="static")
O_list = static_result['O_list']   # len == 2427
D_list = static_result['D_list']   # len == 2427

# C 矩阵（距离）
C_matrix = df_to_matrix(DISTANCE_CSV, data_type="matrix", matrix_type="C")  # (2427, 2427)

# T 矩阵（实际 OD）
T_observed = df_to_matrix(OD_CSV, data_type="matrix", matrix_type="T")      # (2427, 2427)
```

**验证（必须通过才继续）**:
```python
assert len(O_list) == 2427, f"O_list 长度错误: {len(O_list)}"
assert len(D_list) == 2427, f"D_list 长度错误: {len(D_list)}"
assert C_matrix.shape == (2427, 2427), f"C_matrix 形状错误: {C_matrix.shape}"
assert T_observed.shape == (2427, 2427), f"T_observed 形状错误: {T_observed.shape}"
```

**输出路径**: `get_result_path('1.Data_Preprocess', ...)`

---

### Step 2 — `## 2.2 Baseline_Pattern`（Wilson 标定 beta）

**调用函数**: `calibrate_beta()` + `compute_wilson()`（`src/models_pattern.py`）

```python
import numpy as np
from src.models_pattern import calibrate_beta, compute_wilson

O_array = np.array(O_list, dtype=float)
D_array = np.array(D_list, dtype=float)

# 两阶段扫参，目标距离 5577.58 m
calib = calibrate_beta(
    O=O_array, D=D_array, C=C_matrix,
    target_distance=5577.58,
    beta_range=(0.01, 1.0),
    coarse_step=0.01,
    fine_range=0.03,
    fine_step=0.001,
    max_iter=50,
)
best_beta = calib['best_beta']

# 用最优 beta 计算基线格局
baseline_result = compute_wilson(
    O=O_array, D=D_array, C=C_matrix,
    beta=best_beta,
    max_iter=50,
    return_details=True
)
T_baseline = baseline_result['T_model']   # float, shape (2427, 2427)
```

**验证**:
```python
assert abs(baseline_result['avg_dist'] - 5577.58) / 5577.58 < 0.01, \
    f"标定误差过大: {baseline_result['avg_dist']:.2f} m"
```

**输出**:
- `get_result_path('2.Pattern_Computation/2.2Baseline_Pattern', 'T_baseline_float.npy')` — 浮点矩阵
- `get_result_path('2.Pattern_Computation/2.2Baseline_Pattern', 'calibration_sweep.csv')` — sweep_data（calib['sweep_data']）
- `get_result_path('2.Pattern_Computation/2.2Baseline_Pattern', 'calibration_summary.csv')` — best_beta、model_distance、error

---

### Step 3 — `## 2.3 Random_Pattern`（β=0）

**调用函数**: `compute_wilson()`（`src/models_pattern.py`）

```python
random_result = compute_wilson(
    O=O_array, D=D_array, C=C_matrix,
    beta=0.0,
    max_iter=50,
    return_details=True
)
T_random = random_result['T_model']   # float, shape (2427, 2427)
```

**输出**:
- `get_result_path('2.Pattern_Computation/2.3Random_Pattern', 'T_random_float.npy')`
- `get_result_path('2.Pattern_Computation/2.3Random_Pattern', 'random_summary.csv')` — avg_dist、total_flow、iterations

---

## 动作二：整数化与统计输出

### Step 4 — `## 2.4 Prob_to_Int — Baseline Pattern Integerization`

**调用函数**: `matrix_to_long_df()` + `prob_to_int()`（`src/data_prep.py`）

```python
from src.data_prep import matrix_to_long_df, prob_to_int, distance_combine

target_total = int(O_array.sum())

df_baseline_float = matrix_to_long_df(T_baseline, value_col='人数', o_col='o', d_col='d')
df_baseline_int = prob_to_int(
    df_prob=df_baseline_float,
    target_total=target_total,
    output_dir=get_result_path('2.Pattern_Computation/2.4Baseline_Int', '')
)

# 补全 distance 列（从 C_matrix）
distance_dict = {(i, j): C_matrix[i, j]
                 for i in range(C_matrix.shape[0])
                 for j in range(C_matrix.shape[1])
                 if C_matrix[i, j] > 0}
df_baseline_int = distance_combine(df_baseline_int, distance_dict)
```

**验证**:
```python
assert df_baseline_int['人数'].sum() == target_total
```

**输出**: `get_result_path('2.Pattern_Computation/2.4Baseline_Int', 'star_baseline_int.csv')`

---

### Step 5 — `## 2.5 Prob_to_Int — Random Pattern Integerization`

同 Step 4，对 `T_random` 执行整数化，补全 distance。

**输出**: `get_result_path('2.Pattern_Computation/2.5Random_Int', 'star_random_int.csv')`

---

### Step 6 — `## 3.1 Basic_Stats — Pattern Statistics`

对四个格局分别计算 TAZ 级别指标和统计信息。

**调用函数**: `compute_taz_indicators()` + `compute_statistics()`（`src/metrics_eval.py`）

**注意**：读入实际格局和理想格局时，需将列名统一为 `o, d, 人数, distance`：

| 格局 | 输入文件 | 列名映射 |
|------|---------|---------|
| 实际格局 | `results/1.Data_Preprocess/实际格局-统一结构.csv` | 确认列名，按需 rename |
| 理想格局 | `results/2.Pattern_Computation/2.1Theoretical_Pattern/理想格局-统一结构-0414.csv` | 确认列名，按需 rename |
| 基线整数化 | Step 4 输出 | 已统一 |
| 随机整数化 | Step 5 输出 | 已统一 |

```python
from src.metrics_eval import compute_taz_indicators, compute_statistics

patterns = {
    'actual':    df_actual,
    'ideal':     df_ideal,
    'baseline':  df_baseline_int,
    'random':    df_random_int,
}

gdfs = {}
for name, df in patterns.items():
    gdf = compute_taz_indicators(df_od=df, fence=fence,
                                 o_col='o', d_col='d',
                                 value_col='人数', distance_col='distance')
    stats = compute_statistics(gdf, name=name, save=True)
    gdf.to_csv(get_result_path('3.1Basic_Stats', f'star_stats_{name}.csv'),
               index=False, encoding='utf-8-sig')
    gdfs[name] = gdf
```

**输出路径**: `results/3.1Basic_Stats/star_stats_{name}.csv`（四个文件）

---

### Step 7 — `## 3.4 Pattern_Comparison — Diff Statistics`

对四对差值计算差值统计和 KL 散度。

**调用函数**: `compute_diff()` + `compute_diff_statistics()` + `compute_kl()`（`src/metrics_eval.py`）

| 对比 | A | B |
|------|---|---|
| 实际 - 理想 | actual | ideal |
| 实际 - 基线 | actual | baseline |
| 基线 - 理想 | baseline | ideal |
| 实际 - 随机 | actual | random |

```python
from src.metrics_eval import compute_diff, compute_diff_statistics, compute_kl

pairs = [
    ('actual', 'ideal'),
    ('actual', 'baseline'),
    ('baseline', 'ideal'),
    ('actual', 'random'),
]

for name_a, name_b in pairs:
    gdf_diff = compute_diff(gdfs[name_a], gdfs[name_b],
                            name_a=name_a, name_b=name_b, fence=fence,
                            output_dir=get_result_path('3.4Pattern_Comparison', ''))
    diff_stats = compute_diff_statistics(gdf_diff, name_a=name_a, name_b=name_b, save=True)
    gdf_diff.to_csv(
        get_result_path('3.4Pattern_Comparison', f'star_diff_{name_a}_vs_{name_b}.csv'),
        index=False, encoding='utf-8-sig'
    )

    # KL 散度
    kl_result = compute_kl(
        df_a=patterns[name_a], df_b=patterns[name_b],
        name_a=name_a, name_b=name_b,
        output_dir=get_result_path('3.4Pattern_Comparison', '')
    )
```

**输出路径**: `results/3.4Pattern_Comparison/star_diff_{nameA}_vs_{nameB}.csv`（四个文件）+ KL 散度 CSV

---

## 日志与文档规范

每次执行后，按以下格式记录：

### log/run_YYYYMMDD_HHMMSS.md

```markdown
# Run Log — YYYY-MM-DD HH:MM:SS

## 输入
- STATIC_CSV: ...
- DISTANCE_CSV: ...
- OD_CSV: ...

## 执行步骤
1. Data_Preprocess — O/D/C/T 矩阵转换
2. Baseline_Pattern — calibrate_beta, best_beta=X.XXX, avg_dist=XXXX.XX m
3. Random_Pattern — beta=0, avg_dist=XXXX.XX m
4. Prob_to_Int Baseline — total=XXXXXXX
5. Prob_to_Int Random — total=XXXXXXX
6. Basic_Stats — 四个格局统计
7. Pattern_Comparison — 四对差值统计 + KL 散度

## 输出文件
- results/2.Pattern_Computation/2.2Baseline_Pattern/T_baseline_float.npy
- results/2.Pattern_Computation/2.2Baseline_Pattern/calibration_sweep.csv
- results/2.Pattern_Computation/2.3Random_Pattern/T_random_float.npy
- results/2.Pattern_Computation/2.4Baseline_Int/star_baseline_int.csv
- results/2.Pattern_Computation/2.5Random_Int/star_random_int.csv
- results/3.1Basic_Stats/star_stats_{actual|ideal|baseline|random}.csv
- results/3.4Pattern_Comparison/star_diff_{pair}.csv（四个）
```

### docs/Result_Analysis.md（累加更新，时间戳与日志一致）

按 pipeline 小标题追加，用人文地理/城市规划专业表达，可直接引用到论文。

### docs/Technical_Record.md（累加更新，时间戳与日志一致）

含 LaTeX 公式，对应论文方法章节。

---

## 关键风险点

1. **列名不统一**：实际格局和理想格局的列名需在 Step 6 之前统一为 `o, d, 人数, distance`
2. **distance 列缺失**：整数化后的 OD 无 distance，需用 `distance_combine()` 从 C_matrix 补全
3. **beta=0 收敛性**：`compute_wilson` 已支持 beta=0，直接传入即可

---

## 验证清单

- [ ] `len(O_list) == 2427`，`C_matrix.shape == (2427, 2427)`
- [ ] `baseline_result['avg_dist']` 与 5577.58 误差 < 1%
- [ ] `df_baseline_int['人数'].sum() == target_total`
- [ ] `df_random_int['人数'].sum() == target_total`
- [ ] `results/3.1Basic_Stats/` 下存在四个 star_stats_*.csv
- [ ] `results/3.4Pattern_Comparison/` 下存在四个 star_diff_*.csv 及 KL 散度文件
- [ ] 日志时间戳与 Result_Analysis.md、Technical_Record.md 一致
