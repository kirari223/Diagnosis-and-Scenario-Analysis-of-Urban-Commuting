"""
格局模型模块
包含线性规划模型和Wilson双约束模型
"""
import numpy as np
import pandas as pd

from .config import get_result_path, WILSON_DEFAULT_BETA, WILSON_MAX_ITER, WILSON_TOL
from .utils import StatsCollector, timer_decorator, logger, save_matrix


def compute_linear_plan(O_list, D_list, C_matrix, triplets, 
                        housing_total=None, output_path=None):
    """
    线性规划求解最优通勤格局（最小化总通勤距离）
    
    使用Gurobi求解器
    
    Args:
        O_list: 住房分布列表
        D_list: 工作分布列表
        C_matrix: 距离成本矩阵
        triplets: 有效OD对列表 [(o, d, distance), ...]
        housing_total: 总人数（用于目标函数归一化）
        output_path: 结果输出路径
    
    Returns:
        dict: 包含T_matrix, flow_results, objective_value的结果
    """
    try:
        import gurobipy as gp
        from gurobipy import GRB
    except ImportError:
        logger.error("Gurobi未安装，无法使用线性规划模型")
        raise ImportError("请安装Gurobi: pip install gurobipy")
    
    stats = StatsCollector("compute_linear_plan")
    
    # 参数转换
    m = int(max([i for i, x in enumerate(O_list) if x is not None]))
    n = int(max([i for i, x in enumerate(D_list) if x is not None]))
    W = housing_total or sum(x for x in O_list if x is not None)
    
    stats.add('m', m)
    stats.add('n', n)
    stats.add('W', W)
    stats.add('triplets_count', len(triplets))
    
    logger.info(f"线性规划参数: m={m}, n={n}, W={W}")
    
    # 创建模型
    model = gp.Model("Commuting_Optimization")
    model.setParam('OutputFlag', 0)  # 减少输出
    
    # 提取有效点对
    valid_pairs = [(t[0], t[1]) for t in triplets]
    c_dict = {(t[0], t[1]): t[2] for t in triplets}
    
    # 创建决策变量
    X = model.addVars(valid_pairs, vtype=GRB.INTEGER, lb=0, name="x")
    stats.add('variables_count', len(valid_pairs))
    
    # 设置目标函数：最小化总通勤距离
    obj = gp.quicksum(c_dict[i, j] * X[i, j] for i, j in valid_pairs) / W
    model.setObjective(obj, GRB.MINIMIZE)
    
    # 预处理：创建起点和终点的索引字典
    origin_pairs = {}
    destin_pairs = {}
    
    for i, j in valid_pairs:
        if i not in origin_pairs:
            origin_pairs[i] = []
        origin_pairs[i].append((i, j))
        
        if j not in destin_pairs:
            destin_pairs[j] = []
        destin_pairs[j].append((i, j))
    
    # 添加起点约束
    constraint_count = 0
    for i in range(m + 1):
        if i in origin_pairs and O_list[i] is not None:
            model.addConstr(
                gp.quicksum(X[i, j] for i, j in origin_pairs[i]) == O_list[i],
                name=f"O_Constraint_{i}"
            )
            constraint_count += 1
    
    # 添加终点约束
    for j in range(n + 1):
        if j in destin_pairs and D_list[j] is not None:
            model.addConstr(
                gp.quicksum(X[i, j] for i, j in destin_pairs[j]) == D_list[j],
                name=f"D_Constraint_{j}"
            )
            constraint_count += 1
    
    stats.add('constraints_count', constraint_count)
    
    # 求解
    logger.info("开始求解线性规划模型...")
    model.optimize()
    
    stats.add('model_status', model.status)
    
    if model.status == GRB.OPTIMAL:
        logger.info(f"模型求解成功，最优目标值: {model.objVal}")
        stats.add('objective_value', model.objVal)
        
        # 提取结果
        flow_results = []
        T_matrix = np.zeros((m + 1, n + 1))
        
        epsilon = 1e-6
        for (i, j) in valid_pairs:
            value = X[i, j].X
            int_value = round(value)
            if abs(value) > epsilon and int_value > 0:
                flow_results.append({
                    "o": i,
                    "d": j,
                    "人数": int_value
                })
                if i < T_matrix.shape[0] and j < T_matrix.shape[1]:
                    T_matrix[i, j] = int_value
        
        stats.add('nonzero_flows', len(flow_results))
        stats.add('T_matrix_sum', T_matrix.sum())
        
        # 保存结果
        if output_path:
            df_result = pd.DataFrame(flow_results)
            df_result.to_csv(output_path, index=False, encoding='utf-8-sig')
            save_matrix(T_matrix, str(output_path).replace('.csv', '.npy'))
            logger.info(f"结果已保存: {output_path}")
            stats.add('output_path', str(output_path))
        
        stats.save('compute_linear_plan_stats.csv')
        
        return {
            'T_matrix': T_matrix,
            'flow_results': flow_results,
            'objective_value': model.objVal,
            'status': 'OPTIMAL'
        }
    else:
        logger.error(f"模型求解失败，状态码: {model.status}")
        stats.add('error', f"Optimization failed with status {model.status}")
        stats.save('compute_linear_plan_stats.csv')
        
        return {
            'T_matrix': None,
            'flow_results': [],
            'objective_value': None,
            'status': f'FAILED_{model.status}'
        }


