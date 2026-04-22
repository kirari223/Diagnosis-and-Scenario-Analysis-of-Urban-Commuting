# 情景设定：WFH居家办公趋势下的通勤情景演变
## 长沙市政策导向：
1. 《长沙市国土空间总体规划（2021-2035）》："15分钟生活圈"建设
- 目标是让居民就地享受高品质生活
- 不是鼓励搬家，而是让人们不必搬家
2. 湖南省新就业形态政策：打破就业地与社保绑定
- 降低的是工作端摩擦
- 对居住端毫无松动作用
3. 长沙"青年友好城市"建设：提供人才公寓、购房补贴
- 这些政策是为了稳定居住，不是促进流动
4. 城市更新行动（《长沙市全面推进城市更新行动方案(2026—2030年)》及前期“十四五”举措）通过老旧小区改造、15分钟生活圈建设，大幅提升了现有居住地的宜居性、配套完善度和居民满意度。享受更新红利的居民，其“留守”意愿和沉没成本感知会增强，而非减弱。
5. 中国二线城市常见的学区、家庭网络、社区嵌入等因素，进一步放大了居住端的路径依赖。数字经济政策（如马栏山、岳麓山大科城）主要利好工作端的灵活匹配（平台化、虚拟协作），而非直接降低搬家门槛。
6. 城市更新与产业结构转型,长沙近年大力发展数字经济、文化创意、人工智能等高科技产业（湘江新区、马栏山视频文创园、岳麓山大学科技城）。这些产业的岗位特征更适合居家办公、混合办公等灵活模式。
**总结**：长沙市的政策导向是稳定居住，降低工作摩擦。

## 情景参数设定
**情景名称**：居住地O端刚性提升20%，工作地D端刚性降低 20%

**参数**：

| 参数 | 值 | 说明 |
|---|---|---|
| `rigidityO_multiplier` | `1.2` | 居住地O端刚性提升 20% |
| `rigidityD_multiplier` | `0.8` | 工作地D端刚性降低 20% |
| `scenario_label` | `'rigidity_WFH'` | 文件命名标识 |

# 任务
根据已经输出的职住两端刚性结果E:\00_Commute_Scenario_Research\results\4.Scenario_Analysis\4.2Rigidity_Computation\star_rigidity_params.csv，在O端刚性提升20%、D端刚性降低20%的设定上做情景推演，输出情景格局、实际与情景格局比较的统计信息，把情景结果本身的静动态情况可视化，且可视化两者的作差情况    

# 运行步骤
1. 输入已有的刚性值结果
E:\00_Commute_Scenario_Research\results\4.Scenario_Analysis\4.2Rigidity_Computation\star_rigidity_params.csv
theta_O是居住端O的刚性参数值，theta_D是工作地D的刚性参数值，注意两者在该csv文件中的结果是由米单位的运算得出的，如果以千米单位进行整体运算需要转换单位对现在的两端theta值都除以1000。
2. 用函数compute_scenario_uot进行格局推演
使用elasticity.py中的compute_scenario_uot函数进行情景推演，但现在该函数只有一个刚性变化系数，需要再增加一个刚性变化系数，以对OD两端进行不同程度的刚性变化模拟。将需要两个刚性变化系数的改动更新到对应的spec中，即E:\00_Commute_Scenario_Research\spec\03_Scenario_Analysis\02_scenario_computation.md。
3. 对计算的格局结果进行整数化
- 运用封装好的整数化函数prob_to_int（来自data_prep.py），并将需要对应整数化步骤补充到spec中，即  E:\00_Commute_Scenario_Research\spec\03_Scenario_Analysis\03_result_comparison.md
- 对情景格局本身、及实际格局与其作差的统计信息输出
    参照以下spec进行——
    E:\00_Commute_Scenario_Research\spec\03_Scenario_Analysis\03_result_comparison.md
4. 可视化
- 参照
    E:\00_Commute_Scenario_Research\spec\03_Scenario_Analysis\04_visualization.md运行
- 补充箱线图和pdf图，分别表示实际格局跟情景格局的人数分布情况对比、实际格局跟情景格局的距离分布情况对比
    箱线图将横轴作为人数，纵轴是两个格局为刻度，也就是说箱线图是横着排的
    参照sns.boxplot画箱线图，字体、颜色等设定沿用整个项目的config
    pdf按照visualization.py中的create_distance_pdf来画
- 格局本身跟格局对比的函数（create_choropleth_map、create_diverging_map）不变。但是一般来说，格局作差的色带应该有负数出现的，色带不应该是全正值，不过也不一定，很小可能下实际格局的所有OD流距离都比情景格局的大，但总之请你帮我检查色带正负这一点。
- 注意可视化的前序步骤要进行，add_scalebar：底层绘图函数。
负责“真正画”比例尺（线段、黑白块、0/10km文字），不关心 CRS，只按传入长度和位置画。
_add_scalebar_auto：上层包装函数。
会先判断 gdf.crs：若是地理坐标（度）就把米转换成度，再调用 add_scalebar；若是投影坐标（米）就直接调用。
也负责把 label_fontsize、right_edge_pos 这些参数传给 add_scalebar。
_prepare_map_for_plot：绘图前的数据准备步骤。
它会把 gdf_data 和 gdf_base 统一到同一个合适的投影 CRS（优先估计 UTM），避免经纬度直接画图带来的比例失真。
是 create_choropleth_map 和 create_diverging_map 的前置步骤。
5. 输出结果
   输出结果到"E:\00_Commute_Scenario_Research\results\4.Scenario_Analysis\4.3Scenario_Computation\rigidity_WFH"
   "E:\00_Commute_Scenario_Research\results\4.Scenario_Analysis\4.4Scenario_Compare\4.4.1Scenario_Pattern_Stats\rigidity_WFH"
   "E:\00_Commute_Scenario_Research\results\4.Scenario_Analysis\4.4Scenario_Compare\4.4.2Scenario_Actual_Compare\rigidity_WFH"
   "E:\00_Commute_Scenario_Research\results\4.Scenario_Analysis\4.4Scenario_Compare\4.4.3Scenario_Compare_Visualize\rigidity_WFH"
   以后每个情景格局的输出都请放到对应的`scenario_label`文件命名标识的子文件夹下，关于情景输出子文件夹名设定的这个信息更新到CLAUDE.md中

# 记录要求
将操作的步骤继续按照Technical_Record编写，每个文档存放一个模块计算的相关技术操作内容，按照这个模块的大致步骤命名文件，即Technical_Record_{mod_step}，这个信息更新到CLAUDE.md中