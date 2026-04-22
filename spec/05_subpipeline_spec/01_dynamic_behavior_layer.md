# 动态行为层规范 - 3.1.2Dynamic_Stats

## 概述

动态行为层基于完整OD数据（含时间、交通方式信息），分析通勤的时间特征和交通方式特征，并进行OD流可视化和社区发现。

**数据源**: `data/[主城区]TAZ4-od.csv`（507.9 MB）
**列名**: Htaz, Jtaz, 人数, 平均通勤时间(s), 驾车比例, 地铁比例, 公交比例, 骑行比例, 步行比例

---

## 输出文件清单

```
results/3.Situation_Diagnosis/3.1Holistic_Diagnosis/3.1.2Dynamic_Stats/
├── star_平均通勤时间分布图_TAZ.png          # TAZ级平均时间地图
├── star_通勤时长区间占比_饼图.png            # 全局时长分段占比
├── star_交通方式占比_饼图.png                # 全局交通方式占比
├── star_OD流线图_实际格局.html               # transbigdata交互式流线图
├── star_OD流线图_实际格局.png                # HTML转PNG静态图
├── star_社区发现结果.html                    # 社区检测可视化
├── star_社区发现结果.png                     # HTML转PNG静态图
├── star_社区发现_模块度报告.txt              # 模块度、社区数等统计
├── star_动态行为指标汇总.csv                 # 时间、交通方式统计表
└── star_标准差椭圆_通勤流.png                # 基于OD流的标准差椭圆
```

---

## 新增函数规范

### 1. `src/metrics_eval.py`

#### `compute_time_indicators()`

```python
def compute_time_indicators(
    df_od: pd.DataFrame,
    fence: gpd.GeoDataFrame,
    time_col: str = '平均通勤时间(s)',
    o_col: str = 'o',
    d_col: str = 'd',
    value_col: str = '人数',
) -> tuple[gpd.GeoDataFrame, dict]:
    """
    计算TAZ级平均通勤时间和全局时长分段统计。

    Args:
        df_od:     完整OD DataFrame，含时间列
        fence:     TAZ边界GeoDataFrame
        time_col:  时间列名（秒）
        o_col:     起点TAZ列名
        d_col:     终点TAZ列名
        value_col: 人数列名

    Returns:
        tuple:
            gdf_time: TAZ级GeoDataFrame，含 '平均通勤时间_min' 列
            time_stats: dict，含全局时长分段统计
                {
                    '<15分钟': 人数,
                    '15-30分钟': 人数,
                    '30-45分钟': 人数,
                    '45-60分钟': 人数,
                    '>60分钟': 人数,
                    '全局平均时间_min': float,
                }
    """
```

**实现要点**:
- TAZ级：按o_col聚合，加权平均时间（权重=人数）
- 时长分段：bins=[0, 900, 1800, 2700, 3600, inf]（秒），labels=['<15分钟', '15-30分钟', '30-45分钟', '45-60分钟', '>60分钟']
- 时间单位转换：秒 → 分钟（除以60）

#### `compute_transport_mode_stats()`

```python
def compute_transport_mode_stats(
    df_od: pd.DataFrame,
    value_col: str = '人数',
) -> dict:
    """
    计算5种交通方式的全局加权占比。

    Args:
        df_od:     完整OD DataFrame，含交通方式比例列
        value_col: 人数列名

    Returns:
        dict: {
            '驾车': float,  # 加权占比（0-1）
            '地铁': float,
            '公交': float,
            '骑行': float,
            '步行': float,
        }
    """
```

**实现要点**:
- 列名映射：驾车比例→驾车, 地铁比例→地铁, 公交比例→公交, 骑行比例→骑行, 步行比例→步行
- 加权计算：`(df[mode_col] * df[value_col]).sum() / df[value_col].sum()`

#### `compute_street_balance_ratio()`

```python
def compute_street_balance_ratio(
    static_csv_path: Path,
    fence: gpd.GeoDataFrame,
    street_shp_path: Path,
) -> gpd.GeoDataFrame:
    """
    计算街道级职住平衡度。

    Args:
        static_csv_path: TAZ静态数据CSV路径（含taz, 人口类型, 人数列）
        fence:           TAZ边界GeoDataFrame
        street_shp_path: 街道边界SHP路径

    Returns:
        GeoDataFrame: 街道级，含 '居住人数', '工作人数', '平衡度' 列
    """
```

**实现要点**:
- 与 `compute_street_self_sufficiency()` 逻辑类似
- TAZ中心点空间关联到街道（sjoin）
- 按街道聚合居住人数（home）和工作人数（work）
- 街道平衡度 = 工作人数 / 居住人数

