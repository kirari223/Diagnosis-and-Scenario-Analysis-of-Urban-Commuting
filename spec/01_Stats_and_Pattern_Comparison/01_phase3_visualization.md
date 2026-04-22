# 阶段3：可视化

## 目标

为四个格局输出 OD 端分布图（choropleth），为四对差值输出差值分布图（diverging）、格局本身的OD流线图、四对格局OD流线差值图（flowline）、人数与距离分布对比箱线图。所有图风格统一，可直接用于论文。

---

## 全局出图规范

| 参数 | 值 |
|---|---|
| 图幅 | (14, 12) |
| DPI | 300 |
| 标签/图例标题字号 | 28pt |
| 图例字号 | 24pt |
| 注释字号 | 20pt |
| 字体 | SimHei（备选 Microsoft YaHei） |
| 底图填充色 | `#F5F5F5` |
| 底图边线色 | `#CCCCCC`，linewidth=0.3 |
| 外边界色 | `#333333`，linewidth=1.5 |
| 专题图层边线 | white，linewidth=0.15 |
| 背景 | 无经纬度网格（`ax.set_axis_off()`） |
| 保存格式 | PNG，300 DPI，bbox_inches='tight'，facecolor='white' |
| 图面标题 | 不在图面中显示 |

颜色方案沿用 `config.COLOR_SCHEMES`，不另起炉灶。

---

## 3.1 Basic_Stats — 格局本身可视化

对四个格局（actual、ideal、baseline、random）各输出 OD 端分布图：

| 图 | 函数 | 说明 |
|---|---|---|
| `star_{name}_static_O.png` | `create_choropleth_map` | O端（居住地）出行量分布 choropleth |
| `star_{name}_static_D.png` | `create_choropleth_map` | D端（就业地）吸引量分布 choropleth |
| `star_{name}_flowline.png` | `create_flowline` | OD流线图，每个格局本身的OD通勤流线图示 |
数据来源：`pattern_static_stats` 输出的 O侧/D侧聚合结果（`总流出量`/`总流入量` 列）。

**不输出**流线图和距离PDF（留待后续阶段）。

---

## 3.4 Pattern_Comparison — 差值可视化

四对差值：**实际-理想、实际-基线、实际-随机、随机-理想**。

对每对输出：

| 图 | 函数 | 说明 |
|---|---|---|
| `star_diff_{nameA}_vs_{nameB}_O.png` | `create_diverging_map` | O端出行量差值 diverging choropleth |
| `star_diff_{nameA}_vs_{nameB}_D.png` | `create_diverging_map` | D端吸引量差值 diverging choropleth |
| `star_diff_{nameA}_vs_{nameB}_flowline.png` | `create_flowline` | OD流线差值图（is_diff=True） |
| `star_diff_{nameA}_vs_{nameB}_boxplot_people.png` | `create_distribution_plot` | 两格局人数分布对比箱线图 |
| `star_diff_{nameA}_vs_{nameB}_boxplot_distance.png` | `create_distribution_plot` | 两格局距离分布对比箱线图 |

---

## 操作一：`create_choropleth_map`（`src/visualization.py`）

用于 3.1 的 O/D 端分布图。接受 TAZ 级聚合数据（O侧总流出量 / D侧总流入量），按 `config.COLOR_SCHEMES` 配色。

**签名**（已有，确认 `output_path` 由调用方传入，不依赖 `get_figure_path`）：
```python
def create_choropleth_map(
    gdf_data: gpd.GeoDataFrame,
    gdf_base: gpd.GeoDataFrame,
    column: str,
    config_key: str,
    output_path: Path,
    title: str = '',
) -> None:
```

---

## 操作二：`create_diverging_map`（`src/visualization.py`）

用于 3.4 的 O/D 端差值图。接受 TAZ 级差值 GeoDataFrame（`compute_diff` 输出），按发散色阶显示正负差值。

**签名**（已有，确认 `output_path` 由调用方传入）：
```python
def create_diverging_map(
    gdf_diff: gpd.GeoDataFrame,
    gdf_base: gpd.GeoDataFrame,
    column: str,
    output_path: Path,
    title: str = '',
) -> None:
```

---

## 操作三：`create_flowline`（`src/visualization.py`，新增）

用于 3.4 的 OD 流线差值图。——还需要做格局本身的通勤流线图示，如果跟OD流线差值图无法兼容，请再写对单个格局进行流线可视化的函数

**签名**：
```python
def create_flowline(
    df_od: pd.DataFrame,
    fence: gpd.GeoDataFrame,
    output_path: Path,
    title: str = '',
    flow_col: str = '人数',
    o_col: str = 'o',
    d_col: str = 'd',
    top_n: int = 500,
    is_diff: bool = False,
    cmap_single: str = 'YlOrRd',
    linewidth_scale: float = 3.0,
    alpha: float = 0.6,
) -> None:
```

**实现逻辑**：

1. 构建 TAZ 中心点坐标字典（从 `fence.geometry.centroid`）
2. 为 OD 数据关联起终点坐标，dropna
3. 筛选 top_n 条（差值模式按绝对值排序）
4. 绘制底图 + LineCollection（差值模式用 `RdBu_r` + `TwoSlopeNorm`，单格局用 `cmap_single` + `Normalize`）
5. 线宽按流量绝对值映射到 [0.3, linewidth_scale]
6. 添加 colorbar、指北针、比例尺，`ax.set_axis_off()`，保存

---

## 操作四：`create_distribution_plot`（`src/visualization.py`，新增）

用于 3.4 的人数/距离分布对比箱线图。

**签名**：
```python
def create_distribution_plot(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    name_a: str,
    name_b: str,
    output_path: Path,
    col: str = '人数',
    title: str = '',
) -> None:
```

**实现逻辑**：

- 并排箱线图，左侧为格局A，右侧为格局B
- 箱线图颜色从 `config.COLOR_SCHEMES` 取（或使用 `#2E7D9A` / `#C65A4A`）
- x轴标签为格局名，y轴为人数（人）或距离（m）
- 图幅 (10, 7)，字体 SimHei，标签 24pt
- 保存为 PNG，300 DPI
