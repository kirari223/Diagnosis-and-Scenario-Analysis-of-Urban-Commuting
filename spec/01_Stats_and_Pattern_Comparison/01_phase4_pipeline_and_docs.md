# 阶段4：Pipeline集成 + 文档输出

## 目标

将阶段1-3的所有函数整合到 `notebooks/01_main_pipeline.ipynb` 的对应章节中，确保从头到尾能完整跑通，并输出运行日志、结果解读文档（Result_Analysis.md）和方法说明文档（Technical_Record.md）。

---

## 操作一：更新 `src/__init__.py` 导出

在 `src/__init__.py` 中补充新增函数的导出（顶层只导出 config + utils，其余按模块导入，所以只需确认新函数在各模块中可被 `from src.xxx import yyy` 调用，无需修改 `__init__.py`）。

**需要确认可导入的新函数**：
- `from src.data_prep import prob_to_int`（签名已修改）
- `from src.metrics_eval import pattern_statistics, compute_kl`（新增）
- `from src.visualization import create_flowline, create_distance_pdf, create_distribution_plot`（新增）
- `from src.utils import write_run_log`（新增）

---

## 操作二：更新 `notebooks/01_main_pipeline.ipynb` 章节结构

### 现有章节（保留）

- `Environment_Setting_and_Import`（步骤1）
- `Data_Preparation`（步骤2，matrix_to_df）
- `Load_Fence`（步骤3）
- `Baseline_Pattern_Wilson`（步骤4）

### 新增/修改章节

在 notebook 中按以下顺序新增章节，每个章节对应一个 markdown 小标题（英文）：

---

#### 章节：`2.3_Prob_to_Int — Baseline Pattern Integerization`

```python
# %% [markdown]
# ## 2.3_Prob_to_Int — Baseline Pattern Integerization

# %%
from src.data_prep import prob_to_int

df_baseline_float = pd.read_csv(
    RESULTS_DIR / '2.Pattern_Computation/2.2Baseline_Pattern/基线格局-od-距离已补全.csv',
    encoding='utf-8-sig'
)
print(f"基线格局原始: {len(df_baseline_float):,} 行, 总人数: {df_baseline_float['人数'].sum():.0f}")

target_total = int(df_baseline_float['人数'].sum())

df_baseline_int = prob_to_int(
    df_prob=df_baseline_float,
    target_total=target_total,
    threshold=0.5,
)

# 重新关联距离（整数化后需从原始数据关联）
df_baseline_int = df_baseline_int.merge(
    df_baseline_float[['o', 'd', 'distance']].drop_duplicates(['o', 'd']),
    on=['o', 'd'], how='left'
)

print(f"整数化后: {len(df_baseline_int):,} 行, 总人数: {df_baseline_int['人数'].sum():,}")

# 保存
out_path = get_result_path('2.Pattern_Computation/2.3_Prob_to_Int', 'star_baseline_integer.csv')
df_baseline_int.to_csv(out_path, index=False, encoding='utf-8-sig')
print(f"已保存: {out_path}")
```

---

#### 章节：`3.1_Basic_Stats — Pattern Statistics and Visualization`

