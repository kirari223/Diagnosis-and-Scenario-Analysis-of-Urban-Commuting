# 技术记录

## 2026-04-14 13:34:03 — Wilson 重扫参与统计信息重输出

对应日志：`log/run_20260414_133403.md`

---

### 1. 数据预处理

原始数据通过 `df_to_matrix()` 向量化读取，无循环，秒级完成百万级数据转换。

- 静态人口文件（`[主城区]TAZ4-static.csv`）按 `人口类型` 字段分别提取居住（home）和就业（work）分布，构建 $O$ 向量和 $D$ 向量，维度均为 $2427 \times 1$。
- 距离文件（`[主城区]TAZ4距离-完整版.csv`）构建阻抗矩阵 $C \in \mathbb{R}^{2427 \times 2427}$。
- OD 聚合文件（`[主城区]TAZ4-od聚合.csv`）构建实际通勤矩阵 $T^{\text{obs}} \in \mathbb{R}^{2427 \times 2427}$。

---

### 2. Wilson 双约束最大熵模型

#### 2.1 模型形式

Wilson 双约束模型的通勤流矩阵为：

$$T_{ij} = A_i O_i B_j D_j \exp(-\beta c_{ij})$$

其中平衡因子满足：

$$A_i = \frac{1}{\sum_j B_j D_j \exp(-\beta c_{ij})}, \quad B_j = \frac{1}{\sum_i A_i O_i \exp(-\beta c_{ij})}$$

通过交替迭代（IPF）求解，收敛条件为相邻迭代步平衡因子的相对变化量 $< 10^{-10}$，最大迭代次数设为 50。

#### 2.2 基线格局标定

以实际格局加权平均通勤距离 $\bar{d}^{\text{obs}} = 5577.58$ m 为标定目标，采用两阶段扫参：

- **粗扫**：$\beta \in [0.0001, 0.001]$，步长 $\Delta\beta = 0.0001$，共 10 个点
- **精细扫**：以粗扫最优值为中心，范围 $\pm 0.0001$，步长 $\Delta\beta = 0.00001$

标定结果：$\beta^* = 0.0003$，模型平均通勤距离 $\bar{d}^{\text{model}} = 5610.96$ m，相对误差 $0.60\%$。

注：本研究距离单位为米，$\beta$ 量级约为 $10^{-4}$，与以千米为单位的文献中 $\beta \approx 0.3$ 量级一致（$0.0003 \times 1000 = 0.3$）。

#### 2.3 随机格局

令 $\beta = 0$，则 $\exp(-\beta c_{ij}) = 1$，模型退化为：

$$T_{ij} = A_i O_i B_j D_j$$

即在满足 $O$、$D$ 双约束的条件下，通勤流按比例均匀分配，不受距离影响。此格局作为"无距离约束"的参照基准，其平均通勤距离 $\bar{d}^{\text{random}} = 13649.74$ m。

---

### 3. 整数化方法

浮点格局通过以下步骤转换为整数格局：

1. **截尾**：丢弃人数 $< 0.5$ 的 OD 对
2. **四舍五入**：$T_{ij}^{\text{int}} = \text{round}(T_{ij})$
3. **全局缩放**：$T_{ij}^{\text{scaled}} = \text{round}(T_{ij}^{\text{int}} \cdot \frac{W}{\sum T_{ij}^{\text{int}}})$，其中 $W = \sum O_i = 2{,}212{,}508$
4. **微调**：对最大流量 OD 对逐一加减 1，使总量严格等于 $W$

---

### 4. KL 散度与 Jensen-Shannon 散度

设两格局的归一化概率分布为 $P = \{p_{ij}\}$，$Q = \{q_{ij}\}$，其中 $p_{ij} = T_{ij}^A / \sum T^A$，$q_{ij} = T_{ij}^B / \sum T^B$。

**KL 散度**（非对称）：

$$\text{KL}(P \| Q) = \sum_{ij} p_{ij} \ln \frac{p_{ij}}{q_{ij}}$$

**Jensen-Shannon 散度**（对称，有界 $[0, \ln 2]$）：

$$\text{JSD}(P \| Q) = \frac{1}{2} \text{KL}(P \| M) + \frac{1}{2} \text{KL}(Q \| M), \quad M = \frac{P + Q}{2}$$

对于 OD 对并集中缺失的值，填充 $\epsilon = 10^{-10}$ 以避免 $\log(0)$。

---

### 5. TAZ 级指标计算

对每个 TAZ $i$ 作为出行起点，计算：

