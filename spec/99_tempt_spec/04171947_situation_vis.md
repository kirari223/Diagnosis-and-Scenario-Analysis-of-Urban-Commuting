# 任务
现在要针对3.1Situation_Diagonosis和3.4Pattern_Comparison进行代码完善并用单图调试其参数，对于每种类型的图抽单个图来做测试。

# 步骤一：补充单格局设色图、格局对比设色图的对应main_pipeline调用部分

1. 对于config、`create_choropleth_map`、`create_diverging_map`函数已经写好，只用填充spec指定的main_pipeline部分，不用修改函数代码本身。
2. 只写出可视化的主流程调用部分，不用修改统计信息输出的部分，前述过程只做参考

## 章节：`3.1Basic_Stats`

注：请在现有的数值计算后面新增单元格以存放对单格局的可视化调用代码

```python
# %% [markdown]
# ## 3.1Basic_Stats

# %%
from src.metrics_eval import pattern_statistics
from src.visualization import create_choropleth_map, create_flowline, create_distance_pdf

# 读取四个格局
df_actual = pd.read_csv(
    RESULTS_DIR / '1.Data_Preprocess/实际格局-统一结构.csv', encoding='utf-8-sig'
)
df_ideal = pd.read_csv(
    RESULTS_DIR / '2.Pattern_Computation/2.1Theoretical_Pattern/理想格局-统一结构-0414.csv',
    encoding='utf-8-sig'
)
df_baseline = pd.read_csv(
    RESULTS_DIR / '2.Pattern_Computation/2.4Baseline_Int/star_baseline_int.csv',
    encoding='utf-8-sig'
)
df_random = pd.read_csv(
    RESULTS_DIR / '2.Pattern_Computation/2.5Random_Int/star_random_int.csv',
    encoding='utf-8-sig'
)

patterns = {
    '实际': df_actual,
    '理想': df_ideal,
    '基线': df_baseline,
    '随机'：df_random,
}

gdf_dict = {}

for name, df in patterns.items():
    print(f"\n{'='*50}")
    print(f"处理格局: {name}")
    output_dir = get_result_path(f'3.Situation_Diagnosis/3.1_Basic_Stats/{name}格局', '').parent
    
    result = pattern_statistics(df, name, output_dir)
    gdf_dict[name] = result['gdf_taz']
    
    # 静态设色图
    for col, config_key, fname in [
        ('总通勤人数', 'total_people', f'star_{name}_map_total_people.png'),
        ('平均通勤距离', 'avg_distance', f'star_{name}_map_avg_distance.png'),
    ]:
        create_choropleth_map(
            gdf_data=gdf_dict[name],
            gdf_base=fence,
            column=col,
            config_key=config_key,
            output_path=get_result_path(f'3.Situation_Diagnosis/3.1_Basic_Stats/{name}格局', fname),
            title=f'{name}格局 - {col}',
        )
    
    # 动态流线图
    top_n = 200 if name == '理想' else 500
    create_flowline(
        df_od=df,
        fence=fence,
        output_path=get_result_path(f'3.Situation_Diagnosis/3.1_Basic_Stats/{name}格局',
                                     f'star_{name}_flowline.png'),
        title=f'{name}格局 OD流线图（前{top_n}条）',
        top_n=top_n,
    )

# 四格局距离PDF对比图（合并在一张）
create_distance_pdf(
    df_list=[df_actual, df_ideal, df_baseline],
    names=['实际格局', '理想格局', '基线格局'，'随机格局'],
    output_path=get_result_path('3.Situation_Diagnosis/3.1_Basic_Stats', 'star_all_distance_pdf.png'),
    title='四格局通勤距离分布对比',
)
```

---

## 章节：`3.4Pattern_Comparison`

```python
# %% [markdown]
# ## 3.4Pattern_Comparison

# %%
from src.metrics_eval import compute_diff, compute_diff_statistics, compute_kl
from src.visualization import create_diverging_map, create_flowline, create_distribution_plot

diff_pairs = [
    ('实际', '理想'),
    ('实际', '基线'),
    ('实际', '随机'),
    ('基线', '理想'),
]

for name_a, name_b in diff_pairs:
    print(f"\n{'='*50}")
    print(f"差值分析: {name_a} - {name_b}")
    
    section = f'3.Situation_Diagnosis/3.4_Pattern_Comparison/{name_a}-{name_b}'
    output_dir = get_result_path(section, '').parent
    
    df_a = patterns[name_a]
    df_b = patterns[name_b]
    gdf_a = gdf_dict[name_a]
    gdf_b = gdf_dict[name_b]
    
    # 差值GeoDataFrame
    gdf_diff = compute_diff(gdf_a, gdf_b, name_a, name_b, fence, output_dir=output_dir)
    
    # 差值统计
    compute_diff_statistics(gdf_diff, name_a, name_b, output_dir=output_dir)
    
    # KL散度
    compute_kl(df_a, df_b, name_a, name_b, output_dir=output_dir)
    
    # 差值设色图（3张）
    for col_base, config_key, fname_suffix in [
        ('总通勤人数', 'diff_people', 'map_people'),
        ('平均通勤距离', 'diff_distance', 'map_distance'),
    ]:
        create_diverging_map(
            gdf_data=gdf_diff,
            gdf_base=fence,
            column=f'{col_base}_diff',
            config_key=config_key,
            output_path=get_result_path(section, f'star_diff_{name_a}_{name_b}_{fname_suffix}.png'),
            title=f'{name_a} - {name_b}: {col_base}差值',
        )
    
    # 差值流线图
    # 需要先计算OD级别差值（不是TAZ级别）
    df_diff_od = pd.merge(
        df_a[['o', 'd', '人数']].rename(columns={'人数': f'人数_{name_a}'}),
        df_b[['o', 'd', '人数']].rename(columns={'人数': f'人数_{name_b}'}),
        on=['o', 'd'], how='outer'
    ).fillna(0)
    df_diff_od['差值'] = df_diff_od[f'人数_{name_a}'] - df_diff_od[f'人数_{name_b}']
    
    create_flowline(
        df_od=df_diff_od,
        fence=fence,
        output_path=get_result_path(section, f'star_diff_{name_a}_{name_b}_flowline.png'),
        title=f'{name_a} - {name_b} 差值流线图（前500条）',
        flow_col='差值',
        top_n=500,
        is_diff=True,
    )
    
# 步骤二：在调试文件中调用函数，每个函数只画出一张图
在E:\00_Commute_Scenario_Research\tempt\0417vis_tempt.ipynb
文件中调用以上的可视化函数，根据其对应的main_pipelien流程来整理得到可视化的数据，但采用MVP原则简化数据输入和输出，不写冗余代码，只作为调试用，目的是观察各个绘图函数的参数设定是否正确

# 原则
对于`create_choropleth_map`、`create_diverging_map`函数，已经写好不需要修改，最多解决变量不承继的问题，而不要进行参数的修改。`create_distance_pdf`函数酌情修改，使得变量连接。
`create_flowline`函数问题最大，需要加粗流线的宽度是使之清晰可分辨，线条宽度根据人数多少来划分，人数多的最宽、人数较少就较窄，线条粗细也要作为图例展示。另外人流量小的OD流线透明度高，人数越多透明度越低，但是线条透明度可以不作为图例。

让0417vis_tempt成为tempt文件下的子文件夹名，输出的调试图片放到这个子文件夹下