```python
# %% [markdown]
# ## 3.1_Basic_Stats — Pattern Statistics and Visualization

# %%
from src.metrics_eval import pattern_statistics
from src.visualization import create_choropleth_map, create_flowline, create_distance_pdf

# 读取三个格局
df_actual = pd.read_csv(
    RESULTS_DIR / '1.Data_Preprocess/实际格局-统一结构.csv', encoding='utf-8-sig'
)
df_ideal = pd.read_csv(
    RESULTS_DIR / '2.Pattern_Computation/2.1Theoretical_Pattern/理想格局-统一结构.csv',
    encoding='utf-8-sig'
)
df_baseline = pd.read_csv(
    RESULTS_DIR / '2.Pattern_Computation/2.3_Prob_to_Int/star_baseline_integer.csv',
    encoding='utf-8-sig'
)

patterns = {
    '实际': df_actual,
    '理想': df_ideal,
    '基线': df_baseline,
}

gdf_dict = {}

for name, df in patterns.items():
    print(f"\n{'='*50}")
    print(f"处理格局: {name}")
    output_dir = get_result_path(f'3.Situation_Diagnosis/3.1_Basic_Stats/{name}格局', '').parent
    
    result = pattern_statistics(df, name, output_dir)
    gdf_dict[name] = result['gdf_taz']
    
    # 静态设色图（3张）
    for col, config_key, fname in [
        ('总通勤人数', 'total_people', f'star_{name}_map_total_people.png'),
        ('平均通勤距离', 'avg_distance', f'star_{name}_map_avg_distance.png'),
        ('内部通勤比', 'internal_ratio', f'star_{name}_map_internal_ratio.png'),
    ]:
        create_choropleth_map(
            gdf_data=gdf_dict[name],
            gdf_base=fence,
            column=col,
            config_key=config_key,
            output_path=get_result_path(f'3.Situation_Diagnosis/3.1_Basic_Stats/{name}格局', fname),
            title=f'{name}格局 - {col}',
        )
    
    # 动态流线图
    top_n = 200 if name == '理想' else 500
    create_flowline(
        df_od=df,
        fence=fence,
        output_path=get_result_path(f'3.Situation_Diagnosis/3.1_Basic_Stats/{name}格局',
                                     f'star_{name}_flowline.png'),
        title=f'{name}格局 OD流线图（前{top_n}条）',
        top_n=top_n,
    )

# 三格局距离PDF对比图（合并在一张）
create_distance_pdf(
    df_list=[df_actual, df_ideal, df_baseline],
    names=['实际格局', '理想格局', '基线格局'],
    output_path=get_result_path('3.Situation_Diagnosis/3.1_Basic_Stats', 'star_all_distance_pdf.png'),
    title='三格局通勤距离分布对比',
)
```

---

#### 章节：`3.4_Pattern_Comparison — Diff Analysis and Visualization`

```python
# %% [markdown]
# ## 3.4_Pattern_Comparison — Diff Analysis and Visualization

# %%
from src.metrics_eval import compute_diff, compute_diff_statistics, compute_kl
from src.visualization import create_diverging_map, create_flowline, create_distribution_plot

diff_pairs = [
    ('实际', '理想'),
    ('实际', '基线'),
    ('基线', '理想'),
]

for name_a, name_b in diff_pairs:
    print(f"\n{'='*50}")
    print(f"差值分析: {name_a} - {name_b}")
    
    section = f'3.Situation_Diagnosis/3.4_Pattern_Comparison/{name_a}-{name_b}'
    output_dir = get_result_path(section, '').parent
    
    df_a = patterns[name_a]
    df_b = patterns[name_b]
    gdf_a = gdf_dict[name_a]
    gdf_b = gdf_dict[name_b]
    
    # 差值GeoDataFrame
    gdf_diff = compute_diff(gdf_a, gdf_b, name_a, name_b, fence, output_dir=output_dir)
    
    # 差值统计
    compute_diff_statistics(gdf_diff, name_a, name_b, output_dir=output_dir)
    
    # KL散度
    compute_kl(df_a, df_b, name_a, name_b, output_dir=output_dir)
    
    # 差值设色图（3张）
    for col_base, config_key, fname_suffix in [
        ('总通勤人数', 'diff_people', 'map_people'),
        ('平均通勤距离', 'diff_distance', 'map_distance'),
        ('内部通勤比', 'diff_ratio', 'map_ratio'),
    ]:
        create_diverging_map(
            gdf_data=gdf_diff,
            gdf_base=fence,
            column=f'{col_base}_diff',
            config_key=config_key,
            output_path=get_result_path(section, f'star_diff_{name_a}_{name_b}_{fname_suffix}.png'),
            title=f'{name_a} - {name_b}: {col_base}差值',
        )
    
    # 差值流线图
    # 需要先计算OD级别差值（不是TAZ级别）
    df_diff_od = pd.merge(
        df_a[['o', 'd', '人数']].rename(columns={'人数': f'人数_{name_a}'}),
        df_b[['o', 'd', '人数']].rename(columns={'人数': f'人数_{name_b}'}),
        on=['o', 'd'], how='outer'
    ).fillna(0)
    df_diff_od['差值'] = df_diff_od[f'人数_{name_a}'] - df_diff_od[f'人数_{name_b}']
    
    create_flowline(
        df_od=df_diff_od,
        fence=fence,
        output_path=get_result_path(section, f'star_diff_{name_a}_{name_b}_flowline.png'),
        title=f'{name_a} - {name_b} 差值流线图（前500条）',
        flow_col='差值',
        top_n=500,
        is_diff=True,
    )
    
    # 箱线对比图
    create_distribution_plot(
        df_a=df_a,
        df_b=df_b,
        name_a=name_a,
        name_b=name_b,
        output_path=get_result_path(section, f'star_diff_{name_a}_{name_b}_boxplot.png'),
    )
```