@timer_decorator
def compute_wilson(O, D, C, beta=None, max_iter=None, tol=None, 
                   return_details=False):
    """
    Wilson双约束模型 - numpy向量化版本
    
    T_ij = A_i * O_i * B_j * D_j * exp(-beta * C_ij)
    
    Args:
        O: 起点约束向量 (m,)
        D: 终点约束向量 (n,)
        C: 成本矩阵 (m, n)
        beta: 摩擦系数（默认使用配置值）
        max_iter: 最大迭代次数
        tol: 收敛容差
        return_details: 是否返回详细结果
    
    Returns:
        dict: 包含T_model, avg_dist, A, B的结果
    """
    stats = StatsCollector("compute_wilson")
    
    # 使用默认值（beta=0 是合法值，不能用 or 替换）
    if beta is None:
        beta = WILSON_DEFAULT_BETA
    max_iter = max_iter or WILSON_MAX_ITER
    tol = tol or WILSON_TOL
    
    # 确保输入是numpy数组
    O = np.array(O, dtype=float)
    D = np.array(D, dtype=float)
    C = np.array(C, dtype=float)
    
    # 处理None值
    O = np.nan_to_num(O, nan=0.0)
    D = np.nan_to_num(D, nan=0.0)
    
    m = len(O)
    n = len(D)
    
    stats.add('m', m)
    stats.add('n', n)
    stats.add('beta', beta)
    stats.add('max_iter', max_iter)
    stats.add('tol', tol)
    
    logger.info(f"Wilson模型参数: m={m}, n={n}, beta={beta}")
    
    # 计算阻抗矩阵
    Q = np.exp(-beta * C)
    Q = np.nan_to_num(Q, nan=0.0)
    
    # 初始化平衡因子
    A = np.ones(m)
    B = np.ones(n)
    
    # 迭代求解
    for it in range(max_iter):
        A_old = A.copy()
        B_old = B.copy()
        
        # 更新A
        BD = B * D
        sum_j = Q @ BD
        A = 1.0 / np.maximum(sum_j, 1e-15)
        
        # 更新B
        AO = A * O
        sum_i = Q.T @ AO
        B = 1.0 / np.maximum(sum_i, 1e-15)
        
        # 收敛检查
        err_A = np.mean(np.abs(A - A_old) / (np.abs(A_old) + 1e-10))
        err_B = np.mean(np.abs(B - B_old) / (np.abs(B_old) + 1e-10))
        
        if max(err_A, err_B) < tol:
            logger.info(f"Wilson模型收敛于迭代 {it + 1}")
            stats.add('iterations', it + 1)
            stats.add('converged', True)
            break
    else:
        logger.warning(f"Wilson模型达到最大迭代次数 {max_iter}")
        stats.add('iterations', max_iter)
        stats.add('converged', False)
        stats.add('final_err_A', err_A)
        stats.add('final_err_B', err_B)
    
    # 计算模型流量矩阵
    AO = (A * O).reshape(-1, 1)
    BD = (B * D).reshape(1, -1)
    T_model = AO * BD * Q
    
    # 计算平均通勤距离
    total = T_model.sum()
    avg_dist = (T_model * C).sum() / total if total > 1e-10 else np.nan
    
    stats.add('total_flow', total)
    stats.add('avg_distance', avg_dist)
    stats.add('nonzero_flows', np.count_nonzero(T_model > 1e-10))
    
    # 验证约束
    row_sums = T_model.sum(axis=1)
    col_sums = T_model.sum(axis=0)
    
    row_error = np.mean(np.abs(row_sums - O) / (O + 1e-10))
    col_error = np.mean(np.abs(col_sums - D) / (D + 1e-10))
    
    stats.add('row_constraint_error', row_error)
    stats.add('col_constraint_error', col_error)
    
    stats.save('compute_wilson_stats.csv')
    
    result = {
        'T_model': T_model,
        'avg_dist': avg_dist,
        'A': A,
        'B': B,
        'total_flow': total,
        'iterations': stats.stats[-1].get('iterations', max_iter) if stats.stats else max_iter
    }
    
    if return_details:
        result.update({
            'row_constraint_error': row_error,
            'col_constraint_error': col_error,
            'Q': Q
        })
    
    return result


