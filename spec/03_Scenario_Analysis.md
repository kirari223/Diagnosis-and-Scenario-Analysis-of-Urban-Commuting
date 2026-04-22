# 任务名称：通勤刚性提取与情景推演
运用实际通勤格局的数据来标定现有通勤刚性，并推演出现有刚性提升20%之后的OD静态分布格局和通勤流格局，与实际格局进行比较。

# 运行步骤
## 步骤一：刚性提取
用全量通勤格局的泊松回归来算OD两端整体的刚性。尤其注意弹性计算时输入的β值单位。
输入实际格局的静态OD分布数据、动态通勤数据
全局O、D两侧刚性值提取结果放在文件夹：E:\00_Commute_Scenario_Research\results\4.Scenario_Analysis\4.2Rigidity_Computation

## 步骤二：情景推演
2.1请运算出现有格局刚性,结果放到E:\00_Commute_Scenario_Research\results\4.Scenario_Analysis\4.2Rigidity_Computation这个文件夹中
2.2刚性提升20%的情景推演：在现有格局提升20%的设定下运行凸优化的情景设定代码，输出刚性提升20%的情景结果，输出放到这个文件夹中E:\00_Commute_Scenario_Research\results\4.Scenario_Analysis\4.3Scenario_Computation
（步骤一、二，刚性提取和情景推演，具体代码生成请参照F:\02_250910_Commute\15-FINAL\0415_弹性计算+情景推演.md）

## 步骤三：结果对比
3.1格局统计信息计算，参照主流程中“3.1 Basic_Stats — Pattern Statistics”调用相同的函数，输出刚性提升20%格局本身的静态统计、动态统计信息，该步骤编排到主流程的4.4.1Scenario_Pattern_Stats部分。结果保存到E:\00_Commute_Scenario_Research\results\4.Scenario_Analysis\4.4Scenario_Compare\4.4.1Scenario_Pattern_Stats
3.2实际格局与情景格局的对比，参照主流程中“3.4 Pattern_Comparison — Diff Statistics”，输出实际格局-情景格局的统计信息，该步骤编排到主流程的“3.4 Pattern_Comparison — Diff Statistics”部分，保存到E:\00_Commute_Scenario_Research\results\4.Scenario_Analysis\4.4Scenario_Compare\4.4.2Scenario_Actual_Compare中
结果对比时会涉及到格式转换，请调用现有data_prep.py中的预处理函数来进行格式转换，如果现有函数有不兼容情景格局输出的情况，就修改优化现有函数。
3.3格局对比可视化
参照E:\00_Commute_Scenario_Research\spec\01_Stats_and_Pattern_Comparison\01_phase3_visualization.md的内容，检查现有的画图src脚本是否能满足可视化需求。
需要输出情景格局本身的静态、动态格局图、PDF图，以及两个格局静态和动态相减的格局对比图、箱线图
图片输出到“E:\00_Commute_Scenario_Research\results\4.Scenario_Analysis\4.4Scenario_Compare\4.4.3Scenario_Compare_Visualize”中

# 输出要求
输出的文件放到main_pipeline对应标题的文件夹之下，保证文件的嵌套关系，如main_pipeline中的一级标题就对应results中的一级子文件夹，主流程的二级标题对应results的二级子文件夹，二级子文件夹都要放在对应的一级子文件夹之下,三级标题同理。

# spec撰写要求
- 情景设定本身也有多个，spec描述时需要考虑对于不同情景参数的适配性。
- 对当前这个文件进行细节补充、逻辑梳理和阶段拆分，生成以该文件命名的文件夹，放入当前文件、润色后的总spec文件，分阶段的各个spec文件

# 函数优化要求
请注意所有的src中的函数都是工具性质，是可调用的即插即用模块，请注意其兼容性不能只适配单一步骤，函数注释中也不要用步骤限定性的描述。同时情景设定本身也有多个，需要考虑对于不同情景参数的适配性。