---

## 操作三：输出运行日志

每个章节执行完后调用 `write_run_log`：

```python
from src.utils import write_run_log

write_run_log(
    step_name='3.1_Basic_Stats — Pattern Statistics and Visualization',
    inputs={
        '实际格局': str(RESULTS_DIR / '1.Data_Preprocess/实际格局-统一结构.csv'),
        '理想格局': str(RESULTS_DIR / '2.Pattern_Computation/2.1Theoretical_Pattern/理想格局-统一结构.csv'),
        '基线格局': str(RESULTS_DIR / '2.Pattern_Computation/2.3_Prob_to_Int/star_baseline_integer.csv'),
    },
    outputs={
        '统计CSV': '3.Situation_Diagnosis/3.1_Basic_Stats/{格局名}/',
        '地图PNG': '3.Situation_Diagnosis/3.1_Basic_Stats/{格局名}/',
        '流线图': '3.Situation_Diagnosis/3.1_Basic_Stats/{格局名}/',
        'PDF图': '3.Situation_Diagnosis/3.1_Basic_Stats/star_all_distance_pdf.png',
    },
    notes='三格局各出3张设色图+1张流线图，合并出1张距离PDF对比图',
)
```

---

## 操作四：更新 `docs/Result_Analysis.md`

在 `docs/Result_Analysis.md` 中按 pipeline 章节标题累加以下内容（每次执行后追加，不覆盖已有内容）：

### 追加格式

```markdown
## 2.3_Prob_to_Int — 基线格局整数化

**执行时间**：{YYYY-MM-DD}

**结果摘要**：
- 原始基线格局 OD 对数：5,800,740，总人数：2,212,508
- 截尾阈值 0.5 后保留 OD 对数：约 XXX，保留率：XX%
- 整数化后总人数：2,212,508（与目标一致）

**解读**：
基线格局由 Wilson 双约束模型生成，人数为连续浮点数。整数化采用截尾+四舍五入方法，
截尾阈值 0.5 去除了极小流量 OD 对（通勤人数不足半人的 OD 对在实际中无意义），
保留了主要通勤流，整数化后总人数与模型输出一致。

---

## 3.1_Basic_Stats — 三格局实证统计

**执行时间**：{YYYY-MM-DD}

### 全局统计对比

| 指标 | 实际格局 | 理想格局 | 基线格局 |
|---|---|---|---|
| 总通勤人数 | XX | XX | XX |
| 加权平均通勤距离(m) | XX | XX | XX |
| 内部通勤比(%) | XX | XX | XX |
| 变异系数(人数) | XX | XX | XX |

**解读**：
（根据实际数值填写，用人文地理/城市规划专业表达）
...

---

## 3.4_Pattern_Comparison — 格局差值分析

**执行时间**：{YYYY-MM-DD}

### KL散度汇总

| 格局对 | KL(A||B) | KL(B||A) | JS散度 |
|---|---|---|---|
| 实际-理想 | XX | XX | XX |
| 实际-基线 | XX | XX | XX |
| 基线-理想 | XX | XX | XX |

**解读**：
...
```

**注意**：Result_Analysis.md 的具体数值在执行后填写，此处只定义格式模板。

