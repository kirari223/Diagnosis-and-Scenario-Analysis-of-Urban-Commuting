# 评估模块总体规划

## 1. 模块概述

### 1.1 目标
构建三层次评估体系，对通勤格局进行全面诊断：
- **静态结构层**：职住分布特征（人数、平衡度、自给度）
- **优化潜力层**：格局对比评估（超额通勤、格局差异）
- **动态行为层**：通勤态势（时间、空间、交通方式）

### 1.2 输入数据
- 实际格局：`results/1.Data_Preprocess/实际格局-统一结构.csv`
- 理想格局：`results/2.Pattern_Computation/2.1Theoretical_Pattern/理想格局-统一结构-0414.csv`
- 基准格局：`results/2.Pattern_Computation/2.4Baseline_Int/star_baseline_int.csv`
- 随机格局：`results/2.Pattern_Computation/2.5Random_Int/star_random_int.csv`
- TAZ边界：`data/TAZ4_shapefile4326.shp`
- 街道边界：`F:\02_250910_Commute\260210-jd-taz4-share\都市区街道边界-订正后.shp`
- OD详细数据：`data/[主城区]TAZ4-od.csv`（含时间、交通方式）
- 静态分布：`data/[主城区]TAZ4-static.csv`

### 1.3 输出结构
```
results/3.Situation_Diagnosis/3.1Holistic_Diagnosis/
├── 3.1.1Static_Stats/              # 静态结构层
│   ├── star_人数分布_O端.png
│   ├── star_人数分布_D端.png
│   ├── star_平衡度分布图.png
│   ├── star_自给度分布图_街道.png
│   ├── star_静态结构指标汇总.csv
│   └── 标准差椭圆_O端_D端.png
├── 3.1.2Dynamic_Stats/              # 动态行为层
│   ├── star_平均通勤距离分布图.png
│   ├── star_通勤距离pdf.png
│   ├── star_通勤时长区间占比.png
│   ├── star_交通方式占比.png
│   ├── star_动态行为指标汇总.csv
│   ├── OD流线图.html
│   ├── 社区发现结果.html
│   └── 标准差椭圆_通勤流.png
└── 3.1.3Pattern_Comparison/         # 优化潜力层
    ├── star_超额通勤指标.csv
    ├── star_格局对比_人流箱线图_实际vs理想.png
    ├── star_格局对比_人流箱线图_实际vs基准.png
    ├── star_格局对比_人流箱线图_实际vs随机.png
    ├── star_格局对比_距离pdf_实际vs理想.png
    ├── star_格局对比_距离pdf_实际vs基准.png
    ├── star_格局对比_距离pdf_实际vs随机.png
    ├── star_静态分布人数差_实际vs理想_O端.png
    ├── star_静态分布人数差_实际vs理想_D端.png
    ├── star_静态分布人数差_实际vs基准_O端.png
    ├── star_静态分布人数差_实际vs基准_D端.png
    ├── star_静态分布人数差_实际vs随机_O端.png
    ├── star_静态分布人数差_实际vs随机_D端.png
    ├── OD流量差_实际vs理想.html
    ├── OD流量差_实际vs基准.html
    └── OD流量差_实际vs随机.html
```

---

## 2. 技术实现路线

### 2.1 已有函数复用
| 指标/可视化 | 已有函数 | 位置 |
|------------|---------|------|
| 人数变异系数 | `pattern_static_stats()` | `metrics_eval.py` |
| 平均分布人数 | `pattern_static_stats()` | `metrics_eval.py` |
| 平衡度 | `compute_taz_indicators()` | `metrics_eval.py` |
| 平均通勤距离 | `compute_taz_indicators()` | `metrics_eval.py` |
| 通勤距离变异系数 | `pattern_flow_stats()` | `metrics_eval.py` |
| KL散度 | `compute_kl()` | `metrics_eval.py` |
| 人数分布图 | `create_choropleth_map()` | `visualization.py` |
| 平衡度图 | `create_choropleth_map()` | `visualization.py` |
| 平均通勤距离图 | `create_choropleth_map()` | `visualization.py` |
| 静态分布人数差图 | `create_diff_maps()` | `visualization.py` |
| 通勤距离pdf | `create_distance_pdf()` | `visualization.py` |
| 人流箱线图 | `create_distribution_plot()` | `visualization.py` |

### 2.2 新增函数需求
| 函数名 | 功能 | 输出 | 文件位置 |
|-------|------|------|---------|
| `compute_street_self_sufficiency()` | 计算街道级自给度 | GeoDataFrame | `src/metrics_eval.py` |
| `compute_excess_commute_indicators()` | 计算超额通勤指标 | dict | `src/metrics_eval.py` |
| `compute_std_ellipse()` | 计算标准差椭圆 | dict | `src/geo_excu.py` |
| `plot_std_ellipse()` | 绘制标准差椭圆 | PNG | `src/geo_excu.py` |
| `create_od_flowmap()` | 创建OD流线图（基于transbigdata或folium） | HTML | `src/visualization.py` |
| `create_pie_chart()` | 创建饼图（时长/交通方式占比） | PNG | `src/visualization.py` |
| `compute_time_indicators()` | 计算时间指标（TAZ/全局平均时长） | DataFrame | `src/metrics_eval.py` |
| `compute_transport_mode_stats()` | 计算交通方式统计 | dict | `src/metrics_eval.py` |

