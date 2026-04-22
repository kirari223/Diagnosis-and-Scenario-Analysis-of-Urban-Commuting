"""
弹性分析模块
包含分行业弹性计算、参数扫描等功能
"""
import numpy as np
import pandas as pd

from .config import get_result_path
from .models_pattern import compute_wilson, calibrate_beta, compute_kl_divergence
from .utils import StatsCollector, timer_decorator, logger, save_json, save_matrix


@timer_decorator
def calibrate_beta_batch(industries_data, C, beta_range=(0.01, 1.0), 
                         coarse_step=0.01, fine_range=0.03, fine_step=0.001,
                         max_iter=100, tol=1e-10):
    """
    批量校准多个行业的beta参数
    
    Args:
        industries_data: 行业数据字典 {行业名: {'O': O, 'D': D, 'target_distance': dist}}
        C: 成本矩阵
        beta_range: beta扫描范围
        coarse_step: 粗扫步长
        fine_range: 精细扫描范围
        fine_step: 精细扫描步长
        max_iter: Wilson模型最大迭代次数
        tol: Wilson模型收敛容差
    
    Returns:
        dict: 各行业校准结果
    """
    stats = StatsCollector("calibrate_beta_batch")
    stats.add('industry_count', len(industries_data))
    
    calibration_results = {}
    
    for ind_name, ind_data in industries_data.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"校准行业: {ind_name}")
        logger.info(f"{'='*60}")
        
        O = ind_data['O']
        D = ind_data['D']
        target_distance = ind_data['target_distance']
        
        # 执行校准
        result = calibrate_beta(
            O=O,
            D=D,
            C=C,
            target_distance=target_distance,
            beta_range=beta_range,
            coarse_step=coarse_step,
            fine_range=fine_range,
            fine_step=fine_step,
            max_iter=max_iter,
            tol=tol
        )
        
        calibration_results[ind_name] = result
        
        # 记录统计
        stats.add(f'{ind_name}_best_beta', result['best_beta'])
        stats.add(f'{ind_name}_error', result['error'])
        stats.add(f'{ind_name}_error_pct', result.get('error_pct', np.nan))
    
    stats.save('calibrate_beta_batch_stats.csv')
    
    return calibration_results


@timer_decorator
def compute_elasticity_batch(industries_data, calibration_results, C, 
                             T_obs_dict=None, save_results=True):
    """
    批量计算多个行业的弹性
    
    Args:
        industries_data: 行业数据字典
        calibration_results: 校准结果字典
        C: 成本矩阵
        T_obs_dict: 观测流量矩阵字典（可选）
        save_results: 是否保存结果
    
    Returns:
        dict: 各行业弹性结果
    """
    stats = StatsCollector("compute_elasticity_batch")
    stats.add('industry_count', len(industries_data))
    
    elasticity_results = {}
    
    for ind_name, ind_data in industries_data.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"计算弹性: {ind_name}")
        logger.info(f"{'='*60}")
        
        O = ind_data['O']
        D = ind_data['D']
        beta = calibration_results[ind_name]['best_beta']
        
        if np.isnan(beta):
            logger.warning(f"{ind_name}: beta为NaN，跳过")
            elasticity_results[ind_name] = {
                'KL': np.nan,
                'theta': np.nan,
                'rating': 'N/A',
                'error': 'Beta is NaN'
            }
            continue
        
        # 计算Wilson模型
        wilson_result = compute_wilson(O, D, C, beta)
        T_wilson = wilson_result['T_model']
        avg_dist = wilson_result['avg_dist']
        
        logger.info(f"  Wilson平均距离: {avg_dist:.4f}")
        
        # 如果有观测数据，计算KL散度
        if T_obs_dict and ind_name in T_obs_dict:
            T_obs = T_obs_dict[ind_name]
            total_obs = T_obs.sum()
            
            kl_result = compute_kl_divergence(T_obs, T_wilson, total_obs)
            
            elasticity_results[ind_name] = {
                'best_beta': beta,
                'target_distance': ind_data['target_distance'],
                'model_distance': avg_dist,
                'total_flow': wilson_result['total_flow'],
                'KL': kl_result['KL'],
                'theta': kl_result['theta'],
                'rating': kl_result['rating']
            }
            
            logger.info(f"  KL偏离: {kl_result['KL']:.6f}")
            logger.info(f"  结构弹性θ: {kl_result['theta']:.6f}")
            logger.info(f"  刚性评级: {kl_result['rating']}")
        else:
            # 没有观测数据，只保存Wilson结果
            elasticity_results[ind_name] = {
                'best_beta': beta,
                'target_distance': ind_data['target_distance'],
                'model_distance': avg_dist,
                'total_flow': wilson_result['total_flow'],
                'KL': None,
                'theta': None,
                'rating': None
            }
    
    # 保存结果
    if save_results:
        save_elasticity_results(elasticity_results, calibration_results)
    
    stats.add('completed_count', len([r for r in elasticity_results.values() if r.get('theta') is not None]))
    stats.save('compute_elasticity_batch_stats.csv')
    
    return elasticity_results