@timer_decorator
def calibrate_beta(O, D, C, target_distance, 
                   beta_range=(0.01, 1.0), coarse_step=0.01, fine_range=0.03, fine_step=0.001,
                   max_iter=None, tol=None):
    """
    校准Wilson模型的beta参数
    
    使用两阶段扫描：粗扫 + 精细扫描
    
    Args:
        O: 起点约束向量
        D: 终点约束向量
        C: 成本矩阵
        target_distance: 目标平均通勤距离
        beta_range: beta扫描范围
        coarse_step: 粗扫步长
        fine_range: 精细扫描范围（相对于最优值）
        fine_step: 精细扫描步长
        max_iter: Wilson模型最大迭代次数
        tol: Wilson模型收敛容差
    
    Returns:
        dict: 包含best_beta, model_distance, error, sweep_data的结果
    """
    stats = StatsCollector("calibrate_beta")
    stats.add('target_distance', target_distance)
    stats.add('beta_range', beta_range)
    stats.add('coarse_step', coarse_step)
    
    logger.info(f"开始校准beta参数，目标距离: {target_distance}")
    
    # 第一阶段：粗扫
    beta_coarse = np.arange(beta_range[0], beta_range[1] + coarse_step, coarse_step)
    logger.info(f"粗扫: beta = {beta_range[0]} ~ {beta_range[1]}, step={coarse_step} ({len(beta_coarse)}个点)")
    
    sweep = []
    for idx, beta in enumerate(beta_coarse):
        try:
            result = compute_wilson(O, D, C, beta, max_iter, tol)
            avg_dist = result['avg_dist']
            
            if not np.isnan(avg_dist):
                sweep.append({
                    'beta': float(beta),
                    'distance': float(avg_dist),
                    'error': float(abs(avg_dist - target_distance)),
                    'total_flow': float(result['total_flow'])
                })
        except Exception as e:
            logger.warning(f"beta={beta} 计算失败: {e}")
        
        if (idx + 1) % 10 == 0 or idx == len(beta_coarse) - 1:
            logger.info(f"  粗扫进度: [{idx+1}/{len(beta_coarse)}] beta={beta:.3f}")
    
    if not sweep:
        logger.error("粗扫无有效点！")
        stats.add('error', 'No valid points in coarse sweep')
        stats.save('calibrate_beta_stats.csv')
        return {
            'best_beta': np.nan,
            'model_distance': np.nan,
            'error': np.nan,
            'sweep_data': []
        }
    
    best_coarse = min(sweep, key=lambda x: x['error'])
    logger.info(f"粗扫最优: beta={best_coarse['beta']:.3f}, "
                f"distance={best_coarse['distance']:.4f}, "
                f"error={best_coarse['error']:.4f}")
    
    # 第二阶段：精细扫描
    fine_center = best_coarse['beta']
    fine_start = max(beta_range[0], fine_center - fine_range)
    fine_end = min(beta_range[1], fine_center + fine_range)
    beta_fine = np.arange(fine_start, fine_end + fine_step, fine_step)
    
    stats.add('fine_start', fine_start)
    stats.add('fine_end', fine_end)
    stats.add('fine_step', fine_step)
    
    logger.info(f"精细扫描: beta = {fine_start:.4f} ~ {fine_end:.4f}, step={fine_step} ({len(beta_fine)}个点)")
    
    fine_sweep = []
    for idx, beta in enumerate(beta_fine):
        try:
            result = compute_wilson(O, D, C, beta, max_iter, tol)
            avg_dist = result['avg_dist']
            
            if not np.isnan(avg_dist):
                fine_sweep.append({
                    'beta': float(beta),
                    'distance': float(avg_dist),
                    'error': float(abs(avg_dist - target_distance)),
                    'total_flow': float(result['total_flow'])
                })
        except Exception as e:
            pass
        
        if (idx + 1) % 20 == 0 or idx == len(beta_fine) - 1:
            logger.info(f"  精细扫描进度: [{idx+1}/{len(beta_fine)}] beta={beta:.4f}")
    
    # 合并结果
    all_sweep = sweep + fine_sweep
    best = min(all_sweep, key=lambda x: x['error'])
    
    error_pct = 100 * best['error'] / target_distance if target_distance != 0 else 0
    
    logger.info(f"\n>>> 最优 beta = {best['beta']:.6f}")
    logger.info(f">>> Wilson距离 = {best['distance']:.4f}")
    logger.info(f">>> 目标距离 = {target_distance:.4f}")
    logger.info(f">>> 误差 = {best['error']:.6f} ({error_pct:.4f}%)")
    
    stats.add('best_beta', best['beta'])
    stats.add('model_distance', best['distance'])
    stats.add('error', best['error'])
    stats.add('error_pct', error_pct)
    stats.add('sweep_points', len(all_sweep))
    
    stats.save('calibrate_beta_stats.csv')
    
    return {
        'best_beta': best['beta'],
        'model_distance': best['distance'],
        'target_distance': target_distance,
        'error': best['error'],
        'error_pct': error_pct,
        'sweep_data': all_sweep
    }


