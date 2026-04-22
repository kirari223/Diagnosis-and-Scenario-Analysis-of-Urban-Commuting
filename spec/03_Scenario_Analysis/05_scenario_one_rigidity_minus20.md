# 情景一：居家办公趋势提升下的刚性降低情景

## 情景背景

**城市更新与产业结构转型**：长沙近年大力发展数字经济、文化创意、人工智能等高科技产业（湘江新区、马栏山视频文创园、岳麓山大学科技城）。这些产业的岗位特征更适合居家办公、混合办公等灵活模式。

**政策背书**：
- 《长沙市数字经济发展"十四五"规划》：推动数字技术与实体经济深度融合，鼓励企业创新工作模式
- 《湘江新区"十四五"规划》：打造创新高地和人才集聚区，高新技术人才对工作灵活性有更高要求

**情景叙事**：随着数字经济产业进一步发展，以及城市更新带来的新型办公空间（联合办公、社区工作站）普及，居家办公（或混合办公）将成为更多居民的选择。人们对"必须每天准时到达固定工作地点"的约束感降低，职住的"刚性"随之下降。

---

## 情景参数设定

**情景名称**：全量刚性降低 20%

**参数**：

| 参数 | 值 | 说明 |
|---|---|---|
| `rigidity_multiplier` | `0.8` | 刚性降低 20% |
| `scenario_label` | `'rigidity_minus20'` | 文件命名标识 |

**操作逻辑**：

1. 通过泊松回归得到基准刚性 $\alpha_O^{\text{base}}, \alpha_D^{\text{base}}$，映射为 $\theta_O^{\text{base}}, \theta_D^{\text{base}}$
2. 情景设定：$\theta_O^{\text{scenario}} = \theta_O^{\text{base}} \times 0.8$，$\theta_D^{\text{scenario}} = \theta_D^{\text{base}} \times 0.8$
3. 调用 UOT 求解器，以降低后的 $\theta$ 推演新的 OD 格局

**模拟机制**：$\theta$ 降低后，KL 惩罚项权重减小，模型更倾向于让 $O^*$ 和 $D^*$ 偏离现状 $O_0$ 和 $D_0$，以寻找更优的职住匹配，等价于"更容易搬家/换工作"。总通勤人数 $M$ 保持不变。

---

## 预期结果方向

| 指标 | 预期变化 | 机制 |
|---|---|---|
| 平均通勤距离 | 增加 | 刚性降低 → 职住匹配更自由 → 部分人接受更远通勤换取更优岗位 |
| KL(O*\|\|O0) | > 0 | 居住端分布偏离现状 |
| KL(D*\|\|D0) | > 0 | 就业端分布偏离现状 |
| 与实际格局 KL 散度 | 增加 | 情景格局与实际格局结构差异扩大 |

---

## 输出路径

```
results/4.Scenario_Analysis/
  4.2Rigidity_Computation/
    star_rigidity_params.csv          # alpha_O, alpha_D, theta_O, theta_D
  4.3Scenario_Computation/
    rigidity_minus20/
      T_scenario_float.npy
      star_rigidity_minus20_int.csv
      scenario_computation_stats.csv
  4.4Scenario_Compare/
    4.4.1Scenario_Pattern_Stats/
      star_rigidity_minus20_static_concise_stats.csv
      star_rigidity_minus20_flow_concise_stats.csv
    4.4.2Scenario_Actual_Compare/
      star_kl_actual_rigidity_minus20.csv
      star_diff_actual_vs_rigidity_minus20.csv
    4.4.3Scenario_Compare_Visualize/
      star_rigidity_minus20_static_O.png
      star_rigidity_minus20_static_D.png
      star_rigidity_minus20_flowline.png
      star_diff_actual_vs_rigidity_minus20_O.png
      star_diff_actual_vs_rigidity_minus20_D.png
      star_diff_actual_vs_rigidity_minus20_flowline.png
      star_diff_actual_vs_rigidity_minus20_boxplot_people.png
      star_diff_actual_vs_rigidity_minus20_boxplot_distance.png
```

---

## 调用示例

```python
from src.elasticity import estimate_rigidity_poisson, compute_scenario_uot
from src.config import get_result_path

# 步骤 4.2：提取刚性
rigidity_result = estimate_rigidity_poisson(
    T_obs=T_observed,
    O_array=O_array,
    D_array=D_array,
    C_matrix=C_matrix,
    beta=best_beta,
    output_dir=get_result_path('4.Scenario_Analysis/4.2Rigidity_Computation', ''),
)
theta_O = rigidity_result['theta_O']
theta_D = rigidity_result['theta_D']

# 步骤 4.3：情景推演（刚性降低 20%）
scenario_result = compute_scenario_uot(
    C_matrix=C_matrix,
    O_array=O_array,
    D_array=D_array,
    theta_O=theta_O,
    theta_D=theta_D,
    beta=best_beta,
    rigidity_multiplier=0.8,
    scenario_label='rigidity_minus20',
    output_dir=get_result_path('4.Scenario_Analysis/4.3Scenario_Computation/rigidity_minus20', ''),
)
```

---

## 结果解读框架

结果分析应围绕以下三个维度展开：

1. **通勤成本变化**：平均通勤距离是否增加？增幅是否在合理范围（5%~20%）？
2. **职住结构调整**：$O^*$ 和 $D^*$ 偏离现状的幅度（KL 散度），哪端调整更大？
3. **空间格局差异**：与实际格局相比，哪些 TAZ 的通勤流入/流出变化最显著？是否呈现出"近郊扩散"或"跨江通勤增加"的空间特征？

详见 `docs/Result_Analysis.md` 中对应章节。