---

## 操作五：更新 `docs/Technical_Record.md`

在 `docs/Technical_Record.md` 中补充以下内容（追加到文件末尾）：

### 追加内容

```markdown
## 2.3 基线格局整数化

### 方法说明

Wilson 双约束模型输出的通勤矩阵 $T_{ij}$ 为连续浮点数，需转换为整数以便与实际格局进行对比分析。

**步骤一：截尾**

设截尾阈值 $\theta = 0.5$，过滤极小流量 OD 对：

$$\tilde{T}_{ij} = T_{ij} \cdot \mathbf{1}[T_{ij} \geq \theta]$$

**步骤二：四舍五入**

$$\hat{T}_{ij} = \text{round}(\tilde{T}_{ij})$$

**步骤三：全局缩放微调**

设目标总人数 $N = \sum_{ij} T_{ij}$，缩放系数：

$$\lambda = \frac{N}{\sum_{ij} \hat{T}_{ij}}$$

$$\hat{T}_{ij}^* = \text{round}(\lambda \cdot \hat{T}_{ij})$$

对剩余差值 $\delta = N - \sum_{ij} \hat{T}_{ij}^*$，按人数从大到小对前 $|\delta|$ 个 OD 对加减 1，使总和严格等于 $N$。

---

## 3.1 格局实证统计

### 静态 OD 端统计

对格局 $T$ 的 O 侧（起点）统计，设 $O_i = \sum_j T_{ij}$：

- 变异系数：$CV = \sigma_{O} / \bar{O}$
- 加权平均通勤距离：$\bar{d} = \frac{\sum_{ij} T_{ij} \cdot d_{ij}}{\sum_{ij} T_{ij}}$

### TAZ 级指标

对每个 TAZ $i$，计算：

$$\text{总通勤人数}_i = \sum_j T_{ij}$$

$$\text{平均通勤距离}_i = \frac{\sum_j T_{ij} \cdot d_{ij}}{\sum_j T_{ij}}$$

$$\text{内部通勤比}_i = \frac{T_{ii}}{\sum_j T_{ij}} \times 100\%$$

---

## 3.4 格局差值分析

### TAZ 级差值

对两个格局 $A$、$B$，TAZ $i$ 的差值指标：

$$\Delta \text{总通勤人数}_i = O_i^A - O_i^B$$

$$\Delta \text{平均通勤距离}_i = \bar{d}_i^A - \bar{d}_i^B$$

$$\Delta \text{内部通勤比}_i = r_i^A - r_i^B$$

### KL 散度

将两个格局的 OD 流量归一化为概率分布：

$$P_{ij} = \frac{T_{ij}^A}{\sum_{ij} T_{ij}^A}, \quad Q_{ij} = \frac{T_{ij}^B}{\sum_{ij} T_{ij}^B}$$

对两个格局 OD 对集合取并集，缺失值填充极小值 $\varepsilon = 10^{-10}$。

KL 散度（非对称）：

$$D_{KL}(P \| Q) = \sum_{ij} P_{ij} \ln \frac{P_{ij}}{Q_{ij}}$$

Jensen-Shannon 散度（对称，有界 $[0, \ln 2]$）：

$$M_{ij} = \frac{P_{ij} + Q_{ij}}{2}$$

$$JSD(P \| Q) = \frac{1}{2} D_{KL}(P \| M) + \frac{1}{2} D_{KL}(Q \| M)$$

$JSD$ 值越小，两格局越相似；$JSD = 0$ 表示完全相同。

**注**：由于三个格局的 OD 对集合规模差异较大（理想格局约 4,809 对，实际格局约 513,313 对，基线格局约 XXX 对），KL 散度受 OD 对集合大小影响，比较时需结合 OD 对数量说明。
```

---

## 完整输出文件清单

### 阶段1输出

| 路径 | 说明 |
|---|---|
| `results/2.Pattern_Computation/2.3_Prob_to_Int/star_baseline_integer.csv` | 整数化基线格局 |
| `results/2.Pattern_Computation/2.3_Prob_to_Int/prob_to_int_stats.csv` | 整数化统计 |