@timer_decorator
def extract_od_rigidity(
    df_od: pd.DataFrame,
    O_array: np.ndarray,
    D_array: np.ndarray,
    C_matrix: np.ndarray,
    beta: float,
    o_col: str = 'o',
    d_col: str = 'd',
    value_col: str = '人数',
    output_dir=None,
) -> dict:
    """
    泊松回归提取 OD 两侧刚性参数。

    模型：T_ij ~ Poisson(exp(alpha_i + gamma_j - beta * C_ij))
    对有效 OD 对构建设计矩阵，用 L-BFGS-B 最大化泊松对数似然。

    Args:
        df_od: OD 数据，含 o_col, d_col, value_col 列
        O_array: O 边际向量，索引对应 TAZ ID（0-based）
        D_array: D 边际向量，索引对应 TAZ ID（0-based）
        C_matrix: 距离矩阵，shape (n, n)
        beta: 距离衰减系数（来自 Wilson 标定）
        o_col: 起点列名
        d_col: 终点列名
        value_col: 流量列名
        output_dir: 结果保存目录，None 则不保存

    Returns:
        dict: {
            'rigidity_O': np.ndarray,  shape (n_taz,)，O 侧刚性 alpha
            'rigidity_D': np.ndarray,  shape (n_taz,)，D 侧刚性 gamma
            'taz_ids': list,           TAZ ID 列表
            'pearson_r': float,        模型预测流与观测流的 Pearson 相关系数
            'log_likelihood': float,
        }
    """
    from scipy.optimize import minimize
    from scipy.stats import pearsonr
    from pathlib import Path

    stats = StatsCollector("extract_od_rigidity")
    stats.add('beta', beta)
    stats.add('input_rows', len(df_od))

    df = df_od[[o_col, d_col, value_col]].copy()
    df = df[df[value_col] > 0].dropna()

    taz_ids = sorted(set(df[o_col].unique()) | set(df[d_col].unique()))
    taz_index = {t: i for i, t in enumerate(taz_ids)}
    n = len(taz_ids)

    stats.add('n_taz', n)
    stats.add('n_od_pairs', len(df))

    o_idx = df[o_col].map(taz_index).values.astype(int)
    d_idx = df[d_col].map(taz_index).values.astype(int)
    t_obs = df[value_col].values.astype(float)

    # 距离项（固定，不参与优化）
    c_vals = np.array([C_matrix[o, d] for o, d in zip(o_idx, d_idx)], dtype=float)
    fixed_term = -beta * c_vals

    def neg_log_likelihood(params):
        alpha = params[:n]
        gamma = params[n:]
        log_mu = alpha[o_idx] + gamma[d_idx] + fixed_term
        # 泊松对数似然：sum(t * log_mu - exp(log_mu))
        ll = np.sum(t_obs * log_mu - np.exp(log_mu))
        return -ll

    def neg_ll_grad(params):
        alpha = params[:n]
        gamma = params[n:]
        log_mu = alpha[o_idx] + gamma[d_idx] + fixed_term
        mu = np.exp(log_mu)
        residual = t_obs - mu
        grad_alpha = np.zeros(n)
        grad_gamma = np.zeros(n)
        np.add.at(grad_alpha, o_idx, residual)
        np.add.at(grad_gamma, d_idx, residual)
        return np.concatenate([-grad_alpha, -grad_gamma])

    x0 = np.zeros(2 * n)
    logger.info(f"开始泊松回归优化，参数维度: {2*n}")
    res = minimize(
        neg_log_likelihood, x0, jac=neg_ll_grad,
        method='L-BFGS-B',
        options={'maxiter': 1000, 'ftol': 1e-12, 'gtol': 1e-8}
    )

    alpha_opt = res.x[:n]
    gamma_opt = res.x[n:]
    log_likelihood = -res.fun

    # 计算 Pearson 相关
    log_mu_pred = alpha_opt[o_idx] + gamma_opt[d_idx] + fixed_term
    t_pred = np.exp(log_mu_pred)
    pearson_r, _ = pearsonr(t_obs, t_pred)

    stats.add('log_likelihood', log_likelihood)
    stats.add('pearson_r', pearson_r)
    stats.add('optimizer_success', res.success)
    logger.info(f"优化完成: success={res.success}, log_likelihood={log_likelihood:.4f}, pearson_r={pearson_r:.4f}")

    # 构建全量 TAZ 数组（未出现的 TAZ 填 0）
    n_full = len(O_array)
    rigidity_O_full = np.zeros(n_full)
    rigidity_D_full = np.zeros(n_full)
    for i, taz in enumerate(taz_ids):
        if taz < n_full:
            rigidity_O_full[taz] = alpha_opt[i]
            rigidity_D_full[taz] = gamma_opt[i]

    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        df_alpha = pd.DataFrame({'taz': taz_ids, 'alpha': alpha_opt})
        df_alpha.to_csv(output_dir / 'rigidity_O.csv', index=False, encoding='utf-8-sig',
                        float_format='%.6f')

        df_gamma = pd.DataFrame({'taz': taz_ids, 'gamma': gamma_opt})
        df_gamma.to_csv(output_dir / 'rigidity_D.csv', index=False, encoding='utf-8-sig',
                        float_format='%.6f')

        summary = pd.DataFrame({
            'side': ['O (alpha)', 'D (gamma)'],
            'mean': [alpha_opt.mean(), gamma_opt.mean()],
            'median': [np.median(alpha_opt), np.median(gamma_opt)],
            'std': [alpha_opt.std(), gamma_opt.std()],
            'min': [alpha_opt.min(), gamma_opt.min()],
            'max': [alpha_opt.max(), gamma_opt.max()],
        })
        summary.to_csv(output_dir / 'star_rigidity_summary.csv', index=False,
                       encoding='utf-8-sig', float_format='%.6f')

        stats.save('extract_od_rigidity_stats.csv')
        logger.info(f"刚性提取结果已保存: {output_dir}")

    return {
        'rigidity_O': rigidity_O_full,
        'rigidity_D': rigidity_D_full,
        'taz_ids': taz_ids,
        'pearson_r': pearson_r,
        'log_likelihood': log_likelihood,
    }


