"""
工具函数模块
包含日志、文件IO、数据验证等通用功能
"""
import json
import logging
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .config import PROJECT_ROOT

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StatsCollector:
    """统计信息收集器 - 替代print，结构化存储统计信息"""
    
    def __init__(self, name):
        self.name = name
        self.stats = []
        self.current = {}
    
    def add(self, key, value):
        """添加统计项"""
        self.current[key] = value
    
    def add_dict(self, data_dict):
        """批量添加统计项"""
        self.current.update(data_dict)
    
    def save(self, filename=None):
        """保存统计信息到CSV"""
        if not self.current:
            return None

        # 添加时间戳
        self.current['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.current['stat_name'] = self.name

        self.stats.append(self.current.copy())

        # 保存到文件（filename 若为相对路径则写到 results/ 根目录，绝对路径直接写）
        if filename:
            filepath = Path(filename)
            if not filepath.is_absolute():
                filepath = PROJECT_ROOT / 'results' / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            df = pd.DataFrame(self.stats)
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            logger.info(f"统计信息已保存: {filepath}")

        # 清空当前统计
        result = self.current.copy()
        self.current = {}
        return result
    
    def to_dataframe(self):
        """返回统计信息DataFrame"""
        return pd.DataFrame(self.stats)


def save_matrix(matrix, filepath):
    """保存矩阵到文件（支持.npy和.csv格式）"""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    if filepath.suffix == '.npy':
        np.save(filepath, matrix)
    else:
        if isinstance(matrix, np.ndarray):
            pd.DataFrame(matrix).to_csv(filepath, index=False, encoding='utf-8-sig')
        else:
            matrix.to_csv(filepath, index=False, encoding='utf-8-sig')
    logger.info(f"矩阵已保存: {filepath}")


def load_matrix(filepath):
    """从文件加载矩阵"""
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")
    
    if filepath.suffix == '.npy':
        return np.load(filepath)
    else:
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        # 如果只有数值列，转换为numpy数组
        if df.shape[1] > 1 and all(pd.api.types.is_numeric_dtype(df[col]) for col in df.columns):
            return df.values
        return df


def validate_od_consistency(O_list, D_list, T_matrix, tolerance=1e-6):
    """
    验证O/D/T三者一致性
    
    Returns:
        dict: 验证结果
    """
    results = {
        'valid': True,
        'errors': []
    }
    
    # 检查O_list和T矩阵行和
    for i, o in enumerate(O_list):
        if o is not None and not np.isnan(o):
            row_sum = T_matrix[i, :].sum() if i < T_matrix.shape[0] else 0
            if abs(o - row_sum) > tolerance:
                results['valid'] = False
                results['errors'].append(f"O[{i}]: {o} != T行和: {row_sum}")
    
    # 检查D_list和T矩阵列和
    for j, d in enumerate(D_list):
        if d is not None and not np.isnan(d):
            col_sum = T_matrix[:, j].sum() if j < T_matrix.shape[1] else 0
            if abs(d - col_sum) > tolerance:
                results['valid'] = False
                results['errors'].append(f"D[{j}]: {d} != T列和: {col_sum}")
    
    # 检查O总和和D总和
    O_sum = sum(x for x in O_list if x is not None and not np.isnan(x))
    D_sum = sum(x for x in D_list if x is not None and not np.isnan(x))
    T_sum = T_matrix.sum()
    
    results['O_sum'] = O_sum
    results['D_sum'] = D_sum
    results['T_sum'] = T_sum
    results['O_D_diff'] = abs(O_sum - D_sum)
    results['O_T_diff'] = abs(O_sum - T_sum)
    
    if results['O_D_diff'] > tolerance:
        results['valid'] = False
        results['errors'].append(f"O总和({O_sum}) != D总和({D_sum})")
    
    return results


def timer_decorator(func):
    """计时装饰器"""
    def wrapper(*args, **kwargs):
        start = time.time()
        logger.info(f"开始执行: {func.__name__}")
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.info(f"完成: {func.__name__}, 耗时: {elapsed:.2f}秒")
        return result
    return wrapper


def save_json(data, filepath):
    """保存数据到JSON文件"""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # 处理numpy类型
    def convert(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=convert)
    logger.info(f"JSON已保存: {filepath}")


def load_json(filepath):
    """从JSON文件加载数据"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_summary_report(results_dict, output_path):
    """创建汇总报告"""
    lines = []
    lines.append("=" * 80)
    lines.append("通勤研究项目分析汇总报告")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    lines.append("")
    
    for section_name, data in results_dict.items():
        lines.append(f"\n【{section_name}】")
        lines.append("-" * 60)
        if isinstance(data, dict):
            for key, value in data.items():
                lines.append(f"  {key}: {value}")
        elif isinstance(data, list):
            for item in data:
                lines.append(f"  - {item}")
        else:
            lines.append(f"  {data}")
    
    lines.append("\n" + "=" * 80)
    lines.append("报告结束")
    lines.append("=" * 80)
    
    # 保存报告
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    logger.info(f"汇总报告已保存: {output_path}")
    return '\n'.join(lines)


def write_run_log(
    step_name: str,
    inputs: dict,
    outputs: dict,
    notes: str = '',
    log_dir: Path = None,
) -> Path:
    """
    写入运行日志到 log/ 文件夹。

    Args:
        step_name: pipeline 步骤名称（如 '3.1_Basic_Stats'）
        inputs:    输入文件描述字典 {描述: 路径或说明}
        outputs:   输出文件描述字典 {描述: 路径或说明}
        notes:     备注信息
        log_dir:   日志目录，默认为项目根目录下的 log/

    Returns:
        Path: 日志文件路径
    """
    if log_dir is None:
        # 从 config 取项目根目录
        try:
            from .config import PROJECT_ROOT
            log_dir = PROJECT_ROOT / 'log'
        except ImportError:
            log_dir = Path('log')

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = log_dir / f'run_{ts}.md'

    lines = [
        f'# 运行日志：{step_name}',
        f'时间戳：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        '',
        '## 输入',
    ]
    for desc, val in inputs.items():
        lines.append(f'- {desc}：{val}')

    lines += ['', '## 输出']
    for desc, val in outputs.items():
        lines.append(f'- {desc}：{val}')

    if notes:
        lines += ['', '## 备注', notes]

    log_path.write_text('\n'.join(lines), encoding='utf-8')
    logger.info(f"运行日志已保存: {log_path}")
    return log_path