### 阶段2输出（每格局）

| 路径模板 | 说明 |
|---|---|
| `results/3.Situation_Diagnosis/3.1_Basic_Stats/{name}格局/star_{name}_global_stats.csv` | 全局统计 |
| `results/3.Situation_Diagnosis/3.1_Basic_Stats/{name}格局/{name}_o_side_stats.csv` | O侧统计 |
| `results/3.Situation_Diagnosis/3.1_Basic_Stats/{name}格局/{name}_d_side_stats.csv` | D侧统计 |
| `results/3.Situation_Diagnosis/3.1_Basic_Stats/{name}格局/{name}_taz_indicators.csv` | TAZ指标 |

### 阶段2输出（每差值对）

| 路径模板 | 说明 |
|---|---|
| `results/3.Situation_Diagnosis/3.4_Pattern_Comparison/{A}-{B}/star_diff_{A}_{B}_stats.csv` | 差值统计 |
| `results/3.Situation_Diagnosis/3.4_Pattern_Comparison/{A}-{B}/star_kl_{A}_{B}.csv` | KL散度 |

### 阶段3输出（每格局）

| 路径模板 | 说明 |
|---|---|
| `results/3.Situation_Diagnosis/3.1_Basic_Stats/{name}格局/star_{name}_map_total_people.png` | 总通勤人数地图 |
| `results/3.Situation_Diagnosis/3.1_Basic_Stats/{name}格局/star_{name}_map_avg_distance.png` | 平均通勤距离地图 |
| `results/3.Situation_Diagnosis/3.1_Basic_Stats/{name}格局/star_{name}_map_internal_ratio.png` | 内部通勤比地图 |
| `results/3.Situation_Diagnosis/3.1_Basic_Stats/{name}格局/star_{name}_flowline.png` | OD流线图 |
| `results/3.Situation_Diagnosis/3.1_Basic_Stats/star_all_distance_pdf.png` | 三格局距离PDF对比 |

### 阶段3输出（每差值对）

| 路径模板 | 说明 |
|---|---|
| `results/3.Situation_Diagnosis/3.4_Pattern_Comparison/{A}-{B}/star_diff_{A}_{B}_map_people.png` | 人数差值地图 |
| `results/3.Situation_Diagnosis/3.4_Pattern_Comparison/{A}-{B}/star_diff_{A}_{B}_map_distance.png` | 距离差值地图 |
| `results/3.Situation_Diagnosis/3.4_Pattern_Comparison/{A}-{B}/star_diff_{A}_{B}_map_ratio.png` | 内部通勤比差值地图 |
| `results/3.Situation_Diagnosis/3.4_Pattern_Comparison/{A}-{B}/star_diff_{A}_{B}_flowline.png` | 差值流线图 |
| `results/3.Situation_Diagnosis/3.4_Pattern_Comparison/{A}-{B}/star_diff_{A}_{B}_boxplot.png` | 分布对比箱线图 |

### 日志输出

| 路径 | 说明 |
|---|---|
| `log/run_{YYYYMMDD_HHMMSS}.md` | 每次执行的运行日志 |

### 文档更新

| 路径 | 说明 |
|---|---|
| `docs/Result_Analysis.md` | 累加结果解读（执行后手动填写数值） |
| `docs/Technical_Record.md` | 补充方法说明与公式 |

---

## 注意事项

1. `get_result_path(section, filename)` 中 `section` 含子文件夹时（如 `3.1_Basic_Stats/实际格局`），函数会自动创建多级目录
2. `docs/Result_Analysis.md` 和 `docs/Technical_Record.md` 的数值部分在执行后根据实际输出填写，pipeline 中只写模板结构
3. 整个 pipeline 执行时间预计较长（基线格局580万行），建议分章节执行，不要一次性 Run All
4. 执行前确认虚拟环境：`C:\Users\Administrator\.conda\envs\job_housing`
5. 若 `scipy` 未安装（用于 KDE），在该环境中执行：`pip install scipy`
