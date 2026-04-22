# 整数化行列约束增强

**日期**: 2026-04-14  
**优先级**: 高

---

## 背景

Wilson 双约束最大熵模型的两个核心约束为：

$$\sum_j T_{ij} = O_i \quad \text{（行约束，起点出行量）}$$

$$\sum_i T_{ij} = D_j \quad \text{（列约束，终点吸引量）}$$

当前 `prob_to_int` 仅保证总量 $\sum_{ij} T_{ij} = W$，不保证每行/列之和与 $O_i$/$D_j$ 一致。整数化后的行列误差未被量化，也未被控制。

---

## 任务目标

1. 在 `src/data_prep.py` 中新增函数 `prob_to_int_constrained`，在整数化过程中尽量满足行列约束，并输出行列误差统计
2. 在 `notebooks/01_main_pipeline.py` 的 `## 2.4` 和 `## 2.5` 节中改用新函数
3. 重新输出基线格局和随机格局的整数化结果，以及所有涉及这两个格局的统计和差值分析

---

## 函数规范：`prob_to_int_constrained`

### 签名

```python
def prob_to_int_constrained(
    df_prob: pd.DataFrame,
    O_array: np.ndarray,
    D_array: np.ndarray,
    target_total: int,
    threshold: float = 0.5,
    value_col: str = '人数',
    o_col: str = 'o',
    d_col: str = 'd',
    output_dir=None,
) -> pd.DataFrame:
```

### 算法

采用 **IPF（Iterative Proportional Fitting）整数化** 方案：

1. **截尾**：丢弃 `value_col < threshold` 的 OD 对
2. **初始四舍五入**：得到初始整数矩阵
3. **IPF 迭代调整**（最多 max_iter=20 轮）：
   - 行调整：对每个起点 $i$，计算当前行和 $r_i = \sum_j T_{ij}^{\text{int}}$ 与目标 $O_i$ 的差值 $\delta_i = O_i - r_i$；按流量大小排序，对最大的 $|\delta_i|$ 个 OD 对加减 1
   - 列调整：对每个终点 $j$，同理调整
   - 收敛条件：所有行列误差绝对值之和 $< \epsilon$（默认 $\epsilon = \sum O_i \times 0.001$，即总量的 0.1%）
4. **误差统计**：输出每个 TAZ 的行误差 $e_i^O = r_i - O_i$ 和列误差 $e_j^D$，以及全局统计（MAE、RMSE、最大绝对误差、误差率）

### 输出文件

- `star_{name}_int_constrained.csv` — 整数化 OD（论文直引）
- `{name}_int_row_error.csv` — 每个 TAZ 的行误差
- `{name}_int_col_error.csv` — 每个 TAZ 的列误差
- `star_{name}_int_constraint_summary.csv` — 全局误差统计（论文直引）

---

## 需要重新输出的结果

### 重新生成（覆盖原文件）

- `results/2.Pattern_Computation/2.4Baseline_Int/star_baseline_int.csv`
- `results/2.Pattern_Computation/2.5Random_Int/star_random_int.csv`

### 重新计算统计（覆盖原文件）

- `results/3.1Basic_Stats/star_taz_indicators_baseline.csv`
- `results/3.1Basic_Stats/star_taz_indicators_random.csv`
- `results/3.1Basic_Stats/star_baseline_*.csv`
- `results/3.1Basic_Stats/star_random_*.csv`

### 重新计算差值（覆盖原文件）

- `results/3.4Pattern_Comparison/star_diff_actual_vs_baseline.csv`
- `results/3.4Pattern_Comparison/star_diff_baseline_vs_ideal.csv`
- `results/3.4Pattern_Comparison/star_diff_actual_vs_random.csv`
- `results/3.4Pattern_Comparison/star_kl_actual_baseline.csv`
- `results/3.4Pattern_Comparison/star_kl_baseline_ideal.csv`
- `results/3.4Pattern_Comparison/star_kl_actual_random.csv`
- 对应的 flow_stats 和 diff_stats

### 不需要重新生成

- 实际格局、理想格局本身的统计（`star_taz_indicators_actual.csv`、`star_taz_indicators_ideal.csv` 等）
- `star_diff_actual_vs_ideal.csv`、`star_kl_actual_ideal.csv`

---

## 验证清单

- [ ] `prob_to_int_constrained` 函数存在于 `src/data_prep.py`
- [ ] 行误差 MAE < 原始 $O_i$ 均值的 5%
- [ ] 列误差 MAE < 原始 $D_j$ 均值的 5%
- [ ] 总量仍等于 `target_total`
- [ ] 误差统计 CSV 已输出
- [ ] 所有涉及基线/随机的统计和差值 CSV 已更新
- [ ] 日志时间戳与文档一致
