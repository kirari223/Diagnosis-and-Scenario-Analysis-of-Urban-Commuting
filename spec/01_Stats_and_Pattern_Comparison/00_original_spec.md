我需要完成格局对比的实证统计部分。要对实际格局、理想格局（Theoretical_Pattern）、基线格局（Baseline_Pattern）分别进行各自格局的实证统计（静态OD端统计和动态T统计）、各自格局的实证出图（静态OD端出图和动态T出图）；再对实际格局-理想格局，实际格局-基线格局做差，也输出统计数值结果和图。
现在需要①修改对应的函数和pipeline以及依附的_init_、config等文件。②输出统计信息、图表等作为论文结果。③对应输出日志（要有时间戳）、操作doc、结论doc（对输出的结果进行分析）。

输入文件:
- ""E:\00_Commute_Scenario_Research\results\2.Pattern_Computation\2.1Theoretical_Pattern\理想格局-统一结构.csv""（理想格局，已经关联了距离列，知道每个Od对之间的距离是多少）
-""E:\00_Commute_Scenario_Research\results\1.Data_Preprocess\实际格局-统一结构.csv""（实际格局，已经关联了距离列，知道每个Od对之间的距离是多少）
"E:\00_Commute_Scenario_Research\results\2.Pattern_Computation\2.2Baseline_Pattern\基线格局-od-距离已补全.csv"（基准格局，已经关联了距离列，知道每个Od对之间的距离是多少）
E:\00_Commute_Scenario_Research\data\TAZ4_shapefile4326.shp（地理围栏的shp）

参考代码及对应修改函数：
1.完成整数化，调整data_prep.py中的prob_to_int函数。参照代码"F:\02_250910_Commute\12-gvc\0301格局对比\od_process_step1.py"和F:\02_250910_Commute\12-gvc\0301格局对比\od_process_step2a.py，第一步先对基准格局进行截尾，第二步再进行四舍五入。
2.基本统计信息
2.1修改metrics_eval.py中的compute_diff函数（计算差值）、pattern_statistics函数（表明静态格局的统计信息）、compute_diff_statistics函数（表明格局之间差异的统计信息）
参照F:\02_250910_Commute\12-gvc\格局对比\OD_statistics_only.ipynb做统计信息详细版，参照F:\02_250910_Commute\12-gvc\格局对比\OD_visualization_modified.ipynb做统计信息的简明版，并参照F:\02_250910_Commute\07-相互作用模型\[都市区]TAZ4\OD解析.ipynb做变异系数、四分位数等。注意对距离的比较需要关联通勤距离矩阵，详情从代码中学习（可能需要对应修改data_prep.py中的distance_combine函数）。
2.2在metrics_rval.py中新建compute_kl函数，计算实际/基准/理想格局（理想格局、极限格局都指的同一个东西）之间的KL散度，注意联网搜索检查KL散度是用整数计算还是概率值计算，需要慎重检查kl散度计算是否符合一般交通/通勤类论文的要求
3.进行统计信息与空间单元shp的关联，参照现有spatial_combine函数的逻辑，在需要可视化之前关联taz，视情况看是否优化函数，在流表示时可能要计算taz的中心点坐标
4.可视化：注意比例尺、字体等要够大，不合适的话可以去修改config对应的出图基本参数，或修改，比例尺的相关修改可能不准确，就请联网搜索比例尺的参数调整方法。add_north_arrow、add_scale函数以满足要求。背景不要出现经纬度网格。所有图要成一整套看起来风格统一，颜色就沿用固定的组合，整体颜色使用不要太花哨。
4.1修改visualization.py中的create_choropleth_map函数，参照：F:\02_250910_Commute\06-态势描述指标\305-TAZ4现状诊断\0226final\0226final_可视化.py
4.2在visualization.py中新增create_flowline函数，参照F:\02_250910_Commute\12-gvc\格局对比\OD_visualization_flowlines.ipynb
4.3修改visualization.py中的create_diverging_map函数，参照F:\02_250910_Commute\12-gvc\格局对比\0320_matrixAssessment_try\0320_格局对比分析try.ipynb，确保能正常运行并将两个格局的静态差异可视化。但是颜色还是使用config中的。
4.4描述性统计的图示，在visualization.py中新增create_stats_plot函数（可能新增不止这一个）
参照F:\02_250910_Commute\07-相互作用模型\[都市区]TAZ4\OD解析.ipynb，画距离衰减的pdf图
在visualization中新增create_cloud函数
可以参照"F:\03_20250917_participationPHASE3\03-新出图修改0314\0314专业背景对比.R"，直接用R语言画，将两个格局之间人数聚集水平、距离分布两张图分别绘制，无需画散点。这里使用R语言，请你找到跟享有项目自洽的方式。

main_pipeline中的调用及结果输出：
1.在3.Situation_Diagnosis/3.1Basic_Stats中，对实际格局、理想格局（Theoretical_Pattern）、基线格局（Baseline_Pattern）分别进行各自格局的实证统计（静态OD端统计和动态T统计）、各自格局的实证出图（静态OD端出图和动态T出图），输出到results对应名称的子文件夹中
2.在3.Situation_Diagnosis/3.4Pattern_Comparison中,再对实际格局-理想格局，实际格局-基线格局做差，也输出统计数值结果和图，输出到results对应名称的子文件夹中。

关于函数修改
1.当前被修改的函数可能会对其他函数有依赖，如create_choropleth_map需要画指北针、比例尺，就要调用add_north_arrow、add_scale函数；如create_cloud在可视化两格局对比前可能会进行相应数据预处理，视复用情况在main_pipeline写数据预处理代码，或者在utils.py新建函数。在修改一个函数时如有需要，就对其依赖函数进行优化。
2.目前说明中的修改函数不是固定的，可以根据实际情况多拆分函数出来保证效果。
3.一个函数可能在多个地方复用，因此要保证其可复用性，比如基本统计信息pattern_statistics函数（表明静态格局的统计信息）在对多个格局进行描述性统计分析时、在对最终情景分析结果描述中都会用到。比如create_flowline会在单一格局的图示中用到，也会和compute_diff函数结合后在对比两个格局流量差值时、在后续TAZ单元指标可视化表示也会用到。
4.预估复用程度比较低，如特定步骤的前置处理，在utils.py中新建工具函数

流程要求
需要保证整体流程能够跑通，并用pipeline输出正确的格局。请你再pipeline调用时依据实际状况区分pipeline的一级标题、新增二级标题等，用英文描述当前的步骤作为小标题。有了对应的小标题，就在results的对应子文件夹中输出结果。

