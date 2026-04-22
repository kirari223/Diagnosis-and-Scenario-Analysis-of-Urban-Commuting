# 步骤 4.4.3：可视化（Scenario Compare Visualization）

## 目标

为情景格局输出 OD 端分布图、OD 流线图，为情景与实际格局的差值输出差值分布图、流线差值图、人数与距离分布对比箱线图。所有图风格统一，可直接用于论文。

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

## 输出文件清单

输出路径：`results/4.Scenario_Analysis/4.4Scenario_Compare/4.4.3Scenario_Compare_Visualize/`

### 情景格局本身

| 文件 | 函数 | 说明 |
|---|---|---|
| `star_{scenario_label}_static_O.png` | `create_choropleth_map` | O 端（居住地）出行量分布 |
| `star_{scenario_label}_static_D.png` | `create_choropleth_map` | D 端（就业地）吸引量分布 |
| `star_{scenario_label}_flowline.png` | `create_flowline` | 情景格局 OD 流线图 |

### 差值对比

| 文件 | 函数 | 说明 |
|---|---|---|
| `star_diff_actual_vs_{scenario_label}_O.png` | `create_diverging_map` | O 端出行量差值 diverging choropleth |
| `star_diff_actual_vs_{scenario_label}_D.png` | `create_diverging_map` | D 端吸引量差值 diverging choropleth |
| `star_diff_actual_vs_{scenario_label}_flowline.png` | `create_flowline` | OD 流线差值图（is_diff=True） |
| `star_diff_actual_vs_{scenario_label}_boxplot_people.png` | `create_distribution_plot` | 人数分布对比箱线图 |
| `star_diff_actual_vs_{scenario_label}_boxplot_distance.png` | `create_distribution_plot` | 距离分布对比箱线图 |

---

## 前置条件

- `src/visualization.py` 导入 bug 已修复（`get_figure_path` 已替换为 `get_result_path`）
- `create_flowline` 和 `create_distribution_plot` 已在 `src/visualization.py` 中实现
- `create_diverging_map` 的 `config_key` 参数已改为可选

---

## 调用示例

```python
from src.visualization import (
    create_choropleth_map, create_diverging_map,
    create_flowline, create_distribution_plot,
)
from src.config import get_result_path
import geopandas as gpd

dir_443 = get_result_path('4.Scenario_Analysis/4.4Scenario_Compare/4.4.3Scenario_Compare_Visualize', '')

# 情景格局 O/D 端分布图
# 先用 compute_taz_indicators 聚合出 TAZ 级指标
gdf_scenario_taz = compute_taz_indicators(df_scenario, fence)

create_choropleth_map(
    gdf_data=gdf_scenario_taz, gdf_base=fence,
    column='总通勤人数', config_key='total_people',
    output_path=dir_443 / f'star_{scenario_label}_static_O.png',
)
create_choropleth_map(
    gdf_data=gdf_scenario_taz, gdf_base=fence,
    column='总通勤人数', config_key='total_people',
    output_path=dir_443 / f'star_{scenario_label}_static_D.png',
)

# 情景格局流线图
create_flowline(
    df_od=df_scenario, fence=fence,
    output_path=dir_443 / f'star_{scenario_label}_flowline.png',
    is_diff=False,
)

# 差值地图（gdf_diff 来自步骤 4.4.2 的 compute_diff 输出）
create_diverging_map(
    gdf_data=gdf_diff, gdf_base=fence,
    column='总通勤人数_diff',
    output_path=dir_443 / f'star_diff_actual_vs_{scenario_label}_O.png',
)
create_diverging_map(
    gdf_data=gdf_diff, gdf_base=fence,
    column='总通勤人数_diff',
    output_path=dir_443 / f'star_diff_actual_vs_{scenario_label}_D.png',
)

# 差值流线图
create_flowline(
    df_od=df_diff_merged, fence=fence,
    output_path=dir_443 / f'star_diff_actual_vs_{scenario_label}_flowline.png',
    is_diff=True,
)

# 箱线图
create_distribution_plot(
    df_a=df_actual, df_b=df_scenario,
    name_a='actual', name_b=scenario_label,
    output_path=dir_443 / f'star_diff_actual_vs_{scenario_label}_boxplot_people.png',
    col='人数',
)
create_distribution_plot(
    df_a=df_actual, df_b=df_scenario,
    name_a='actual', name_b=scenario_label,
    output_path=dir_443 / f'star_diff_actual_vs_{scenario_label}_boxplot_distance.png',
    col='distance',
)
```

---

## 操作一：`create_choropleth_map`（已有）

用于情景格局 O/D 端分布图。接受 TAZ 级聚合 GeoDataFrame，按 `config.COLOR_SCHEMES` 配色。

签名（已有，`output_path` 由调用方传入）：

```python
def create_choropleth_map(
    gdf_data: gpd.GeoDataFrame,
    gdf_base: gpd.GeoDataFrame,
    column: str,
    config_key: str,
    output_path: Path = None,
    title: str = None,
    save: bool = True,
) -> None:
```

---

## 操作二：`create_diverging_map`（已有，签名修正）

用于差值分布图。`config_key` 改为可选参数（默认 `None`），自动根据列名前缀推断配色方案。

```python
def create_diverging_map(
    gdf_data: gpd.GeoDataFrame,
    gdf_base: gpd.GeoDataFrame,
    column: str,
    config_key: str = None,   # 可选，None 时自动推断
    output_path: Path = None,
    title: str = None,
    save: bool = True,
) -> None:
```

---

## 操作三：`create_flowline`（新增）

用于格局本身的 OD 流线图和差值流线图。

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

实现逻辑：

1. 构建 TAZ 中心点坐标字典（`fence.geometry.centroid`）
2. 为 OD 数据关联起终点坐标，dropna
3. 筛选 top_n 条（差值模式按绝对值排序）
4. 绘制底图 + `LineCollection`（差值模式用 `RdBu_r` + `TwoSlopeNorm`，单格局用 `cmap_single` + `Normalize`）
5. 线宽按流量绝对值映射到 `[0.3, linewidth_scale]`
6. 添加 colorbar、指北针、比例尺，`ax.set_axis_off()`，保存

---

## 操作四：`create_distribution_plot`（新增）

用于人数/距离分布对比箱线图。

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

实现逻辑：

- 并排箱线图，左侧为格局 A，右侧为格局 B
- 颜色：`#2E7D9A`（A）/ `#C65A4A`（B）
- x 轴标签为格局名，y 轴为人数（人）或距离（m）
- 图幅 (10, 7)，字体 SimHei，标签 24pt
- 保存为 PNG，300 DPI

---

## 验证清单

- [ ] 所有 PNG 文件存在于 `4.4.3Scenario_Compare_Visualize/`
- [ ] 地图包含指北针、比例尺、色标
- [ ] 流线图 top_n 条线可见，颜色映射正确
- [ ] 差值流线图正负值颜色区分明显（`RdBu_r`）
- [ ] 箱线图两侧标签清晰，y 轴单位正确