@timer_decorator
def compute_scenario_od(
    rigidity_O: np.ndarray,
    rigidity_D: np.ndarray,
    O_array: np.ndarray,
    D_array: np.ndarray,
    C_matrix: np.ndarray,
    beta: float,
    rigidity_multiplier: float = 1.0,
    scenario_label: str = 'scenario',
    output_dir=None,
) -> dict:
    """
    凸优化求解刚性变化情景下的 OD 格局。

    在 Wilson 基线先验基础上，将 O/D 刚性参数乘以 rigidity_multiplier，
    用 cvxpy 求解满足 O/D 边际约束的 KL 散度最小化问题。

    Args:
        rigidity_O: O 侧刚性参数 alpha，shape (n_taz,)
        rigidity_D: D 侧刚性参数 gamma，shape (n_taz,)
        O_array: O 边际向量
        D_array: D 边际向量
        C_matrix: 距离矩阵
        beta: 距离衰减系数
        rigidity_multiplier: 刚性变化系数（1.0=不变，1.2=提升20%）
        scenario_label: 情景标识，用于文件命名
        output_dir: 结果保存目录，None 则不保存

    Returns:
        dict: {
            'T_scenario': np.ndarray,   情景 OD 矩阵（浮点，shape n x n）
            'avg_dist': float,          加权平均通勤距离
            'total_flow': float,        总流量
            'solver_status': str,       求解器状态
        }
    """
    try:
        import cvxpy as cp
    except ImportError:
        raise ImportError("请安装 cvxpy: pip install cvxpy")

    from pathlib import Path

    stats = StatsCollector("compute_scenario_od")
    stats.add('rigidity_multiplier', rigidity_multiplier)
    stats.add('scenario_label', scenario_label)

    n = len(O_array)
    m = len(D_array)

    # 构建先验分布（修改后的刚性）
    # log_prior_ij = alpha_i * m + gamma_j * m - beta * C_ij
    log_prior = (
        rigidity_O[:, None] * rigidity_multiplier
        + rigidity_D[None, :] * rigidity_multiplier
        - beta * C_matrix
    )
    prior = np.exp(log_prior)
    # 归一化先验（避免数值溢出）
    prior = prior / prior.sum() * O_array.sum()
    prior = np.clip(prior, 1e-10, None)

    logger.info(f"情景推演: scenario_label={scenario_label}, rigidity_multiplier={rigidity_multiplier}")
    logger.info(f"先验矩阵 shape: {prior.shape}, sum: {prior.sum():.2f}")

    # cvxpy 变量
    T = cp.Variable((n, m), nonneg=True)

    # 目标：KL 散度 sum(T * log(T/prior) - T + prior)，等价于 cp.sum(cp.kl_div(T, prior))
    objective = cp.Minimize(cp.sum(cp.kl_div(T, prior)))

    # 约束：O/D 边际
    constraints = [
        cp.sum(T, axis=1) == O_array,
        cp.sum(T, axis=0) == D_array,
    ]

    prob = cp.Problem(objective, constraints)

    logger.info("开始 cvxpy 求解...")
    try:
        prob.solve(solver=cp.SCS, verbose=False, eps=1e-6, max_iters=10000)
    except Exception as e:
        logger.warning(f"SCS 求解失败: {e}，尝试 ECOS...")
        try:
            prob.solve(solver=cp.ECOS, verbose=False)
        except Exception as e2:
            logger.error(f"ECOS 也失败: {e2}")
            raise

    solver_status = prob.status
    logger.info(f"求解状态: {solver_status}")

    if T.value is None:
        raise RuntimeError(f"cvxpy 求解失败，状态: {solver_status}")

    T_scenario = np.array(T.value)
    T_scenario = np.clip(T_scenario, 0, None)

    total_flow = float(T_scenario.sum())
    # 加权平均距离
    valid_mask = C_matrix > 0
    avg_dist = float(
        np.sum(T_scenario[valid_mask] * C_matrix[valid_mask]) / total_flow
    ) if total_flow > 0 else 0.0

    stats.add('solver_status', solver_status)
    stats.add('total_flow', total_flow)
    stats.add('avg_dist', avg_dist)
    logger.info(f"情景格局: total_flow={total_flow:.0f}, avg_dist={avg_dist:.2f} m")

    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        save_matrix(T_scenario, str(output_dir / 'T_scenario_float.npy'))

        summary_df = pd.DataFrame([{
            'scenario_label': scenario_label,
            'rigidity_multiplier': rigidity_multiplier,
            'solver_status': solver_status,
            'total_flow': total_flow,
            'avg_dist': avg_dist,
        }])
        summary_df.to_csv(output_dir / 'scenario_computation_stats.csv', index=False,
                          encoding='utf-8-sig', float_format='%.4f')

        stats.save('compute_scenario_od_stats.csv')
        logger.info(f"情景推演结果已保存: {output_dir}")

    return {
        'T_scenario': T_scenario,
        'avg_dist': avg_dist,
        'total_flow': total_flow,
        'solver_status': solver_status,
    }


