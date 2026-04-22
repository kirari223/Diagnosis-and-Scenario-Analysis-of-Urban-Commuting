# 步骤 4.1/4.2：刚性提取（Rigidity Extraction）

## 目标

用泊松回归对全量通勤格局进行拟合，分别估计 O 端和 D 端的刚性参数 $\alpha_O$、$\alpha_D$，再映射为 UOT 模型所需的惩罚权重 $\theta_O$、$\theta_D$。

---

## 模型说明

### 泊松回归形式

**D 端刚性估计**（控制起点固定效应，测量就业岗位对通勤流的纯拉力）：

$$\ln \mathbb{E}[T_{ij}] = \mu_i + \alpha_D \cdot \ln(D_j + 1) - \beta \cdot C_{ij}$$

**O 端刚性估计**（控制终点固定效应，测量居住人口对通勤流的纯推力）：

$$\ln \mathbb{E}[T_{ij}] = \nu_j + \alpha_O \cdot \ln(O_i + 1) - \beta \cdot C_{ij}$$

### 参数含义

| 参数 | 含义 |
|---|---|
| $T_{ij}$ | 从居住地 $i$ 到工作地 $j$ 的通勤流量 |
| $O_i$ | 居住地 $i$ 的总居住人口 |
| $D_j$ | 工作地 $j$ 的总就业岗位 |
| $C_{ij}$ | 居住地 $i$ 到工作地 $j$ 的通勤距离（单位：米） |
| $\beta$ | 距离衰减系数，**固定为 Wilson 标定值（米单位下约 0.0003）**，作为 offset 引入，不参与估计 |
| $\mu_i$ | 起点固定效应，吸收起点 $i$ 特有的内在推力 |
| $\nu_j$ | 终点固定效应，吸收终点 $j$ 特有的内在吸引力 |
| $\alpha_O, \alpha_D$ | **核心参数**：$\alpha$ 越接近 1，该端越刚性；$\alpha$ 越小，该端越容易调整 |

### 从 $\alpha$ 映射到 $\theta$

$$\tau \approx \alpha, \quad \theta = \frac{\tau}{1 - \tau} \cdot \varepsilon, \quad \varepsilon = \frac{1}{\beta}$$

$\theta$ 直接进入 UOT 目标函数，作为控制"是否允许搬家/换工作"的惩罚权重。$\theta$ 越大，偏离现状代价越高，格局越刚性。

### 实现注意事项

- **保留零值样本**：泊松回归（PPML）能正确处理 $T_{ij}=0$ 的 OD 对，不应删除零值，否则会高估 $\alpha$
- **$\beta$ 单位**：距离单位为米时 $\beta \approx 0.0003$，为千米时 $\beta \approx 0.3$，offset 符号为负（$-\beta C_{ij}$）
- **固定效应**：D 端回归加起点哑变量，O 端回归加终点哑变量

---

## 输入

| 变量 | 来源 | 说明 |
|---|---|---|
| `T_obs` | `data/[主城区]TAZ4-od聚合.csv` 转矩阵 | 实际通勤 OD 矩阵，shape (n_taz, n_taz) |
| `O_array` | `results/1.Data_Preprocess/` | O 边际向量，shape (n_taz,) |
| `D_array` | `results/1.Data_Preprocess/` | D 边际向量，shape (n_taz,) |
| `C_matrix` | `data/[主城区]TAZ4距离-完整版.csv` | 距离矩阵，shape (n_taz, n_taz)，单位：米 |
| `beta` | `results/2.Pattern_Computation/2.2Baseline_Pattern/calibration_summary.csv` | Wilson 标定 beta（米单位） |

---

## 参考代码
F:\02_250910_Commute\15-FINAL\0415情景推演步骤教育\泊松回归估计弹性参考代码.md

---

## 输出

输出路径：`results/4.Scenario_Analysis/4.2Rigidity_Computation/`

| 文件 | 说明 |
|---|---|
| `star_rigidity_params.csv` | 核心结果：alpha_O, alpha_D, theta_O, theta_D, epsilon |
| `rigidity_regression_stats.csv` | 回归统计：系数、p 值、样本量 |

---

## 关键函数

**`src/elasticity.py`**：

```python
def estimate_rigidity_poisson(
    T_obs: np.ndarray,
    O_array: np.ndarray,
    D_array: np.ndarray,
    C_matrix: np.ndarray,
    beta: float,
    output_dir: Path = None,
) -> dict:
    """
    泊松回归估计 O/D 端刚性参数，并映射为 UOT 惩罚权重 theta。

    Returns:
        dict: {
            'alpha_O': float,   O 端刚性系数
            'alpha_D': float,   D 端刚性系数
            'theta_O': float,   O 端 UOT 惩罚权重
            'theta_D': float,   D 端 UOT 惩罚权重
            'epsilon': float,   熵正则强度 1/beta
        }
    """
```

---

## 调用示例

```python
from src.elasticity import estimate_rigidity_poisson
from src.config import get_result_path

output_dir = get_result_path('4.Scenario_Analysis/4.2Rigidity_Computation', '')
result = estimate_rigidity_poisson(
    T_obs=T_observed,
    O_array=O_array,
    D_array=D_array,
    C_matrix=C_matrix,
    beta=best_beta,
    output_dir=output_dir,
)
theta_O = result['theta_O']
theta_D = result['theta_D']
```

---

## 验证清单

- [ ] `alpha_O` 和 `alpha_D` 均在 (0, 1) 范围内（超出则检查 beta 单位）
- [ ] `theta_O`、`theta_D` 为正数
- [ ] 回归 p 值 < 0.05
- [ ] `star_rigidity_params.csv` 包含 alpha_O, alpha_D, theta_O, theta_D, epsilon 五列