### 2. `src/visualization.py`

#### `create_pie_chart()`

```python
def create_pie_chart(
    data_dict: dict,
    output_path: Path,
    title: str = '',
    colors: list = None,
) -> None:
    """
    绘制饼图（时长区间占比、交通方式占比）。

    Args:
        data_dict:   {标签: 数值} 字典
        output_path: 输出PNG路径
        title:       图标题
        colors:      颜色列表，None时使用默认配色
    """
```

**实现要点**:
- 中文标签 + 百分比标注
- 字体：SimHei
- 输出：300 DPI

#### `create_blank_taz_map()`

```python
def create_blank_taz_map(
    fence: gpd.GeoDataFrame,
    output_path: Path,
) -> None:
    """
    绘制空白TAZ底图（无数据设色）。

    Args:
        fence:       TAZ边界GeoDataFrame
        output_path: 输出PNG路径
    """
```

**实现要点**:
- 只显示边界线（灰色）
- 包含指北针和比例尺
- 无数据设色

#### `create_od_flowmap_tbd()`

```python
def create_od_flowmap_tbd(
    df_od: pd.DataFrame,
    fence: gpd.GeoDataFrame,
    output_path: Path,
    mapbox_token: str,
    bounds: list,
    zoom: int = 14,
    style: int = 6,
    top_n: int = 500,
) -> None:
    """
    使用transbigdata绘制交互式OD流线图，输出HTML和PNG。

    Args:
        df_od:         OD DataFrame（含o, d, 人数列）
        fence:         TAZ边界GeoDataFrame（含center_x, center_y）
        output_path:   输出路径（.html），同时生成同名.png
        mapbox_token:  Mapbox访问令牌
        bounds:        地图范围 [lon_min, lat_min, lon_max, lat_max]
        zoom:          地图缩放级别
        style:         transbigdata地图样式编号
        top_n:         显示流量最大的前N条OD对
    """
```

**实现要点**:
- 使用 `transbigdata` 库
- 按人数降序取前top_n条OD对
- 合并TAZ中心坐标（起终点经纬度）
- 输出HTML交互式地图
- 调用 `html_to_png()` 转换为PNG

#### `html_to_png()`

```python
def html_to_png(
    html_path: Path,
    png_path: Path,
    width: int = 1920,
    height: int = 1080,
    wait_seconds: int = 3,
) -> None:
    """
    将HTML文件截图转为PNG（使用playwright）。

    Args:
        html_path:    HTML文件路径
        png_path:     输出PNG路径
        width:        截图宽度（像素）
        height:       截图高度（像素）
        wait_seconds: 等待页面加载的秒数
    """
```

**实现要点**:
- 使用 `playwright` 库（`pip install playwright && playwright install chromium`）
- 同步API：`sync_playwright()`
- 等待页面加载完成后截图

### 3. `src/geo_excu.py`

#### `plot_std_ellipse_flow()`

```python
def plot_std_ellipse_flow(
    df_od: pd.DataFrame,
    fence: gpd.GeoDataFrame,
    output_path: Path,
    o_col: str = 'o',
    d_col: str = 'd',
    value_col: str = '人数',
) -> None:
    """
    基于OD流绘制标准差椭圆（以OD对中点为坐标，人数为权重）。

    Args:
        df_od:       OD DataFrame
        fence:       TAZ边界GeoDataFrame（含taz, center_x, center_y）
        output_path: 输出PNG路径
        o_col:       起点列名
        d_col:       终点列名
        value_col:   权重列名（人数）
    """
```

**实现要点**:
- 合并起终点坐标
- 计算OD对中点坐标：`mid_x = (o_x + d_x) / 2`
- 以人数为权重计算标准差椭圆
- 叠加在TAZ底图上

#### `community_detection_tbd()`

```python
def community_detection_tbd(
    df_od: pd.DataFrame,
    fence: gpd.GeoDataFrame,
    output_path: Path,
    mapbox_token: str,
    bounds: list,
    zoom: int = 14,
    style: int = 6,
    o_col: str = 'o',
    d_col: str = 'd',
    value_col: str = '人数',
) -> dict:
    """
    使用igraph Louvain算法进行TAZ社区发现，输出HTML可视化和模块度报告。

    Args:
        df_od:        OD DataFrame
        fence:        TAZ边界GeoDataFrame
        output_path:  输出路径（.html），同时生成同名.png和_模块度报告.txt
        mapbox_token: Mapbox访问令牌
        bounds:       地图范围
        zoom:         地图缩放级别
        style:        地图样式编号
        o_col:        起点列名
        d_col:        终点列名
        value_col:    边权重列名（人数）

    Returns:
        dict: {'modularity': float, 'n_communities': int, 'community_sizes': list}
    """
```