- **总通勤人数**：$N_i = \sum_j T_{ij}$
- **加权平均通勤距离**：$\bar{d}_i = \sum_j T_{ij} c_{ij} / N_i$
- **内部通勤比**：$r_i = T_{ii} / N_i \times 100\%$

---

## 2026-04-14 20:51:55 — 整数化步骤顺序修正

对应日志：`log/run_20260414_205155.md`

---

### 3. 整数化方法（最终版）

#### 3.1 问题背景

Wilson 双约束模型输出的 $T_{ij}^{\text{float}}$ 是**概率尺度**的期望流量（行列和等于 $O_i$/$D_j$，但数值量级远小于真实人数）。上一版本先截尾再缩放，导致截尾阈值 0.5 在概率尺度上无物理意义，远距离小流量 OD 对被过度丢弃。

#### 3.2 修正后的步骤顺序

```
Step 1: 缩放  T_scaled = T_float * W / sum(T_float)   （先还原到真实人数尺度）
Step 2: 截尾  丢弃 T_scaled < 0.5                      （0.5人以下无意义）
Step 3: 四舍五入  T_int = round(T_scaled)
Step 4: IPF 行列约束调整（逻辑不变）
Step 5: 全局微调使总量严格等于 W
```

缩放因子为 $s = W / \sum_{ij} T_{ij}^{\text{float}}$，其中 $W = \sum_i O_i = 2{,}212{,}508$。由于 Wilson 浮点解满足双约束，缩放后 $\sum_j s \cdot T_{ij}^{\text{float}} = s \cdot O_i$，截尾前行列和已与目标对齐，IPF 调整量更小。

#### 3.3 整数化误差对比（三次迭代）

| 版本 | 基线 OD 对数 | 基线行 MAE | 基线列 MAE | 随机 OD 对数 | 随机行 MAE |
|------|------------|-----------|-----------|------------|-----------|
| v1（仅全局缩放） | 524,289 | — | — | 820,012 | — |
| v2（先截尾再缩放+IPF） | 333,477 | 3.71 | 2.20 | 389,560 | 62.92 |
| v3（先缩放再截尾+IPF，当前） | 358,854 | 3.53 | 1.23 | 436,702 | 39.68 |

v3 在 OD 对数、列 MAE、随机格局行 MAE 三个维度均优于 v2，是理论上最正确的实现。

---

### 8. 代码变更记录（2026-04-14 20:51）

1. **`prob_to_int_constrained` 步骤顺序修正**（`src/data_prep.py`）：将"截尾→四舍五入→全局缩放"改为"全局缩放→截尾→四舍五入"，IPF 和误差统计逻辑不变。

2. **Pipeline 3.1 节**（`notebooks/01_main_pipeline.py`）：删除 `star_taz_indicators_*.csv` 的保存逻辑（spec 中无此文件）；`compute_taz_indicators` 仍在内存中调用供 3.4 差值计算使用；static/flow stats 只对 `baseline`/`random` 重跑。

3. **Pipeline 3.4 节**（`notebooks/01_main_pipeline.py`）：只重跑涉及 baseline/random 的三对（actual-baseline、baseline-ideal、actual-random），actual-ideal 不重跑。


对应日志：`log/run_20260414_193300.md`

---

### 3. 整数化方法（更新版）

#### 3.1 问题背景

Wilson 双约束模型的浮点解严格满足：

$$\sum_j T_{ij} = O_i, \quad \sum_i T_{ij} = D_j$$

但原 `prob_to_int` 仅保证总量 $\sum_{ij} T_{ij} = W$，整数化后行列约束不再成立，引入了系统性偏差。

#### 3.2 新方法：IPF 整数化（`prob_to_int_constrained`）

在截尾 + 四舍五入 + 全局缩放的基础上，增加 IPF（Iterative Proportional Fitting）行列调整：

**算法流程：**

1. 截尾：丢弃 $T_{ij} < 0.5$ 的 OD 对
2. 初始四舍五入 + 全局缩放至目标总量
3. **IPF 迭代**（最多 20 轮）：
   - 行调整：对每个起点 $i$，计算 $\delta_i = O_i - \sum_j T_{ij}^{\text{int}}$，按流量大小排序，对最大的 $|\delta_i|$ 个 OD 对加减 1
   - 列调整：对每个终点 $j$，同理调整 $\delta_j = D_j - \sum_i T_{ij}^{\text{int}}$
   - 收敛条件：$\sum_i |\delta_i| + \sum_j |\delta_j| \leq W \times 0.001$
4. 全局微调使总量严格等于 $W$

**误差定义：**

$$e_i^O = \sum_j T_{ij}^{\text{int}} - O_i, \quad e_j^D = \sum_i T_{ij}^{\text{int}} - D_j$$