def save_elasticity_results(elasticity_results, calibration_results, 
                            output_dir=None):
    """
    保存弹性分析结果
    
    Args:
        elasticity_results: 弹性结果字典
        calibration_results: 校准结果字典
        output_dir: 输出目录
    """
    if output_dir is None:
        output_dir = get_result_path('4.Scenario_Analysis/4.1Extract_Ratio', '')
    
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 保存汇总表
    summary_rows = []
    for ind_name, result in elasticity_results.items():
        row = {
            '行业': ind_name,
            '最优β': result.get('best_beta'),
            '目标距离(km)': result.get('target_distance'),
            'Wilson距离(km)': result.get('model_distance'),
            '总人数': result.get('total_flow'),
            'KL偏离': result.get('KL'),
            '结构弹性θ': result.get('theta'),
            '刚性评级': result.get('rating')
        }
        summary_rows.append(row)
    
    summary_df = pd.DataFrame(summary_rows)
    summary_path = f"{output_dir}/elasticity_summary.csv"
    summary_df.to_csv(summary_path, index=False, encoding='utf-8-sig')
    logger.info(f"弹性汇总表已保存: {summary_path}")
    
    # 2. 保存详细JSON
    detailed = {}
    for ind_name in elasticity_results.keys():
        e = elasticity_results[ind_name]
        c = calibration_results.get(ind_name, {})
        
        detailed[ind_name] = {
            '最优Beta': e.get('best_beta'),
            'KL偏离': e.get('KL'),
            '结构弹性': e.get('theta'),
            '刚性评级': e.get('rating'),
            '目标平均距离_km': e.get('target_distance'),
            'Wilson平均距离_km': e.get('model_distance'),
            '全局总通勤人数': e.get('total_flow'),
            '校准误差': c.get('error'),
            '校准误差百分比': c.get('error_pct')
        }
    
    json_path = f"{output_dir}/elasticity_detailed.json"
    save_json(detailed, json_path)
    
    # 3. 保存β扫描数据
    for ind_name, cal_result in calibration_results.items():
        sweep = cal_result.get('sweep_data', [])
        if sweep:
            sweep_df = pd.DataFrame(sorted(sweep, key=lambda x: x['beta']))
            sweep_path = f"{output_dir}/beta_sweep_{ind_name}.csv"
            sweep_df.to_csv(sweep_path, index=False, encoding='utf-8-sig')
            logger.info(f"β扫描数据已保存: {sweep_path}")
    
    # 4. 保存文本报告
    report_path = f"{output_dir}/elasticity_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("分行业通勤弹性分析报告\n")
        f.write(f"生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        for ind_name in elasticity_results.keys():
            e = elasticity_results[ind_name]
            c = calibration_results.get(ind_name, {})
            
            f.write(f"{ind_name}\n")
            f.write(f"  最优β: {e.get('best_beta', 'N/A')}\n")
            f.write(f"  目标平均通勤距离: {e.get('target_distance', 'N/A')} km\n")
            f.write(f"  Wilson模型距离: {e.get('model_distance', 'N/A')} km\n")
            f.write(f"  校准误差: {c.get('error', 'N/A')} km")
            if c.get('error_pct'):
                f.write(f" ({c['error_pct']:.4f}%)\n")
            else:
                f.write("\n")
            f.write(f"  KL偏离: {e.get('KL', 'N/A')}\n")
            f.write(f"  结构弹性θ: {e.get('theta', 'N/A')}\n")
            f.write(f"  刚性评级: {e.get('rating', 'N/A')}\n")
            f.write(f"  全局总通勤人数: {e.get('total_flow', 'N/A')}\n\n")
    
    logger.info(f"分析报告已保存: {report_path}")
    
    return summary_df


@timer_decorator
def run_full_elasticity_analysis(industries_data, C, T_obs_dict=None,
                                 beta_range=(0.01, 1.0), 
                                 coarse_step=0.01, fine_range=0.03, fine_step=0.001,
                                 output_dir=None):
    """
    运行完整的弹性分析流程
    
    包括：beta校准、Wilson计算、KL散度、结果保存
    
    Args:
        industries_data: 行业数据字典
        C: 成本矩阵
        T_obs_dict: 观测流量矩阵字典（可选）
        beta_range: beta扫描范围
        coarse_step: 粗扫步长
        fine_range: 精细扫描范围
        fine_step: 精细扫描步长
        output_dir: 输出目录
    
    Returns:
        dict: 完整结果
    """
    logger.info("=" * 80)
    logger.info("开始完整弹性分析流程")
    logger.info("=" * 80)
    
    # 1. 批量校准beta
    logger.info("\n[1/2] 批量校准beta参数...")
    calibration_results = calibrate_beta_batch(
        industries_data=industries_data,
        C=C,
        beta_range=beta_range,
        coarse_step=coarse_step,
        fine_range=fine_range,
        fine_step=fine_step
    )
    
    # 2. 批量计算弹性
    logger.info("\n[2/2] 批量计算弹性...")
    elasticity_results = compute_elasticity_batch(
        industries_data=industries_data,
        calibration_results=calibration_results,
        C=C,
        T_obs_dict=T_obs_dict,
        save_results=False  # 稍后再统一保存
    )
    
    # 3. 保存结果
    if output_dir:
        save_elasticity_results(elasticity_results, calibration_results, output_dir)
    else:
        save_elasticity_results(elasticity_results, calibration_results)
    
    logger.info("\n" + "=" * 80)
    logger.info("弹性分析完成！")
    logger.info("=" * 80)
    
    return {
        'calibration': calibration_results,
        'elasticity': elasticity_results
    }


# 便捷函数：用于全量数据（不分行业）的校准
def calibrate_beta_universal(O, D, C, target_distance, **kwargs):
    """
    全量数据的beta校准（不分行业）

    这是calibrate_beta的便捷包装函数
    """
    return calibrate_beta(O, D, C, target_distance, **kwargs)


@timer_decorator
def estimate_rigidity_poisson(
    T_obs: np.ndarray,
    O_array: np.ndarray,
    D_array: np.ndarray,
    C_matrix: np.ndarray,
    beta: float,
    output_dir=None,
) -> dict:
    """
    泊松回归估计 O/D 端刚性参数，并映射为 UOT 惩罚权重 theta。

    模型（D 端）：E[T_ij] = exp(mu_i + alpha_D * ln(D_j+1) - beta * C_ij)
    模型（O 端）：E[T_ij] = exp(nu_j + alpha_O * ln(O_i+1) - beta * C_ij)
    beta 作为 offset 固定，不参与估计。

    映射：tau = alpha，theta = tau / (1 - tau) * epsilon，epsilon = 1 / beta

    Args:
        T_obs: 实际通勤 OD 矩阵，shape (n_taz, n_taz)
        O_array: O 边际向量，shape (n_taz,)
        D_array: D 边际向量，shape (n_taz,)
        C_matrix: 距离矩阵，shape (n_taz, n_taz)，单位与 beta 一致
        beta: 距离衰减系数（Wilson 标定值，米单位约 0.0003）
        output_dir: 结果保存目录，None 则不保存

    Returns:
        dict: {
            'alpha_O': float,
            'alpha_D': float,
            'theta_O': float,
            'theta_D': float,
            'epsilon': float,
        }
    """
    try:
        import statsmodels.api as sm
    except ImportError:
        raise ImportError("请安装 statsmodels: pip install statsmodels")

    from pathlib import Path

    stats = StatsCollector("estimate_rigidity_poisson")
    stats.add('beta', beta)
    n_taz = len(O_array)
    stats.add('n_taz', n_taz)

    epsilon = 1.0 / beta

    # 构建长格式数据（保留所有样本，包括零值）
    logger.info("构建长格式 OD 数据...")
    rows = []
    for i in range(n_taz):
        for j in range(n_taz):
            rows.append({
                'y': T_obs[i, j],
                'origin': i,
                'destination': j,
                'log_O': np.log(O_array[i] + 1),
                'log_D': np.log(D_array[j] + 1),
                'offset': -beta * C_matrix[i, j],
            })
    df = pd.DataFrame(rows)
    stats.add('total_pairs', len(df))
    stats.add('nonzero_pairs', int((df['y'] > 0).sum()))

    # --- D 端回归：y ~ log_D + FE(origin) + offset ---
    logger.info("[D 端回归] 构建设计矩阵...")
    X_d = df[['log_D']].copy()
    X_d = sm.add_constant(X_d)
    origin_dummies = pd.get_dummies(df['origin'], prefix='o', drop_first=True)
    X_d = pd.concat([X_d, origin_dummies], axis=1)
    y_d = df['y'].values.astype(float)
    offset_d = df['offset'].values

    alpha_D = np.nan
    try:
        logger.info("[D 端回归] 拟合泊松 GLM...")
        model_d = sm.GLM(y_d, X_d, family=sm.families.Poisson(), offset=offset_d)
        result_d = model_d.fit(maxiter=100)
        alpha_D = float(result_d.params['log_D'])
        pval_D = float(result_d.pvalues['log_D'])
        logger.info(f"  alpha_D = {alpha_D:.6f} (p={pval_D:.4f})")
        stats.add('alpha_D', alpha_D)
        stats.add('pval_D', pval_D)
    except Exception as e:
        logger.warning(f"D 端完整模型失败: {e}，尝试简化模型（无固定效应）")
        try:
            X_d_simple = sm.add_constant(df[['log_D']])
            model_d = sm.GLM(y_d, X_d_simple, family=sm.families.Poisson(), offset=offset_d)
            result_d = model_d.fit(maxiter=100)
            alpha_D = float(result_d.params['log_D'])
            logger.info(f"  alpha_D = {alpha_D:.6f} (简化模型)")
            stats.add('alpha_D', alpha_D)
            stats.add('alpha_D_model', 'simplified')
        except Exception as e2:
            logger.error(f"D 端简化模型也失败: {e2}")
            alpha_D = 0.5
            stats.add('alpha_D', alpha_D)
            stats.add('alpha_D_model', 'default')

    # --- O 端回归：y ~ log_O + FE(destination) + offset ---
    logger.info("[O 端回归] 构建设计矩阵...")
    X_o = df[['log_O']].copy()
    X_o = sm.add_constant(X_o)
    dest_dummies = pd.get_dummies(df['destination'], prefix='d', drop_first=True)
    X_o = pd.concat([X_o, dest_dummies], axis=1)
    y_o = df['y'].values.astype(float)
    offset_o = df['offset'].values

    alpha_O = np.nan
    try:
        logger.info("[O 端回归] 拟合泊松 GLM...")
        model_o = sm.GLM(y_o, X_o, family=sm.families.Poisson(), offset=offset_o)
        result_o = model_o.fit(maxiter=100)
        alpha_O = float(result_o.params['log_O'])
        pval_O = float(result_o.pvalues['log_O'])
        logger.info(f"  alpha_O = {alpha_O:.6f} (p={pval_O:.4f})")
        stats.add('alpha_O', alpha_O)
        stats.add('pval_O', pval_O)
    except Exception as e:
        logger.warning(f"O 端完整模型失败: {e}，尝试简化模型（无固定效应）")
        try:
            X_o_simple = sm.add_constant(df[['log_O']])
            model_o = sm.GLM(y_o, X_o_simple, family=sm.families.Poisson(), offset=offset_o)
            result_o = model_o.fit(maxiter=100)
            alpha_O = float(result_o.params['log_O'])
            logger.info(f"  alpha_O = {alpha_O:.6f} (简化模型)")
            stats.add('alpha_O', alpha_O)
            stats.add('alpha_O_model', 'simplified')
        except Exception as e2:
            logger.error(f"O 端简化模型也失败: {e2}")
            alpha_O = 0.5
            stats.add('alpha_O', alpha_O)
            stats.add('alpha_O_model', 'default')

    # 映射 alpha -> theta
    # tau = alpha，theta = tau / (1 - tau) * epsilon
    tau_O = float(np.clip(alpha_O, 1e-6, 1 - 1e-6))
    tau_D = float(np.clip(alpha_D, 1e-6, 1 - 1e-6))
    theta_O = tau_O / (1.0 - tau_O) * epsilon
    theta_D = tau_D / (1.0 - tau_D) * epsilon

    logger.info(f"刚性参数: alpha_O={alpha_O:.4f}, alpha_D={alpha_D:.4f}")
    logger.info(f"UOT 惩罚权重: theta_O={theta_O:.4f}, theta_D={theta_D:.4f}, epsilon={epsilon:.4f}")
    stats.add('theta_O', theta_O)
    stats.add('theta_D', theta_D)
    stats.add('epsilon', epsilon)

    if output_dir is not None:
        from pathlib import Path
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        params_df = pd.DataFrame([{
            'alpha_O': alpha_O,
            'alpha_D': alpha_D,
            'theta_O': theta_O,
            'theta_D': theta_D,
            'epsilon': epsilon,
            'beta': beta,
        }])
        params_df.to_csv(output_dir / 'star_rigidity_params.csv', index=False,
                         encoding='utf-8-sig', float_format='%.6f')

        stats.save('estimate_rigidity_poisson_stats.csv')
        logger.info(f"刚性参数已保存: {output_dir}")

    return {
        'alpha_O': alpha_O,
        'alpha_D': alpha_D,
        'theta_O': theta_O,
        'theta_D': theta_D,
        'epsilon': epsilon,
    }


def solve_uot_scenario(
    C: np.ndarray,
    O0: np.ndarray,
    D0: np.ndarray,
    theta_O: float,
    theta_D: float,
    beta: float,
    total_mass: float,
    max_iter: int = 200,
    tol: float = 1e-5,
) -> tuple:
    """
    UOT 广义 Sinkhorn 求解器：支持双端独立 theta，强制总量守恒。

    允许 O/D 边际偏离锚点（搬家/换工作），但总通勤量守恒。

    Args:
        C: 成本矩阵，shape (n, n)
        O0: O 端锚点边际，shape (n,)
        D0: D 端锚点边际，shape (n,)
        theta_O: O 端刚性惩罚权重
        theta_D: D 端刚性惩罚权重
        beta: 距离衰减系数
        total_mass: 总通勤量（守恒约束）
        max_iter: 最大迭代次数
        tol: 收敛阈值（缩放向量变化量）

    Returns:
        T (np.ndarray): 情景 OD 矩阵，shape (n, n)
        O_star (np.ndarray): 实际 O 边际
        D_star (np.ndarray): 实际 D 边际
    """
    n = len(O0)

    # 松弛指数 tau
    epsilon = 1.0 / beta
    tau_O = theta_O / (theta_O + epsilon)
    tau_D = theta_D / (theta_D + epsilon)

    # 归一化锚点至 total_mass
    O0_norm = O0 / O0.sum() * total_mass
    D0_norm = D0 / D0.sum() * total_mass

    # log-domain Sinkhorn：用 log(u), log(v) 迭代，避免浮点溢出
    # log K = -beta * C
    log_K = (-beta * C).astype(np.float64)

    log_u = np.zeros(n, dtype=np.float64)
    log_v = np.zeros(n, dtype=np.float64)

    log_O0 = np.log(np.maximum(O0_norm, 1e-300))
    log_D0 = np.log(np.maximum(D0_norm, 1e-300))

    def log_sum_exp_mat_vec(log_M, log_x, axis=1):
        """log(M @ exp(log_x)) via logsumexp，axis=1 表示行方向求和"""
        # log_M: (n, n), log_x: (n,)
        if axis == 1:
            tmp = log_M + log_x[np.newaxis, :]   # (n, n)
        else:
            tmp = log_M + log_x[:, np.newaxis]   # (n, n), then sum over rows
            tmp = tmp.T
        max_tmp = tmp.max(axis=1, keepdims=True)
        return (max_tmp.squeeze() +
                np.log(np.exp(tmp - max_tmp).sum(axis=1)))

    for iteration in range(max_iter):
        log_u_old = log_u.copy()

        # log(K @ exp(log_v))
        log_Kv = log_sum_exp_mat_vec(log_K, log_v, axis=1)
        log_u = tau_O * (log_O0 - log_Kv) + (1 - tau_O) * log_u

        # log(K^T @ exp(log_u))
        log_Ktu = log_sum_exp_mat_vec(log_K.T, log_u, axis=1)
        log_v = tau_D * (log_D0 - log_Ktu) + (1 - tau_D) * log_v

        delta = np.max(np.abs(log_u - log_u_old))
        if delta < tol:
            logger.info(f"UOT 收敛于第 {iteration + 1} 次迭代 (delta={delta:.2e})")
            break
    else:
        logger.warning(f"UOT 未在 {max_iter} 次迭代内收敛 (final delta={delta:.2e})")

    # 构建传输矩阵（log domain -> exp）
    log_T = log_u[:, np.newaxis] + log_K + log_v[np.newaxis, :]
    # 防止极端值
    log_T = np.clip(log_T, -700, 700)
    T = np.exp(log_T)

    # 强制总量守恒
    current_mass = T.sum()
    if current_mass > 1e-10:
        T = T * (total_mass / current_mass)

    O_star = T.sum(axis=1)
    D_star = T.sum(axis=0)

    return T, O_star, D_star


@timer_decorator
def compute_scenario_uot(
    C_matrix: np.ndarray,
    O_array: np.ndarray,
    D_array: np.ndarray,
    theta_O: float,
    theta_D: float,
    beta: float,
    rigidityO_multiplier: float = 1.0,
    rigidityD_multiplier: float = 1.0,
    scenario_label: str = 'scenario',
    output_dir=None,
) -> dict:
    """
    情景推演主函数：按独立系数缩放 O/D 端 theta，调用 UOT 求解器，保存结果。

    Args:
        C_matrix: 距离矩阵，shape (n, n)
        O_array: O 边际向量（锚点）
        D_array: D 边际向量（锚点）
        theta_O: O 端基准刚性参数
        theta_D: D 端基准刚性参数
        beta: 距离衰减系数
        rigidityO_multiplier: O 端刚性变化系数（1.2 = 提升 20%）
        rigidityD_multiplier: D 端刚性变化系数（0.8 = 降低 20%）
        scenario_label: 情景标识，用于文件命名
        output_dir: 结果保存目录，None 则不保存

    Returns:
        dict: {
            'T_scenario': np.ndarray,
            'O_star': np.ndarray,
            'D_star': np.ndarray,
            'avg_dist': float,
            'total_flow': float,
        }
    """
    from pathlib import Path

    stats = StatsCollector("compute_scenario_uot")
    stats.add('rigidityO_multiplier', rigidityO_multiplier)
    stats.add('rigidityD_multiplier', rigidityD_multiplier)
    stats.add('scenario_label', scenario_label)

    theta_O_s = theta_O * rigidityO_multiplier
    theta_D_s = theta_D * rigidityD_multiplier
    total_mass = float(O_array.sum())

    logger.info(f"情景推演: {scenario_label}, O_mult={rigidityO_multiplier}, D_mult={rigidityD_multiplier}")
    logger.info(f"theta_O: {theta_O:.4f} -> {theta_O_s:.4f}")
    logger.info(f"theta_D: {theta_D:.4f} -> {theta_D_s:.4f}")

    T_scenario, O_star, D_star = solve_uot_scenario(
        C=C_matrix,
        O0=O_array,
        D0=D_array,
        theta_O=theta_O_s,
        theta_D=theta_D_s,
        beta=beta,
        total_mass=total_mass,
    )

    total_flow = float(T_scenario.sum())
    valid_mask = C_matrix > 0
    avg_dist = float(
        np.sum(T_scenario[valid_mask] * C_matrix[valid_mask]) / total_flow
    ) if total_flow > 0 else 0.0

    # KL 偏离度
    def kl_div(p, q):
        p = np.clip(p, 1e-10, None)
        q = np.clip(q, 1e-10, None)
        p = p / p.sum()
        q = q / q.sum()
        return float(np.sum(p * np.log(p / q)))

    kl_O = kl_div(O_star, O_array)
    kl_D = kl_div(D_star, D_array)

    stats.add('total_flow', total_flow)
    stats.add('avg_dist', avg_dist)
    stats.add('kl_O_star_vs_O0', kl_O)
    stats.add('kl_D_star_vs_D0', kl_D)
    logger.info(f"avg_dist={avg_dist:.2f} m, KL(O*||O0)={kl_O:.4f}, KL(D*||D0)={kl_D:.4f}")

    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        save_matrix(T_scenario, str(output_dir / 'T_scenario_float.npy'))

        summary_df = pd.DataFrame([{
            'scenario_label': scenario_label,
            'rigidityO_multiplier': rigidityO_multiplier,
            'rigidityD_multiplier': rigidityD_multiplier,
            'theta_O_base': theta_O,
            'theta_D_base': theta_D,
            'theta_O_scenario': theta_O_s,
            'theta_D_scenario': theta_D_s,
            'total_flow': total_flow,
            'avg_dist': avg_dist,
            'kl_O_star_vs_O0': kl_O,
            'kl_D_star_vs_D0': kl_D,
        }])
        summary_df.to_csv(output_dir / 'scenario_computation_stats.csv', index=False,
                          encoding='utf-8-sig', float_format='%.4f')

        stats.save('compute_scenario_uot_stats.csv')
        logger.info(f"情景推演结果已保存: {output_dir}")

    return {
        'T_scenario': T_scenario,
        'O_star': O_star,
        'D_star': D_star,
        'avg_dist': avg_dist,
        'total_flow': total_flow,
    }