### 2.3 依赖安装
```bash
# 需要安装的包
pip install transbigdata  # OD流线图、社区发现
pip install folium        # 备选：交互式地图
pip install keplergl      # 备选：高级OD可视化
```

---

## 3. 实施步骤

### Phase 1: 规划与文档（当前阶段）
- [x] 读取评估体系Excel
- [x] 探索现有代码和数据
- [x] 制定总体规划
- [ ] 补充LaTeX公式到评估体系说明文档

### Phase 2: 新函数开发
- [ ] 实现`src/geo_excu.py`：标准差椭圆函数
- [ ] 实现`src/metrics_eval.py`：街道自给度、超额通勤、时间指标、交通方式统计
- [ ] 实现`src/visualization.py`：OD流线图、饼图

### Phase 3: 函数测试
- [ ] 在`tempt/`中测试标准差椭圆
- [ ] 在`tempt/`中测试OD流线图（transbigdata）
- [ ] 在`tempt/`中测试社区发现
- [ ] 在`tempt/`中测试新增指标计算

### Phase 4: 主流程集成
- [ ] 运行静态结构层（3.1.1Static_Stats）
- [ ] 运行优化潜力层（3.1.3Pattern_Comparison）
- [ ] 验证输出文件完整性和正确性
- [ ] 更新`notebooks/01_main_pipeline.ipynb`

### Phase 5: 文档更新
- [ ] 更新`docs/Result_Analysis.md`（结果解读）
- [ ] 更新`docs/Technical_Record.md`（方法说明）
- [ ] 生成执行日志到`log/`

---

## 4. 关键技术点

### 4.1 街道级自给度计算
**方法**：
1. 将TAZ中心点空间关联到街道边界
2. 按街道聚合通勤流：内部流（o==d且同街道）/ 总流（以该街道为O或D）
3. 输出街道级GeoDataFrame

**参考**：
```python
# 内部通勤人数
internal = df_od[df_od[o_col] == df_od[d_col]].groupby(o_col)[value_col].sum()
```

### 4.2 超额通勤指标
**公式**：
- $C_{min}$ = 1.12 km（理想格局）
- $C_{ran}$ = 13.65 km（随机格局）
- $C_{obs}$ = 实际格局平均通勤距离
- $EC = \frac{C_{obs} - C_{min}}{C_{obs}} \times 100$
- $NEC = \frac{C_{obs} - C_{min}}{C_{ran} - C_{min}} \times 100$
- $CE = \frac{C_{ran} - C_{obs}}{C_{ran}} \times 100$
- $NCE = \frac{C_{ran} - C_{obs}}{C_{ran} - C_{min}} \times 100$

### 4.3 标准差椭圆
**输入**：TAZ中心点坐标 + 人数权重
**输出**：椭圆中心、长短轴、旋转角度
**参考代码**：`F:\02_250910_Commute\98-地理处理参照方法\ty.ipynb`

### 4.4 OD流线图
**方案A（推荐）**：使用`transbigdata.visualization_od()`
- 优点：内置keplergl，交互性强
- 缺点：需要mapbox token

**方案B（备选）**：使用`folium`手动绘制
- 优点：无需token
- 缺点：大数据量性能差

**注意**：用户需提供mapbox token或使用本地底图

### 4.5 社区发现
**方法**：使用`transbigdata`的社区发现功能
**参考**：https://transbigdata.readthedocs.io/zh-cn/latest/gallery/Example%208-Community%20detection%20for%20bikesharing%20data.html

---

## 5. 数据质量检查

### 5.1 必须验证
- [ ] 四个格局的行列数一致
- [ ] 索引对齐（o/d列值范围相同）
- [ ] 人数总量匹配
- [ ] 距离列无缺失值

### 5.2 输出检查
- [ ] CSV编码为utf-8-sig
- [ ] 数值列无科学计数法
- [ ] 地图包含指北针、比例尺、色标
- [ ] 图表标题、轴标签为中文

---

## 6. 风险点与应对

| 风险 | 应对措施 |
|------|---------|
| transbigdata安装失败 | 使用folium备选方案 |
| mapbox token缺失 | 提醒用户提供或使用静态底图 |
| 街道边界文件缺失 | 提醒用户提供或跳过街道级分析 |
| OD详细数据时间列缺失 | 跳过时间相关指标 |
| 内存不足（508MB OD数据） | 分块读取或筛选非空行 |

---

## 7. 下一步行动

1. **立即执行**：补充LaTeX公式到评估体系说明文档
2. **询问用户**：
   - 是否有mapbox token？
   - 街道边界文件路径是否正确？
   - 是否需要社区发现功能（需安装transbigdata）？
3. **开始开发**：实现`src/geo_excu.py`中的标准差椭圆函数