@timer_decorator
def compute_kl_divergence(T_obs, T_model, total_flow=None):
    """
    计算KL散度
    
    KL = sum(T_obs * ln(T_obs / T_model))
    
    Args:
        T_obs: 观测流量矩阵
        T_model: 模型流量矩阵
        total_flow: 总流量（用于归一化）
    
    Returns:
        dict: 包含KL散度、结构弹性等指标
    """
    stats = StatsCollector("compute_kl_divergence")
    
    T_obs = np.array(T_obs, dtype=float)
    T_model = np.array(T_model, dtype=float)
    
    total = total_flow or T_obs.sum()
    
    # 只在两者都>0处计算
    mask = (T_obs > 1e-10) & (T_model > 1e-10)
    
    KL = np.sum(T_obs[mask] * np.log(T_obs[mask] / T_model[mask]))
    
    # 结构弹性
    theta = KL / total if total > 1e-10 else np.nan
    
    # 评级
    if theta > 0.1:
        rating = '强'
    elif theta > 0.01:
        rating = '中'
    else:
        rating = '弱'
    
    stats.add('KL', KL)
    stats.add('theta', theta)
    stats.add('rating', rating)
    stats.add('total_flow', total)
    
    stats.save('compute_kl_divergence_stats.csv')
    
    return {
        'KL': float(KL),
        'theta': float(theta),
        'rating': rating,
        'total_flow': float(total)
    }


