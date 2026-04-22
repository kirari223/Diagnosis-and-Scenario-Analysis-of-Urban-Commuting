# 通勤态势格局研究

基于 TAZ4 分区尺度的城市通勤格局建模、评估与情景分析项目。

## 项目结构

```
.
├── data/                        # 原始数据（扁平存放，不提交 Git）
│   ├── [主城区]TAZ4-static.csv
│   ├── [主城区]TAZ4距离-完整版.csv
│   ├── [主城区]TAZ4-od.csv
│   ├── [主城区]TAZ4-od聚合.csv
│   ├── TAZ4_shapefile4326.*
│   ├── 1.人口分布-居住人口-100m.csv
│   ├── 1.人口分布-工作人口-100m.csv
│   └── [主城区]原始网格-TAZ4-mapping.json  # 运行时生成
│
├── docs/                        # 论文写作支撑文档
│   ├── Result_Analysis.md       # 结果解读，按 pipeline 小标题累加，可直接引用到论文
│   ├── Technical_Record.md      # 研究方法叙述，含 LaTeX 公式，对应论文方法章节
│   └── 260410_通勤情景分析.pdf  # 论文初稿参考
│
├── log/                         # 运行记录与检验
│   ├── run_YYYYMMDD_HHMMSS.md  # 每次执行的输入/执行/输出梗概
│   └── check_YYYYMMDD.md       # 代码可用性、结果正确性检验记录
│
├── spec/                        # 任务规范与提示词
│   ├── 00_master_spec.md        # 总纲：研究目标、数据说明、分析框架
│   └── 01_xxx_spec.md           # 各步骤细化规范
│
├── notebooks/
│   ├── 01_main_pipeline.ipynb   # 主流程（唯一入口）
│   └── 02_eda_and_stats.ipynb   # 探索性分析（辅助）
│
├── src/                         # 核心模块（提交 Git）
│   ├── config.py                # 路径与参数配置
│   ├── utils.py                 # StatsCollector、验证工具、IO
│   ├── data_prep.py             # 数据清洗、矩阵转换、整数化
│   ├── models_pattern.py        # Wilson 模型、线性规划、KL 散度
│   ├── metrics_eval.py          # TAZ 指标、统计信息、差值分析
│   ├── visualization.py         # 地图制图、图表生成
│   └── elasticity.py            # 弹性计算、分行业分析
│
└── results/                     # 输出结果（与 pipeline 章节严格对应，不提交 Git）
    ├── 1.Data_Preprocess/
    ├── 2.Pattern_Computation/
    │   ├── 2.1_Theoretical_Pattern/
    │   ├── 2.2_Baseline_Pattern/
    │   ├── 2.3_Prob_to_Int/
    │   └── 2.4_Pattern_Comparison/
    ├── 3.Situation_Diagnosis/
    │   ├── 3.1_Basic_Stats/
    │   ├── 3.2_Unit_Indicators/
    │   ├── 3.3_Excess_Indicators/
    │   └── 3.4_Pattern_Comparison/
    └── 4.Scenario_Analysis/
        ├── 4.1_Extract_Ratio/
        ├── 4.2_Rigidity_Computation/
        └── 4.3_Scenario_Computation/
```

## 结果文件命名规范

- 论文直引文件（图表、核心数据表）：文件名加 `star_` 前缀，如 `star_prob_to_int.csv`
- 调试/验证性文件：无前缀，存放在同一章节文件夹内

## 运行方法

```bash
# 安装依赖
pip install -r requirements.txt

# 打开主流程 notebook
jupyter notebook notebooks/01_main_pipeline.ipynb
```

主流程按章节顺序执行，每个章节的输出自动保存到 `results/` 对应子文件夹。

## 分析流程

```
data/ 原始数据
    → 1. 数据准备        O/D/C/T 矩阵构建
    → 2. 格局计算        Wilson 模型 + 整数化 + KL 散度
    → 3. 态势诊断        TAZ 指标 + 分级设色地图
    → 4. 情景分析        弹性提取 + 凸优化情景模拟
```

## 依赖环境

```
pandas >= 2.0
numpy >= 1.24
geopandas >= 0.13
matplotlib >= 3.7
scipy >= 1.10
cvxpy >= 1.3
gurobipy >= 10.0  # 可选，商业求解器
```
