"""
通勤研究项目 - src 包

顶层只暴露配置常量和核心工具，其余函数在 notebook 中按模块按需导入：
    from src.data_prep import matrix_to_df, prob_to_int
    from src.models_pattern import compute_wilson, compute_kl_divergence
    from src.metrics_eval import (
        compute_taz_indicators, compute_diff,
        pattern_static_stats, pattern_flow_stats, compute_kl,
        compute_balance_ratio, compute_street_self_sufficiency, compute_excess_commute,
    )
    from src.visualization import (
        create_choropleth_map, create_diverging_map,
        create_flowline, create_distance_pdf, create_distribution_plot,
        create_street_choropleth,
    )
    from src.geo_excu import compute_std_ellipse, plot_std_ellipse
    from src.elasticity import run_full_elasticity_analysis
    from src.utils import write_run_log
"""

__version__ = "0.1.0"

# 配置常量与路径函数
from .config import (
    PROJECT_ROOT, DATA_DIR, RESULTS_DIR,
    STATIC_CSV, DISTANCE_CSV, OD_CSV, OD_FEATURE_CSV, SHP_PATH,
    POP_RESIDENTIAL_CSV, POP_WORK_CSV,
    GRID_TAZ_MAPPING_JSON,
    WILSON_DEFAULT_BETA, WILSON_MAX_ITER, WILSON_TOL,
    VISUAL_CONFIG, MAP_ELEMENTS, COLOR_SCHEMES,
    CRS_WGS84, CRS_UTM,
    get_result_path,
)

# 核心工具（全局常用）
from .utils import (
    StatsCollector,
    validate_od_consistency,
    save_matrix,
    load_matrix,
    save_json,
    load_json,
    logger,
)

__all__ = [
    # 配置
    'PROJECT_ROOT', 'DATA_DIR', 'RESULTS_DIR',
    'STATIC_CSV', 'DISTANCE_CSV', 'OD_CSV', 'OD_FEATURE_CSV', 'SHP_PATH',
    'POP_RESIDENTIAL_CSV', 'POP_WORK_CSV',
    'GRID_TAZ_MAPPING_JSON',
    'WILSON_DEFAULT_BETA', 'WILSON_MAX_ITER', 'WILSON_TOL',
    'VISUAL_CONFIG', 'MAP_ELEMENTS', 'COLOR_SCHEMES',
    'CRS_WGS84', 'CRS_UTM',
    'get_result_path',
    # 工具
    'StatsCollector', 'validate_od_consistency',
    'save_matrix', 'load_matrix', 'save_json', 'load_json', 'logger',
]