$$\text{MAE}^O = \frac{1}{|\mathcal{I}|} \sum_i |e_i^O|, \quad \text{RMSE}^O = \sqrt{\frac{1}{|\mathcal{I}|} \sum_i (e_i^O)^2}$$

因此 prob_to_int_constrained 施加的行列约束目标，和"与实际格局对齐 OD 约束"，在数值上是同一件事，只是描述角度不同：

从模型角度说：保持 Wilson 双约束的边际分布
从数据角度说：与实际格局的行列和对齐

#### 3.3 整数化误差结果

| 格局 | OD 对数 | 行 MAE | 行 RMSE | 行最大误差 | 列 MAE | 列 RMSE | 列最大误差 |
|------|---------|--------|---------|-----------|--------|---------|-----------|
| 基线 | 333,477 | 3.71 | 11.98 | 155 | 2.20 | 6.29 | 83 |
| 随机 | 389,560 | 62.92 | 109.46 | 1017 | 74.95 | 110.09 | 549 |

基线格局误差极小（行 MAE=3.71，相对误差率 0.17%），整数化质量高。随机格局误差较大，根本原因是 $\beta=0$ 时浮点流量极度均匀分散（每个 OD 对约 $W/(2427^2) \approx 0.38$ 人），截尾后大量 OD 对被丢弃，剩余 OD 对无法完整覆盖所有 TAZ 的约束，属于随机格局本身的结构特性。

---

### 7. 代码变更记录（2026-04-14 19:33）

1. **新增 `prob_to_int_constrained`**（`src/data_prep.py`）：带行列约束的 IPF 整数化函数，输出行误差、列误差、约束摘要三个 CSV 文件。

2. **Pipeline 2.4/2.5 节**（`notebooks/01_main_pipeline.py`）：改用 `prob_to_int_constrained`，传入 `O_array`、`D_array` 作为约束目标。


本次运行发现并修复以下问题：

1. **`compute_wilson` beta=0 bug**：原代码 `beta = beta or WILSON_DEFAULT_BETA` 在 `beta=0` 时会将其替换为默认值 0.32，导致随机格局无法正确计算。修复为 `if beta is None: beta = WILSON_DEFAULT_BETA`。

2. **`models_pattern.py` 导入错误**：原代码导入不存在的 `get_pattern_path`，修复为 `get_result_path`。

3. **`data_prep.py` emoji 编码错误**：Windows GBK 终端无法编码 `✅` 和 `🔥`，替换为 ASCII 字符。

4. **`compute_diff_statistics` 列名错误**：函数尝试访问 `{col}_pct_change` 列，但 `compute_diff` 从未生成该列。修复为条件判断，仅在列存在时才计算。

5. **beta 扫参范围错误**：原范围 `(0.01, 1.0)` 对应距离 `<1000 m`，远低于目标 5577 m。修正为 `(0.0001, 0.001)`，对应距离范围约 `917~10281 m`。

6. **`compute_statistics` / `compute_diff_statistics` 输出路径**：原函数硬编码 `RESULTS_DIR`，忽略 `output_dir` 参数。新增 `output_dir` 参数支持，并在 pipeline 中传入正确路径。

---

## 2026-04-14 22:12:28 — 整数化回退 v1，统计重输出

对应日志：`log/run_20260414_221228.md`

---

### 9. 整数化方法最终选定（v1 全局缩放）

经过三版对比后，最终选定 v1 全局缩放方案，理由如下：

Wilson 浮点解 $T_{ij}^{\text{float}}$ 本身满足双约束 $\sum_j T_{ij}^{\text{float}} = O_i$，全局缩放 $T_{ij}^{\text{scaled}} = T_{ij}^{\text{float}} \cdot W / \sum T^{\text{float}}$ 后，行列和自然接近 $O_i$/$D_j$（误差仅来自四舍五入）。v2/v3 的 IPF 是在截尾破坏结构后的补救，截尾优先丢弃远距离小流量 OD 对，导致平均距离偏短，且 OD 两端静态统计与实际格局的差值反而更大。

**最终步骤**（`prob_to_int`，`src/data_prep.py`）：

```
Step 1: 截尾  丢弃 T_float < threshold（默认 0.5）
Step 2: 四舍五入  T_int = round(T_float)
Step 3: 全局缩放  scale = W / sum(T_int)，再 round
Step 4: 微调  对最大流量 OD 对逐一加减 1，使总量严格等于 W
```

### 10. 差值对调整

