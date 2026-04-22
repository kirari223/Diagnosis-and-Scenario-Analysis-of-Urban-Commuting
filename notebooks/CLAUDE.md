# 背景说明
- 1. E:\00_Commute_Scenario_Research\notebooks\sub_pipeline中进行函数调用以满足分支任务、不同于主流程步骤，或者已经具备中间结果而输入中间结果无需从头跑主流程的任务情况，可以理解为取主流程的片段流程运行。分支流程的notebooks中小标题的起名跟main_pipeline起名一致，分支流程的输出结果仍然是论文的主体结果，放在results文件对应的小标题之下。
- 2. E:\00_Commute_Scenario_Research\notebooks\02_eda_and_stats.ipynb其中是的函数调用输出次要数据的，但是论文中仍会用这些次要结果

# 要求
除了特别申明的临时需求运行及sub_pipeline之外，对调用函数的流程有改动就要更新到`notebooks/01_main_pipeline.ipynb`该文件中，且按照其步骤规范地放到相应子文件夹之下。
修改调用函数的流程之后，还需要测试是否能输出符合预期的结果。

# 文件存放声明
E:\00_Commute_Scenario_Research\spec\99_ad-hoc_requirements