@timer_decorator
def run_full_calibration(O, D, C, T_obs, target_distance,
                         beta_range=(0.01, 1.0), output_dir=None):
    """
    运行完整的校准流程
    
    包括：beta校准、Wilson模型计算、KL散度计算
    
    Args:
        O: 起点约束
        D: 终点约束
        C: 成本矩阵
        T_obs: 观测流量矩阵
        target_distance: 目标平均通勤距离
        beta_range: beta扫描范围
        output_dir: 输出目录
    
    Returns:
        dict: 完整结果
    """
    stats = StatsCollector("run_full_calibration")
    
    # 1. 校准beta
    logger.info("=" * 60)
    logger.info("[1/3] 校准beta参数...")
    logger.info("=" * 60)
    
    calibration_result = calibrate_beta(O, D, C, target_distance, beta_range)
    best_beta = calibration_result['best_beta']
    
    if np.isnan(best_beta):
        logger.error("beta校准失败")
        return None
    
    # 2. 使用最优beta计算Wilson模型
    logger.info("\n" + "=" * 60)
    logger.info("[2/3] 使用最优beta计算Wilson模型...")
    logger.info("=" * 60)
    
    wilson_result = compute_wilson(O, D, C, best_beta, return_details=True)
    T_wilson = wilson_result['T_model']
    
    # 3. 计算KL散度
    logger.info("\n" + "=" * 60)
    logger.info("[3/3] 计算KL散度...")
    logger.info("=" * 60)
    
    kl_result = compute_kl_divergence(T_obs, T_wilson)
    
    # 汇总结果
    result = {
        'best_beta': best_beta,
        'target_distance': target_distance,
        'model_distance': wilson_result['avg_dist'],
        'total_flow': wilson_result['total_flow'],
        'KL': kl_result['KL'],
        'theta': kl_result['theta'],
        'rating': kl_result['rating'],
        'calibration': calibration_result,
        'wilson': wilson_result,
        'kl': kl_result
    }
    
    stats.add_dict(result)
    stats.save('run_full_calibration_stats.csv')
    
    # 保存结果
    if output_dir:
        import json
        from .utils import save_json
        
        output_path = f"{output_dir}/calibration_result.json"
        save_json(result, output_path)
        
        # 保存扫描数据
        sweep_df = pd.DataFrame(calibration_result['sweep_data'])
        sweep_df.to_csv(f"{output_dir}/beta_sweep.csv", index=False, encoding='utf-8-sig')
        
        # 保存Wilson结果
        save_matrix(T_wilson, f"{output_dir}/T_wilson.npy")
    
    return result