**实现要点**:
- 使用 `igraph` 库构建有向图
- 添加边权重（人数）
- `g.community_multilevel(weights=edge_weights)` 执行Louvain社区检测
- 报告模块度 `g_clustered.modularity`
- 用 `transbigdata` 绘制底图，社区用不同颜色标注TAZ
- 输出HTML + PNG + TXT报告

---

## evaluation.ipynb 更新规范

### 新增评估函数

```python
def eval_M9_V9_time_distribution(df_od_full, fence, output_section, save_fig=True):
    """M9: 通勤时间指标 + V9: 时间分布图（TAZ地图 + 饼图）"""

def eval_M10_V10_transport_mode(df_od_full, output_section, save_fig=True):
    """M10: 交通方式统计 + V10: 交通方式饼图"""

def eval_V11_od_flowmap(df_od_full, fence, output_section, mapbox_token, bounds, save_fig=True):
    """V11: OD流线图（transbigdata交互式）"""

def eval_V12_community_detection(df_od_full, fence, output_section, mapbox_token, bounds, save_fig=True):
    """V12: 社区发现（igraph Louvain）"""

def eval_V13_std_ellipse_flow(df_od_full, fence, output_section, save_fig=True):
    """V13: 基于OD流的标准差椭圆"""
```

### 更新 EVAL_REGISTRY

```python
EVAL_REGISTRY = {
    # 已有...
    "M9_V9_time_distribution":   eval_M9_V9_time_distribution,
    "M10_V10_transport_mode":    eval_M10_V10_transport_mode,
    "V11_od_flowmap":            eval_V11_od_flowmap,
    "V12_community_detection":   eval_V12_community_detection,
    "V13_std_ellipse_flow":      eval_V13_std_ellipse_flow,
}
```

### 新增 EVAL_CONFIGS 配置

```python
EVAL_CONFIGS = {
    # 已有...
    "dynamic_behavior": [
        "M9_V9_time_distribution",
        "M10_V10_transport_mode",
        "V11_od_flowmap",
        "V12_community_detection",
        "V13_std_ellipse_flow",
    ],
}
```

### run_evaluation() 新增参数

```python
def run_evaluation(
    ...,
    df_od_full=None,       # 完整OD数据（含时间、交通方式）
    mapbox_token=None,     # Mapbox令牌
    bounds=None,           # 地图范围
    ...
):
```

---

## 主流程集成（01_main_pipeline.ipynb）

在 `3.1.2Dynamic_Stats` 节添加：

```python
# 加载完整OD数据
OD_FEATURE_CSV = project_root / 'data' / '[主城区]TAZ4-od.csv'
df_od_full = pd.read_csv(OD_FEATURE_CSV, encoding='utf-8-sig')
df_od_full = df_od_full.rename(columns={'Htaz': 'o', 'Jtaz': 'd'})

import os
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")
if not MAPBOX_TOKEN:
    raise RuntimeError("MAPBOX_TOKEN is not set")
BOUNDS = [112.68, 27.8, 113.3, 28.6]

run_evaluation(
    fence=fence,
    output_section='3.Situation_Diagnosis/3.1Holistic_Diagnosis/3.1.2Dynamic_Stats',
    df_actual=df_actual,
    df_od_full=df_od_full,
    config_name='dynamic_behavior',
    mapbox_token=MAPBOX_TOKEN,
    bounds=BOUNDS,
)
```

---

## 依赖安装

```bash
pip install transbigdata igraph seaborn playwright
playwright install chromium
```

---

## 验证清单

- [ ] `star_平均通勤时间分布图_TAZ.png` 存在，TAZ级时间地图清晰
- [ ] `star_通勤时长区间占比_饼图.png` 存在，5个时段占比合计100%
- [ ] `star_交通方式占比_饼图.png` 存在，5种方式占比合计100%
- [ ] `star_OD流线图_实际格局.html` 可交互，`.png` 静态图清晰
- [ ] `star_社区发现结果.html` 可交互，`.png` 静态图清晰
- [ ] `star_社区发现_模块度报告.txt` 包含模块度数值和社区数
- [ ] `star_动态行为指标汇总.csv` 包含时间和交通方式统计
- [ ] `star_标准差椭圆_通勤流.png` 存在，椭圆基于OD流中点