本次将差值对从原来的「实际-理想、实际-基线、基线-理想、实际-随机」调整为「实际-理想、实际-基线、实际-随机、随机-理想」，新增随机-理想对比，删除基线-理想对比（保留在 KL 散度中）。

### 11. 代码变更记录（2026-04-14 22:12）

1. **`src/metrics_eval.py`**：新增 `_safe_write_csv` 函数，用临时文件+原子替换解决 Windows IDE 文件锁定问题；`pattern_static_stats` 和 `pattern_flow_stats` 的简明版 CSV 改用 `_safe_write_csv` 写入。

2. **`notebooks/01_main_pipeline.py`**：3.1 节改为先写到 `_new/` 子目录，再尝试移动覆盖（跳过被锁定的文件）；3.4 节差值对调整为四对（实际-理想、实际-基线、实际-随机、随机-理想）。

3. **spec 更新**：`01_phase3_visualization.md` 中格局本身可视化明确为 OD 端分布图，差值可视化四对改为实际-理想、实际-基线、实际-随机、随机-理想。

---

## 2026-04-20 22:00 — 评估模块搭建（静态结构层 + 优化潜力层）

对应日志：`log/run_评估模块搭建_20260420_220000.md`

---

### 3.1.1 Static_Stats — 静态结构层方法

#### 职住平衡度

$$B_i = \frac{D_i}{O_i}$$

其中 $D_i$ 为TAZ $i$ 的工作地人数，$O_i$ 为居住地人数。数据来源于 `[主城区]TAZ4-static.csv`，按 `人口类型` 字段分别提取 `home`（居住）和 `work`（工作）人数。

#### 街道级自给度

$$S_k = \frac{\sum_{i \in k, j \in k} T_{ij}}{\sum_{i \in k} \sum_{j} T_{ij} + \sum_{j \in k} \sum_{i} T_{ij} - \sum_{i \in k, j \in k} T_{ij}}$$

实现步骤：
1. 将TAZ中心点（`fence` 的 `center_x/center_y`，WGS84）转为EPSG:32649，与街道边界做空间关联（`sjoin`，`within`谓词）
2. 一个TAZ中心点可能落在多个街道边界重叠区域，取第一个匹配结果
3. 按街道聚合O端总流、D端总流、内部流，按上式计算自给度

#### 标准差椭圆

加权协方差矩阵：

$$\Sigma = \begin{bmatrix} \sum_i w_i (x_i - \bar{x})^2 & \sum_i w_i (x_i - \bar{x})(y_i - \bar{y}) \ \sum_i w_i (x_i - \bar{x})(y_i - \bar{y}) & \sum_i w_i (y_i - \bar{y})^2 \end{bmatrix}$$

其中 $w_i$ 为归一化权重（人数/总人数），$(\bar{x}, \bar{y})$ 为加权均值坐标。

椭圆参数由特征值分解得到：$\Sigma \mathbf{v} = \lambda \mathbf{v}$，长半轴 $a = 2\sqrt{\lambda_1}$，短半轴 $b = 2\sqrt{\lambda_2}$。

坐标系：TAZ中心点经纬度（WGS84）转为EPSG:32649（米）后计算，保证椭圆形状不受经纬度变形影响。

---

### 3.1.3 Pattern_Comparison — 优化潜力层方法

#### 超额通勤指标体系

$$EC = \frac{C_{obs} - C_{min}}{C_{obs}} \times 100\%$$

$$NEC = \frac{C_{obs} - C_{min}}{C_{ran} - C_{min}} \times 100\%$$

$$CE = \frac{C_{ran} - C_{obs}}{C_{ran}} \times 100\%$$

$$NCE = \frac{C_{ran} - C_{obs}}{C_{ran} - C_{min}} \times 100\%$$

其中：
- $C_{obs} = 5.578$ km（实际格局加权平均通勤距离）
- $C_{min} = 1.118$ km（理想格局，线性规划最优解）
- $C_{ran} = 13.144$ km（随机格局，Wilson模型 $\beta=0$ 时的期望距离）

数学约束：$NEC + NCE = 100\%$（已验证）。

#### 格局对比可视化

- **箱线图**：截尾阈值 cap=20人，保留小流量OD对的分布特征，避免极端值干扰
- **距离pdf**：截尾 20km，加权KDE（权重为人数），带宽采用Scott方法
- **差值图**：调用 `compute_taz_indicators()` 分别计算各格局TAZ指标，再调用 `compute_diff()` 计算差值，最后 `create_diff_maps()` 出图
- **OD流线图**：两格局OD数据outer join后计算差值列，调用 `create_flowline(is_diff=True)`，绘制流量绝对值最大的前500条OD流线，使用RdBu_r发散色阶
