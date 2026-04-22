# 步骤 4.3：情景推演（Scenario Computation）

## 目标

基于泊松回归提取的刚性参数 $\theta_O$、$\theta_D$，在刚性发生变化的情景假设下，通过非平衡最优传输（UOT）广义 Sinkhorn 迭代求解新的 OD 格局，并整数化输出。

---

## 模型说明

### 非平衡最优传输（UOT）框架
$$W={arg{\min_{γ}\mathrm{\text{ }}}}\mathrm{⟨}γ,\mathbf{M}{{\mathrm{⟩}}_F}+\mathrm{reg}⋅\mathrm{KL}(γ,\mathbf{c})+\mathrm{re{g_{m1}}}⋅\mathrm{KL}(γ\mathbf{1},\mathbf{a})+\mathrm{re{g_{m2}}}⋅\mathrm{KL}(γ^T\mathbf{1},\mathbf{b})$$ 

本模型允许 O/D 边际在总量守恒的前提下偏离现状锚点，以寻找更优的职住匹配。核心思想：

- **锚点边际** $O_0, D_0$：代表现状居住与就业分布
- **刚性参数** $\theta_O, \theta_D$：控制偏离锚点的惩罚强度，$\theta$ 越大越刚性（越难搬家/换工作）
- **总量守恒**：$\sum_{ij} T_{ij} = M$（主城区总通勤人数不增不减）

### 求解算法：广义 Sinkhorn 迭代

**阶段 1：构造核矩阵**

$$K_{ij} = \exp(-\beta \cdot C_{ij}), \quad \varepsilon = 1/\beta$$

**阶段 2：计算松弛指数**

$$\tau_O = \frac{\theta_O}{\theta_O + \varepsilon}, \quad \tau_D = \frac{\theta_D}{\theta_D + \varepsilon}$$

$\tau \in (0,1)$：$\tau$ 越大，边际越被拉回锚点（刚性强）；$\tau$ 越小，边际越自由（刚性弱）。

**阶段 3：迭代更新缩放向量**

$$u \leftarrow u \cdot \left(\frac{O_0}{K v}\right)^{\tau_O}, \quad v \leftarrow v \cdot \left(\frac{D_0}{K^\top u}\right)^{\tau_D}$$

**阶段 4：重构传输矩阵并强制总量守恒**

$$T = \mathrm{diag}(u) \cdot K \cdot \mathrm{diag}(v), \quad T \leftarrow T \cdot \frac{M}{\sum_{ij} T_{ij}}$$

**阶段 5：输出**

$$O^* = T \mathbf{1}, \quad D^* = T^\top \mathbf{1}$$

### 情景参数化

情景通过修改 $\theta$ 实现，不改变 $O_0, D_0$ 和 $M$：

$$\theta_O^{\text{scenario}} = \theta_O^{\text{base}} \times r_O, \quad \theta_D^{\text{scenario}} = \theta_D^{\text{base}} \times r_D$$

其中 $r_O$ = `rigidityO_multiplier`，$r_D$ = `rigidityD_multiplier`。当 $r_O = r_D = r$ 时退化为原单系数形式。

### $\theta$ 与 $\beta$ 的角色对比

| 参数 | 含义 | 在算法中的作用 |
|---|---|---|
| $\beta$ | 距离衰减系数 | 构造核矩阵 $K$，决定空间摩擦强度 |
| $\theta$ | 刚性惩罚权重 | 通过 $\tau$ 决定边际偏离锚点的力度 |
| $\tau$ | 无量纲约束强度 | 直接控制迭代更新步幅，由 $\theta$ 和 $\varepsilon$ 换算得到 |

---

## 输入

| 变量 | 来源 | 说明 |
|---|---|---|
| `C_matrix` | `data/[主城区]TAZ4距离-完整版.csv` | 距离矩阵，单位：米 |
| `O_array` | `results/1.Data_Preprocess/` | O 边际向量（锚点） |
| `D_array` | `results/1.Data_Preprocess/` | D 边际向量（锚点） |
| `theta_O` | `4.2Rigidity_Computation/star_rigidity_params.csv` | O 端基准刚性参数 |
| `theta_D` | `4.2Rigidity_Computation/star_rigidity_params.csv` | D 端基准刚性参数 |
| `beta` | `2.2Baseline_Pattern/calibration_summary.csv` | Wilson 标定 beta |
| `rigidityO_multiplier` | 情景参数 | O 端刚性变化系数，如 1.2 表示提升 20%（默认 1.0） |
| `rigidityD_multiplier` | 情景参数 | D 端刚性变化系数，如 0.8 表示降低 20%（默认 1.0） |
| `scenario_label` | 情景参数 | 情景标识字符串，如 `'rigidity_WFH'` |

---

## 参考代码
F:\02_250910_Commute\15-FINAL\0415情景推演步骤教育\凸优化计算代码.md     

---

## 输出

输出路径：`results/4.Scenario_Analysis/4.3Scenario_Computation/{scenario_label}/`

| 文件 | 说明 |
|---|---|
| `T_scenario_float.npy` | 情景 OD 矩阵（浮点，shape n_taz × n_taz） |
| `star_{scenario_label}_int.csv` | 整数化情景 OD，列：o, d, 人数, distance |
| `scenario_computation_stats.csv` | 求解统计：迭代次数、总流量、平均通勤距离、O*/D* 偏离度 |

---

## 关键函数

**`src/elasticity.py`**：

```python
def solve_uot_scenario(
    C: np.ndarray,
    O0: np.ndarray,
    D0: np.ndarray,
    theta_O: float,
    theta_D: float,
    beta: float,
    total_mass: float,
    max_iter: int = 200,
    tol: float = 1e-5,
) -> tuple:
    """
    UOT 广义 Sinkhorn 求解器：支持双端独立 theta，强制总量守恒。

    Returns:
        T (np.ndarray): 情景 OD 矩阵
        O_star (np.ndarray): 实际 O 边际
        D_star (np.ndarray): 实际 D 边际
    """

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
    output_dir: Path = None,
) -> dict:
    """
    情景推演主函数：修改 theta 后调用 solve_uot_scenario，整数化并保存。

    Returns:
        dict: {
            'T_scenario': np.ndarray,
            'O_star': np.ndarray,
            'D_star': np.ndarray,
            'avg_dist': float,
            'total_flow': float,
        }
    """
```

---

## 调用示例

```python
from src.elasticity import compute_scenario_uot
from src.config import get_result_path

output_dir = get_result_path('4.Scenario_Analysis/4.3Scenario_Computation/rigidity_WFH', '')
result = compute_scenario_uot(
    C_matrix=C_matrix,
    O_array=O_array,
    D_array=D_array,
    theta_O=theta_O,
    theta_D=theta_D,
    beta=best_beta,
    rigidityO_multiplier=1.2,      # O 端刚性提升 20%
    rigidityD_multiplier=0.8,      # D 端刚性降低 20%
    scenario_label='rigidity_WFH',
    output_dir=output_dir,
)
```

---

## 验证清单

- [ ] `T_scenario_float.npy` 总量 $\approx$ `total_mass`（误差 < 1）
- [ ] `star_{scenario_label}_int.csv` 总人数 == `int(O_array.sum())`
- [ ] `scenario_computation_stats.csv` 包含 `rigidityO_multiplier` 和 `rigidityD_multiplier` 两列
- [ ] `O_star` 与 `O_array` 的 KL 散度已记录（反映居住端调整幅度）
- [ ] `D_star` 与 `D_array` 的 KL 散度已记录（反映就业端调整幅度）
- [ ] D 端刚性降低时，平均通勤距离应增加（更多跨区通勤）
