"""
项目配置文件
集中管理所有路径和常量
"""
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(r"E:\00_Commute_Scenario_Research")

# 数据目录（扁平结构，原始数据直接存放在 data/ 下）
DATA_DIR = PROJECT_ROOT / "data"

# 结果目录（与 main_pipeline 章节标题严格对应）
RESULTS_DIR = PROJECT_ROOT / "results"

# 原始数据文件
STATIC_CSV          = DATA_DIR / "[主城区]TAZ4-static.csv"
DISTANCE_CSV        = DATA_DIR / "[主城区]TAZ4距离-完整版.csv"
OD_CSV              = DATA_DIR / "[主城区]TAZ4-od聚合.csv"
OD_FEATURE_CSV      = DATA_DIR / "[主城区]TAZ4-od.csv"
SHP_PATH            = DATA_DIR / "TAZ4_shapefile4326.shp"
POP_RESIDENTIAL_CSV = DATA_DIR / "1.人口分布-居住人口-100m.csv"
POP_WORK_CSV        = DATA_DIR / "1.人口分布-工作人口-100m.csv"

# 网格-TAZ 映射文件（存放在 data/ 根目录）
GRID_TAZ_MAPPING_JSON = DATA_DIR / "[主城区]原始网格-TAZ4-mapping.json"


def get_result_path(section: str, filename: str) -> Path:
    """
    获取 results/ 下对应章节的文件路径，自动创建目录。

    Args:
        section: pipeline 章节名，与 main_pipeline 小标题对应，
                 如 '1.Data_Preprocess'、'2.3_Prob_to_Int'
        filename: 文件名，论文直引文件加 star_ 前缀

    Returns:
        Path: 完整文件路径

    Examples:
        get_result_path('2.3_Prob_to_Int', 'star_prob_to_int.csv')
        get_result_path('1.Data_Preprocess', 'matrix_data_stats.csv')
    """
    p = RESULTS_DIR / section
    p.mkdir(parents=True, exist_ok=True)
    return p / filename



# 模型参数
WILSON_DEFAULT_BETA = 0.32
WILSON_MAX_ITER = 30
WILSON_TOL = 1e-10

# 可视化参数
VISUAL_CONFIG = {
    'figure_size': (18, 12),
    'dpi': 300,
    'title_fontsize': 18,
    'label_fontsize': 28,
    'legend_fontsize': 24,
    'annotation_fontsize': 20,
}

MAP_ELEMENTS = {
    'scalebar_length': 10000,  # 10km
    'scalebar_x': 0.82,
    'scalebar_y': 0.08,
    'north_arrow_x': 0.92,
    'north_arrow_y': 0.88,
    'north_arrow_size': 0.07,
}

# 配色方案
COLOR_SCHEMES = {
    'avg_distance': {
        'name': '平均通勤距离',
        'colors': ['#EFF7FC', '#D1E7F5', '#A3D2EF', '#75BDE9', '#2E7D9A'],
        'bins': [0, 1, 2, 3, 4, 5],
        'unit': 'km',
        'decimals': 1
    },
    'avg_time': {
        'name': '平均通勤时间',
        'colors': ['#EFF7FC', '#D1E7F5', '#A3D2EF', '#75BDE9', '#2E7D9A'],
        'bins': [0, 15, 30, 45, 60, 120],
        'unit': '分钟',
        'decimals': 1
    },
    'total_people': {
        'name': '总通勤人数',
        'colors': ['#FFF5F0', '#FEE0D2', '#FDC7B3', '#FBB095', '#C65A4A'],
        'bins': [0, 1000, 2000, 3000, 4000, 5000],
        'unit': '人',
        'decimals': 0
    },
    'internal_ratio': {
        'name': '内部通勤比',
        'colors': ['#F0F9F0', '#D4EBD4', '#AED9AE', '#88C688', '#4A8F4A'],
        'bins': [0, 20, 40, 60, 80, 100],
        'unit': '%',
        'decimals': 1
    },
    'diff_distance': {
        'name': '平均通勤距离差值',
        'colors_pos': ['#FFEBEE', '#EF9A9A', '#E53935', '#B71C1C'],
        'colors_neg': ['#1B5E20', '#388E3C', '#81C784', '#E8F5E9'],
        'unit': 'km',
        'decimals': 1
    },
    'diff_people': {
        'name': '总通勤人数差值',
        'colors_pos': ['#FFF3E0', '#FFB74D', '#FF9800', '#E65100'],
        'colors_neg': ['#0D47A1', '#1E88E5', '#90CAF9', '#E3F2FD'],
        'unit': '人',
        'decimals': 0
    },
    'diff_ratio': {
        'name': '内部通勤比差值',
        'colors_pos': ['#FFF3E0', '#FFB74D', '#FF9800', '#E65100'],
        'colors_neg': ['#0D47A1', '#1E88E5', '#90CAF9', '#E3F2FD'],
        'unit': '%',
        'decimals': 1
    },
    'balance_ratio': {
        'name': '职住平衡度',
        'colors': ['#2166AC', '#92C5DE', '#F7F7F7', '#F4A582', '#D6604D'],
        'bins': [0, 0.5, 0.8, 1.2, 2.0, 999.0],
        'unit': '',
        'decimals': 2
    },
    'self_sufficiency': {
        'name': '自给度',
        'colors': ['#F0F9F0', '#D4EBD4', '#AED9AE', '#88C688', '#4A8F4A'],
        'bins': [0, 0.1, 0.2, 0.3, 0.4, 1.0],
        'unit': '',
        'decimals': 2
    },
    'self_sufficiency_density': {
        'name': '自给度密度',
        'colors': ['#F0F9F0', '#D4EBD4', '#AED9AE', '#88C688', '#4A8F4A'],
        'bins': [0, 0.01, 0.02, 0.03, 0.04, 0.1],
        'unit': '1/km²',
        'decimals': 3
    },
    'static_people': {
        'name': '分布人数',
        'colors': ['#FFF5F0', '#FEE0D2', '#FDC7B3', '#FBB095', '#F08070', '#D6604D', '#B22020', '#7F0000'],
        'bins': [0, 500, 1000, 2000, 4000, 8000, 12000, 16000, 20000],
        'unit': '人',
        'decimals': 0
    },
}

# 坐标系统
CRS_WGS84 = "EPSG:4326"
CRS_UTM = "EPSG:32649"  # 根据实际区域调整
