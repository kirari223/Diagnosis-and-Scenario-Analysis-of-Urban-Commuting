# 阶段1：整数化

## 目标

将基线格局和随机格局（浮点数人数）转换为整数格局，作为后续统计和可视化的输入。

整数化方法：**v1 全局缩放**（截尾 → 四舍五入 → 全局缩放微调），不使用 IPF 行列约束。

---

## 输入

| 文件 | 说明 |
|---|---|
| Wilson 浮点矩阵 `T_baseline`（内存） | 基线格局浮点解，shape (2427, 2427) |
| Wilson 浮点矩阵 `T_random`（内存） | 随机格局浮点解，shape (2427, 2427) |

---

## 操作：调用 `prob_to_int`（`src/data_prep.py`）

使用现有的 `prob_to_int` 函数，**不使用** `prob_to_int_constrained`。

### 算法（v1 全局缩放）

```
Step 1: 截尾  丢弃 value_col < threshold（默认 0.5）
Step 2: 四舍五入  T_int = round(T_float)
Step 3: 全局缩放  scale = target_total / sum(T_int)，再 round
Step 4: 微调  对最大流量 OD 对逐一加减 1，使总量严格等于 target_total
```

### 调用方式

```python
from src.data_prep import matrix_to_long_df, prob_to_int, distance_combine

target_total = int(O_array.sum())

# 基线格局
df_baseline_float = matrix_to_long_df(T_baseline, value_name='人数', o_col='o', d_col='d')
df_baseline_int = prob_to_int(df_prob=df_baseline_float, target_total=target_total)
df_baseline_int = distance_combine(df_baseline_int, distance_dict)

# 随机格局
df_random_float = matrix_to_long_df(T_random, value_name='人数', o_col='o', d_col='d')
df_random_int = prob_to_int(df_prob=df_random_float, target_total=target_total)
df_random_int = distance_combine(df_random_int, distance_dict)
```

---

## 输出

| 文件 | 说明 |
|---|---|
| `results/2.Pattern_Computation/2.4Baseline_Int/star_baseline_int.csv` | 基线格局整数化结果（论文直引） |
| `results/2.Pattern_Computation/2.5Random_Int/star_random_int.csv` | 随机格局整数化结果（论文直引） |

---

## 验证

```python
assert df_baseline_int['人数'].sum() == target_total
assert df_random_int['人数'].sum() == target_total
```
