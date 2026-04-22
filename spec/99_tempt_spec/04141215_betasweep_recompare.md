# 格局重扫参与统计信息重输出

## 任务目标
用wilson最大熵模型重新输出两个格局（基准格局+随机格局），然后用现有pipeline中的## 3.1_Basic_Stats — Pattern Statistics和## 3.4_Pattern_Comparison — Diff Statistics）输出对四个格局（实际、理想、基线整数化后、随机整数化后）分别计算静态OD端统计和动态T统计，并对四对差值（实际-理想、实际-基线、基线-理想、实际-随机）计算差值统计和KL散度。所有统计结果保存为CSV，供论文引用和阶段3可视化使用。

## 动作一：wilson重扫参
### 1.1 输入数据预处理
运用data_prep.py中的df_to_matrix函数，将原数据转化为wilson最大熵模型可以使用的O\D\C\T矩阵
输入../../data/[主城区]TAZ4-od聚合.csv，转化为T矩阵
输入E:\00_Commute_Scenario_Research\data\[主城区]TAZ4-static.csv转为0\D矩阵
输入E:\00_Commute_Scenario_Research\data\[主城区]TAZ4距离-完整版.csv转为T矩阵
在main_pipeline.ipynb调用，输出存到对应的结果文件夹——
 1. Data_Preprocess
  读取原始数据，转换为矩阵格式
完成转换，转换完后需要检查最终的TAZ编号、矩阵行列数是否正确，TAZ编号是0-2426，应有2427行/列

# 2.运行与检查wilson最大熵模型计算代码
采用models_pattern.py中的compute_wilson函数和calibrate_beta函数重新扫参，输出两个格局：①基线格局，当输出的全局平均通勤距离与实际平均通勤距离（5577.58m）相等时，标定完成；②随机格局，当β=0时输出的通勤格局

在main_pipeline.ipynb调用两个wilson模型计算函数，并输出到对应结果文件夹
2. Pattern_Computation
运行，## 2.2Baseline_Pattern，## 2.3 Random_pattern

迭代次数不宜过多，50次左右即可
需要检查最终的TAZ编号、矩阵行列数是否正确，TAZ编号是0-2426，应有2427行/列，根据输出结果看相应代码是否优化


## 动作二：重新计算统计信息并输出结果
### 2.1将输出的基线格局、随机格局结果整数化
将上述步骤输出的基线格局和随机格局结果导入，分别在主流程的## 2.4_Prob_to_Int — Baseline Pattern Integerization，## 2.5_Prob_to_Int — Random Pattern Integerization运行，输出整数化结果在对应文件夹

### 2.2输出四个格局本身的统计信息和做差的统计信息
输入以下格局和基线格局、随机格局计算统计信息，
results/1.Data_Preprocess/实际格局-统一结构.csv
results/2.Pattern_Computation/2.1Theoretical_Pattern/理想格局-统一结构-0414.csv
data/TAZ4_shapefile4326.shp

调用主流程中## 3.1_Basic_Stats — Pattern Statistics计算各格局本身的统计信息，注意此时新增了一个格局
调用主流程中## 3.4_Pattern_Comparison — Diff Statistics计算四个格局做差的对比统计信息

实际运行时请输出到正确文件夹，并写日志。做结果分析和技术记录，分别到E:\00_Commute_Scenario_Research\docs\Result_Analysis.md和E:\00_Commute_Scenario_Research\docs\Technical_Record.md，每次结果分析和技术记录的时间戳要与日志中的记录一一对应。